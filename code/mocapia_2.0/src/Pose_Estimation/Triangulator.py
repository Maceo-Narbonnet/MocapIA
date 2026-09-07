"""Use functions in this class to triangulate 3D points from 2D points and camera matrices intrinsics aned extrinsics matricies"""
from multiprocessing import Pool
import config.Logger as Logger

import json
import csv
from typing import List, Tuple, Dict
import cv2
import numpy as np
import os
from tqdm import tqdm
from config.Hdf5 import Hdf5_Calib, Hdf5_Detections
from config.Project import MocapProject

from Pose_Estimation.extrinsic_calib import ExtrinsicCalib
from ultralytics import YOLO
from mmpose.apis import MMPoseInferencer
# os.environ["YOLO_VERBOSE"] = "False"
from Pose_Estimation.change_ref_store import save_T, load_T
import numpy as np
import shutil, time
from Pose_Estimation.video_utils import clear_folder


DetectionMatrix = np.ndarray


class UserCancelled(RuntimeError):
    """Raised when the user cancels the processing (window closed / ESC / external stop)."""
    pass
#"rtmpose-x_8xb256-700e_body8-halpe26-384x288"

class Triangulator:
    """This class is used to triangulate 2D points to 3D points using the extrinsics calibration parameters of the cameras.
    The 2D points are obtained from the object decetion and pose estimation on the videos of the cameras in the capture analysis folder.
    Args :
        project_path : str : path to the project folder
        experiment_name : str : name of the experiment (session)
        capture_name : str : name of the capture"""

    def __init__(self, project_path,experiment_name, capture_name, csv_name="", progress_cb=None, stop_cb=None):
        self.project_path = project_path
        self.experiment_name = experiment_name
        self.capture_name = capture_name
        self.project = MocapProject(project_path)
        self.hdf5_calib = Hdf5_Calib(f"{project_path}/{experiment_name}/calibration/{experiment_name}_calibration_param.hdf5")
        self.logger = Logger.Logger().get_logger()
        self.csv_3d_path = os.path.join(project_path, experiment_name, "analysis", capture_name, f"{capture_name}_3D_points.csv")
        # self.csv_3d = open(self.csv_3d_path, "a")
        self.fps = 30
        self.max_frame = 8000
        self.camera_ips = self.project.get_experiment_camera_ips(experiment_name) #get the camera ips
 

        self.connection : List[Tuple[int, int]] = [
            (0, 1), (0, 2), (1, 3), (2, 4),
            (5, 18), (6, 18), (5, 7), (7, 9), (6, 8), (8, 10),
            (17, 18), (18, 19), (19, 11), (19, 12),
            (11, 13), (12, 14), (13, 15), (14, 16),
            (20, 24), (21, 25), (23, 25), (22, 24), (15, 24), (16, 25)]

        self.bodyparts = np.array([
        "Nose","LEye","REye","LEar","REar","LShoulder","RShoulder",
        "LElbow","RElbow","LWrist","RWrist","LHip","RHip","LKnee",
        "RKnee", "LAnkle","RAnkle","Head","Neck","Hip","LBigToe",
        "RBigToe","LSmallToe","RSmallToe","LHeel","RHeel"])

        self.tmp_folder_path = os.path.join(project_path, experiment_name, "calibration", "tmp")
        if not os.path.isdir(self.tmp_folder_path): 
            os.makedirs(self.tmp_folder_path)
        self.hdf5_detection = Hdf5_Detections(f"{self.tmp_folder_path}\{experiment_name}_detections.hdf5")

        self.img_size = self.project.get_img_size(experiment_name)
        self.progress_cb = progress_cb
        self._stop_cb = stop_cb
        
        self.analysis_dir = os.path.join(project_path, experiment_name, "analysis", capture_name)
        self.tmp_dir = os.path.join(self.analysis_dir, ".tmp_run")
        os.makedirs(self.tmp_dir, exist_ok=True)
        self.csv_3d_path_final = self.csv_3d_path
        self.csv_3d_path_tmp = os.path.join(self.tmp_dir, os.path.basename(self.csv_3d_path) + ".tmp")
        
        # Create motion_annotated directory structure
        self.motion_annotated_dir = os.path.join(project_path, experiment_name, "analysis", "motion_annotated")
        self._setup_motion_annotated_dirs()
        
    def _should_stop(self) -> bool:
        """Check if an external stop was requested."""
        try:
            return bool(self._stop_cb and self._stop_cb())
        except Exception:
            return False

    def _emit_progress(self, phase: str, current: int, total: int):
        """Safely invoke the external progress callback"""
        cb = getattr(self, "progress_cb", None)
        if callable(cb):
            try:
                cb(phase, int(current), int(total))
            except Exception:
                pass

    def _load_camera_name_to_id_mapping(self):
        """
        Read the camera_setup section from <project>/<experiment>/config.json and generate a mapping {name -> id/serial/ip}.
        Supports different field names: id / serial / ip / camera_ip.
        """

        try:
            cfg_path = os.path.join(self.project_path, self.experiment_name, "config.json")
            if not os.path.isfile(cfg_path):
                return {}

            with open(cfg_path, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
            cams = cfg.get("camera_setup") or []

            mapping = {}
            for c in cams:
                name = c.get("name")
                ip = c.get("ip")
                if name and ip:
                    mapping[str(name)] = str(ip)
            return mapping
        except Exception as e:
            print("[Triangulator] load camera mapping failed:", e)
            return {}

    def _find_video_for_camera(self, camera_ip: str):
        cap_dir = os.path.join(self.project_path, self.experiment_name, "captures", self.capture_name)
        meta_path = os.path.join(cap_dir, "capture.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                sources = meta.get("sources") or []

                # Match using the camera name → IP mapping
                name_to_id = self._load_camera_name_to_id_mapping()
                for s in sources:
                    if not isinstance(s, dict):
                        continue
                    cam_name = s.get("camera")
                    p = s.get("path")
                    if cam_name and name_to_id.get(cam_name) == camera_ip and p and os.path.isfile(p):
                        return os.path.normpath(p)

                # Fallback: use index-based matching
                if hasattr(self, "camera_ips") and self.camera_ips:
                    try:
                        idx = self.camera_ips.index(camera_ip)
                        if 0 <= idx < len(sources):
                            cand = sources[idx]
                            if isinstance(cand, dict):
                                p = cand.get("path")
                                if p and os.path.isfile(p):
                                    return os.path.normpath(p)
                    except Exception:
                        pass
            except Exception as e:
                print("[Triangulator] Failed to read capture.json:", e)

        # Legacy convention: under captures, files are named <camera_ip>.mp4
        if os.path.isdir(cap_dir):
            path = os.path.join(cap_dir, f"{camera_ip}.mp4")
            if os.path.isfile(path):
                return os.path.normpath(path)

        return None

    def _setup_motion_annotated_dirs(self):
        """Create motion_annotated directory and TSS1-4 subdirectories."""
        os.makedirs(self.motion_annotated_dir, exist_ok=True)
        for i in range(1, 5):
            tss_dir = os.path.join(self.motion_annotated_dir, f"TSS{i}")
            os.makedirs(tss_dir, exist_ok=True)

    def _get_tss_folder_for_camera(self, camera_ip: str) -> str:
        """
        Get the TSS folder (TSS1-4) for a given camera IP.
        Maps camera IP to camera index (0-3) and returns corresponding TSS folder.
        """
        if camera_ip not in self.camera_ips:
            return None
        
        idx = self.camera_ips.index(camera_ip)
        tss_name = f"TSS{idx + 1}"
        tss_folder = os.path.join(self.motion_annotated_dir, tss_name)
        return tss_folder

    def get_2dpoints_video(self, camera_ip: str, show_video: bool = False, inferencer: str = "rtmpose-x_8xb256-700e_body8-halpe26-384x288")-> None:
            """
            Function to perform object detection with YOLOv9 and pose inference with MMPose RTMPose-x on a video.

            Args:
                camera_ip (str): IP address of the camera to process.
                show_video (bool): Whether or not to display the annotated video frames.
                inferencer (str): Name of the MMPose inferencer to use.
            Returns:
            None, but saves the pose annotations to a JSON file. In the analysis/capture_name folder.
            """
            self.logger.info(f"Started inference for camera {camera_ip}")
            json_output_path = os.path.join(
                self.project_path,
                self.experiment_name,
                "analysis",
                self.capture_name,
                f"{camera_ip}_pose_annotations.json",
            )
            # write tmp files
            tmp_json   = os.path.join(self.tmp_dir,    f"{camera_ip}_pose_annotations.json.tmp")
            with open(tmp_json, "w", encoding="utf-8") as f:
                json.dump([], f)

            # loading the video
            video_path = self._find_video_for_camera(camera_ip)
            print("[Triangulator] using video:", video_path)
            if not video_path or not os.path.isfile(video_path):
                self.logger.error(f"Video not found for camera {camera_ip}. Skip.")
                return
            cap = cv2.VideoCapture(video_path)

            # Get video properties
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.max_frame = total_frames

            # Setup video writer for annotated output
            tss_folder = self._get_tss_folder_for_camera(camera_ip)
            video_writer = None
            if tss_folder:
                annotated_video_path = os.path.join(tss_folder, f"{self.capture_name}_annotated.mp4")
                video_writer = cv2.VideoWriter(annotated_video_path, fourcc, fps, (frame_width, frame_height))
                self.logger.info(f"Saving annotated video to: {annotated_video_path}")
            else:
                self.logger.warning(f"Could not determine TSS folder for camera {camera_ip}")


            detector = YOLO("yolo11s.pt")
            # model_pose = YOLO("yolo11s-pose.pt")
            mmpose_inferencer = MMPoseInferencer(inferencer, device="cuda")


            output = []    # stock all pose datas of each frame
            frame_nb = 0    # record the number of the frame
            with tqdm(total=total_frames, desc="Processing video", unit="frame") as pbar:    # progress bar
                # Loop through the video frames
                while cap.isOpened():
                    # Read a frame from the video
                    ret, frame = cap.read()  # IMPORTANT: capturer aussi 'ret'
                    # Si la lecture echoue ou fin de video, on sort
                    if not ret or frame is None:
                        break

                    # Perform YOLOv9 tracking on the frame, persisting tracks across frames

                    results = detector.track(frame, classes=0, persist=True)    # target(classes=0 to detect the persons) detector + track
                    annotated_frame_yolo = results[0].plot()    # draw the bounding box
                    # Creer la structure pour cette frame
                    frame_data = {'instances': {}}


                    if results[0].boxes.id is not None:
                        id_list = results[0].boxes.id    # take all the target IDs detected

                        # Iterate over the detected subjects
                        for id_nb, box in enumerate(results[0].boxes):
                            x1, y1, x2, y2 = map(int, box.xyxy[0])    # x1,y1,x2,y2 are target's boundary's coordinates, it's used to crop the person's image
                            crop_img = frame[y1:y2, x1:x2]    # crop the humain being part detected, used for pose estimation

                            # Pose inference with MMPose body26
                            mmpose_inference = mmpose_inferencer(crop_img)    # begin the pose estimation
                            # yolo_inference = model_pose(crop_img)
                            # print(yolo_inference)
                            result = next(mmpose_inference)    # get the result of pose estimation

                            keypoints = result['predictions'][0][0]['keypoints']    # get the keypoints of human being

                            output_keypoints = []    # used for stocking the current target's keypoints

                            for keypoint in keypoints:
                                x, y = keypoint[0], keypoint[1]
                                adjusted_x, adjusted_y = x + x1, y + y1    # adjust the coordinates to the original images
                                cv2.circle(annotated_frame_yolo, (int(adjusted_x), int(adjusted_y)), 5, (255, 100, 0), -1)    # draw the keypoints in the image
                                output_keypoints.append([adjusted_x, adjusted_y])    # stock the keypoints

                            frame_data['instances'][int(id_list[id_nb].item())] = output_keypoints    

                            for connection in self.connection:    # iterate the self.connection, define the connection's relation of body's bones  
                                start_point = tuple(map(int, output_keypoints[connection[0]]))
                                end_point = tuple(map(int, output_keypoints[connection[1]]))
                                cv2.line(annotated_frame_yolo, start_point, end_point, (0, 255, 0), 2)    # draw the lines to  connect the keypoints

                    # Ajouter la frame SEULEMENT si elle contient des detections
                    # OU si on veut garder toutes les frames (meme vides) pour la synchronisation
                    output.append(frame_data)

                    # Write annotated frame to video
                    if video_writer is not None:
                        video_writer.write(annotated_frame_yolo)

                    # Ajouter l'affichage de la frame annotee
                    if show_video:
                        win = "Annotated Frame"
                        cv2.imshow(win, annotated_frame_yolo)    # show the video frames after labeling

                        # First, process the event queue (including clicking the X button)
                        key = cv2.waitKey(1) & 0xFF

                        # 1) Keyboard exit (q or ESC)
                        if key in (ord('q'), 27):
                            self.logger.info("User requested exit via keyboard.")
                            try:
                                cv2.destroyWindow(win)
                            except Exception:
                                pass
                            raise UserCancelled("Cancelled by keyboard")

                        # 2) Window closed (clicked the X button in the top-right corner)
                        try:
                            vis = cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE)
                        except Exception:
                            # Some backends raise an exception when the window is closed; treat it as closed
                            vis = 0.0
                        if vis < 1:
                            try:
                                cv2.destroyWindow(win)
                            except Exception:
                                pass
                            raise UserCancelled("Window closed by user")

                    # 3) External thread cancellation request (from RTMPoseThread.cancel())
                    if self._should_stop():
                        try: cv2.destroyAllWindows()
                        except Exception: pass
                        raise UserCancelled("Cancelled by external request")
                    pbar.update(1)
                    frame_nb += 1
                    
            # Supprimer les frames vides a la fin du JSON avant de sauvegarder
            while output and not output[-1]['instances']:
                output.pop()
                print(f"[Triangulator] Removed trailing empty frame, new length: {len(output)}")

            # Save JSON output
            with open(tmp_json, "w", encoding="utf-8") as f:
                json.dump(output, f)
            print(f"[Triangulator] Saved {len(output)} frames to {json_output_path}")

            # Release video capture and writer objects
            cap.release()
            if video_writer is not None:
                video_writer.release()
                self.logger.info(f"Annotated video saved successfully for camera {camera_ip}")
            cv2.destroyAllWindows()  # Make sure all windows are closed properly


    def get_2dpoints_all_videos(self, save_video: bool = False,
                                inferencer: str = "rtmpose-x_8xb256-700e_body8-halpe26-384x288"):
        """Run 2D for all cameras. All tmp JSONs will be promoted to final only if all succeed."""
        cams_ok = []
        try:
            for camera_ip in self.camera_ips:
                if self._should_stop():
                    raise UserCancelled("Cancelled before next camera")
                self.get_2dpoints_video(camera_ip, save_video, inferencer)
                cams_ok.append(camera_ip)

            # — Once all cameras are done, atomically replace tmp with final —
            for ip in cams_ok:
                tmp_json = os.path.join(self.tmp_dir,     f"{ip}_pose_annotations.json.tmp")
                fin_json = os.path.join(self.analysis_dir, f"{ip}_pose_annotations.json")
                if os.path.isfile(tmp_json):
                    os.replace(tmp_json, fin_json)

        except UserCancelled:
            # Cancelled: do not write to disk or overwrite existing files;
            # keep any temporary files so that the upper layer can decide whether to clean them up
            raise
        except Exception:
            # On exception: do not write to disk either, let the upper layer handle the failure
            raise


    def convert_json_to_array(self, camera_ip:str, subject_ids:int):
        """Read the json file for the corresponding camera and return a numpy array of the 2D points for the subject.
        Args : 
            camera_ip : str : camera ip
            subject_id : List[int] : list of the subjects id
        Returns :
            numpy array : 2D points for the subject (shape : (nb_frames, nb_bodyparts, 2))
        """

        json_path = os.path.join(self.project_path, self.experiment_name, "analysis", self.capture_name, f"{camera_ip}_pose_annotations.json")
        with open(json_path, 'r') as file:
            d = json.load(file)

        # Initialize result array
        res = []

        # Create a NaN-filled array to use when subject not found
        nan_array = np.full((self.bodyparts.shape[0], 2), np.nan)

        # Iterate through frames in the JSON data
        for i in range(len(d)):
            subject_found = False

            # Iterate through subject IDs
            for subject_id in subject_ids:
                # Check if the current subject ID exists in the current frame's instances
                if str(subject_id) in d[i]['instances']:
                    # Append the subject's pose to the result array
                    res.append(np.array(d[i]['instances'][str(subject_id)]))
                    subject_found = True
                    break

            # If the subject was not found in the current frame, append a NaN array
            if not subject_found:
                res.append(nan_array)

        # Convert the result array to a NumPy array and reshape
        res = np.array(res)
        res = res.reshape(res.shape[0], res.shape[1] * res.shape[2])
        return res.reshape(res.shape[0], res.shape[1] // 2, 2)

    def get_camera_dict_for_subject(self, frame_indice:int, subject_ids:Dict[str, List[int]]) -> Dict[str, np.ndarray]:
        """This function return a dictionary {camera_ip : 2D points} for the subject_ids. where 2D points is a numpy array of shape (nb_frames, nb_bodyparts, 2)
        Args : 
            frame_indice : int : the frame indice
            subject_ids : dict of list of subjects ids for each cameras.
        Returns :
            dict : {camera_ip : 2D points} where 2D points is a numpy array of shape (nb_bodyparts, 2) of the 2D points for the subject at the frame_indice"""
        camera_dict_for_subject = {}
        for camera_ip in subject_ids.keys(): #iterate over the camera ips
            points_array_each_frame = self.convert_json_to_array(camera_ip, subject_ids[camera_ip]) #get the 2D points for the subject (shape : (nb_frames, nb_bodyparts, 2))
            points_array = points_array_each_frame[frame_indice] #get the 2D points for the subject at the frame_indice (shape : (nb_bodyparts, 2))
            camera_dict_for_subject[camera_ip] = points_array
        return camera_dict_for_subject


    def add_headers_to_csv(self)-> None:
        """Add headers lines to the csv file, if the file is empty
        CSV header structure : Same as Vicon cvs files structure :
        Trajectories
        120 (framerate)
               | Bodypart1 | Bodypart2 | Bodypart3 | ... | BodypartN |
        Frames | X | Y | Z | X | Y | Z | X | Y | Z | ... | X | Y | Z |
               |mm |mm |mm |mm |mm |mm |mm |mm |mm | ... |mm |mm |mm |

        all with "," separators"""
        # assert self.is_empty_csv()

        row_1 = ["Trajectories"]
        row_2 = [str(self.fps)]
        row_3 = [""]
        row_4 = ["Frames"]
        row_5 = [""]

        #create the headers
        for bodypart in self.bodyparts:
            row_3 += [bodypart,"",""]
            row_4 += ["X","Y","Z"]
            row_5 += ["mm","mm","mm"]

        #write the headers to the csv file
        with open(self.csv_3d_path_tmp, "w", newline="") as csv_3d:
            csv_writer = csv.writer(csv_3d)
            csv_writer.writerow(row_1)
            csv_writer.writerow(row_2)
            csv_writer.writerow(row_3)
            csv_writer.writerow(row_4)
            csv_writer.writerow(row_5)



    def add_line_to_csv(self,frame_indice:int, points_3d:np.ndarray)-> None:
        """Add a line to the csv file with the 3D points for the subject at the frame_indice.
        Args : 
            points_3d: np.ndarray : 3D points for the subject (shape : (nb_bodyparts, 3))
            frame_indice : int : the frame indice"""

        row = [frame_indice]+points_3d.flatten().tolist()

        with open(self.csv_3d_path_tmp, "a", newline="") as csv_3d:
            csv_writer = csv.writer(csv_3d)
            csv_writer.writerow(row)


    def change_ref(self, T:np.ndarray, points:np.ndarray)->np.ndarray:
        """Change the reference of the 3D points with the transformation matrix.
        Args :
        T : np.ndarray : homogenous transformation matrix (shape : (4,4))
        points : np.ndarray : 3D points (shape : (nb_points, 3))
        Returns :
        np.ndarray : 3D points with the new reference (shape : (nb_points, 3))"""

        # Add a colum of ones to the points (N x 4) to get the homogeneous coordinates
        points_homogeneous = np.column_stack((points, np.ones(points.shape[0])))
        # applie the transformation matrix to the points
        points_transformed_homogeneous = np.dot(points_homogeneous, T.T)
        # Remove the last column of ones to get the 3D points
        points_R2 = points_transformed_homogeneous[:, :3]
        return points_R2
    
    def cleanup_tmp(self, force: bool = True) -> None:
        """Thin wrapper around utils.clear_folder; keeps Triangulator API stable."""
        tmp = getattr(self, "tmp_dir", None)
        if not tmp:
            return
        if force:
            try:
                shutil.rmtree(tmp, ignore_errors=False)
                return
            except Exception:
                # fallback: a file handle might not be released yet; wait a bit and try a softer cleanup
                time.sleep(0.2)
        # Gentle cleanup: empty files, remove directory if empty; with slight retries
        try:
            clear_folder(tmp, remove_dir_if_empty=True, retries=3, retry_delay=0.2)
        except Exception:
            # Failsafe: don't let cleanup errors affect the main workflow
            pass

    def point_to_csv(self, subject_ids: Dict[str, List[int]] = None, T: np.ndarray = None) -> None:
        """Use the functions in extrinsic calib to get the 3Dpoints for the subject_ids.
        Args:
            subject_ids : dict like {"C2314...53": [1,2], "C2314...54": [1]}
            T : transformation matrix (3x3 or 4x4); None => no transform
        """
        
        # --------------------------------------------------
        # Auto-load change reference matrix if not provided
        # --------------------------------------------------
        if T is None:
            T_loaded = load_T(self.project_path, self.experiment_name)
            if T_loaded is not None:
                T = T_loaded
                print("[Triangulator] Loaded change_ref matrix from disk")
            else:
                print("[Triangulator] No change_ref matrix found, using local frame")
                
        extrinsic = ExtrinsicCalib(self.project_path, self.experiment_name, (5, 6), 120)
        self.add_headers_to_csv()

        # --- NEW: clamp the frame count to shortest per-camera 2D json length ---
        lengths = []
        for cam_id in self.camera_ips:
            fp = os.path.join(
                self.project_path, self.experiment_name, "analysis",
                self.capture_name, f"{cam_id}_pose_annotations.json"
            )
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f) or []
                                
                # data est une liste de frames: [{'instances': {...}}, {'instances': {...}}, ...]
                if not isinstance(data, list):
                    print(f"[Triangulator] Warning: {fp} is not a list, skipping")
                    lengths.append(0)
                    continue
                
                # Exclure les frames vides a la fin
                valid_length = len(data)
                while valid_length > 0:
                    last_frame = data[valid_length - 1]
                    
                    # Verifier que last_frame est un dictionnaire
                    if not isinstance(last_frame, dict):
                        valid_length -= 1
                        continue
                    
                    instances = last_frame.get('instances', {})
                    
                    # Verifier que instances n'est pas vide
                    if instances and isinstance(instances, dict) and len(instances) > 0:
                        # Verifier qu'au moins une instance a des keypoints valides
                        has_valid_keypoints = False
                        for inst_id, inst_data in instances.items():
                            # inst_data peut etre une liste de keypoints directement
                            if isinstance(inst_data, list) and len(inst_data) > 0:
                                has_valid_keypoints = True
                                break
                            # ou un dictionnaire avec une cle 'keypoints'
                            elif isinstance(inst_data, dict):
                                keypoints = inst_data.get('keypoints', [])
                                if keypoints and len(keypoints) > 0:
                                    has_valid_keypoints = True
                                    break
                        if has_valid_keypoints:
                            break
                    valid_length -= 1
                    print(f"[Triangulator] Excluding empty frame at index {valid_length} for camera {cam_id}")
                
                lengths.append(valid_length)
                print(f"[Triangulator] Camera {cam_id}: {len(data)} total frames, {valid_length} valid frames")

            except Exception as e:
                print(f"[Triangulator] cannot read {fp}: {e}")
                import traceback
                traceback.print_exc()
                lengths.append(0)

        min_len = min(lengths) if lengths else 0
        if min_len <= 0:
            # If there are no usable frames, return early to avoid IndexError later
            if hasattr(self, "logger"):
                self.logger.error("No frames to process (2D outputs are empty).")
            else:
                print("[Triangulator] No frames to process (2D outputs are empty).")
            return

        # Use the common minimum number of frames to drive the following loops
        prev_cap = getattr(self, "max_frame", None)
        if prev_cap is None:
            self.max_frame = min_len
        else:
            self.max_frame = min(int(prev_cap), int(min_len))

        print(f"[Triangulator] json_min_len={min_len}, cap_in={prev_cap} -> using max_frame={self.max_frame}")
        self._emit_progress("3d", 0, int(self.max_frame))
        
        # Main loop — triangulation with per-frame validity checks
        written_frames = 0
        try:
            for frame in range(self.max_frame):

                # Support external cancel
                if self._should_stop():
                    raise UserCancelled("Cancelled during 3D triangulation")

                cameras_points_dict = self.get_camera_dict_for_subject(frame, subject_ids)

                # Check: all cameras returned NaN?
                has_valid_data = False
                for cam_ip, pts in cameras_points_dict.items():
                    if pts is not None and not np.all(np.isnan(pts)):
                        has_valid_data = True
                        break

                if not has_valid_data:
                    print(f"[Triangulator] Frame {frame}: skipping (all cameras have NaN data)")
                    continue

                # ================================
                # T applied → use global triangulation
                # ================================
                if T is not None:
                    points_3d = extrinsic.triangulate_points_global(cameras_points_dict)
                    if points_3d is not None and not np.all(np.isnan(points_3d)):
                        points_3d = self.change_ref(T, points_3d)
                        self.add_line_to_csv(frame, points_3d)
                        written_frames += 1
                    else:
                        print(f"[Triangulator] Frame {frame}: skipping (triangulated points are all NaN)")

                # ================================
                # No T → use local triangulation
                # ================================
                else:
                    points_3d, _ = extrinsic.triangulate_points(cameras_points_dict)
                    if points_3d is not None and not np.all(np.isnan(points_3d)):
                        self.add_line_to_csv(frame, points_3d)
                        written_frames += 1
                    else:
                        print(f"[Triangulator] Frame {frame}: skipping (triangulated points are all NaN)")

                # UI progress
                self._emit_progress("3d", frame + 1, int(self.max_frame))

            print(f"[Triangulator] Finished: wrote {written_frames} frames to CSV")

            # ============================================================
            # 3) Promote tmp CSV → final CSV
            # ============================================================
            try:
                if os.path.isfile(self.csv_3d_path_tmp):
                    os.replace(self.csv_3d_path_tmp, self.csv_3d_path_final)
                    self.cleanup_tmp(force=True)
                    if hasattr(self, "logger"):
                        self.logger.info("3D CSV promoted to final: %s", self.csv_3d_path_final)
                    else:
                        print("[Triangulator] 3D CSV promoted:", self.csv_3d_path_final)
            except Exception as e:
                if hasattr(self, "logger"):
                    self.logger.error("Promote 3D CSV failed: %s", e)
                else:
                    print("[Triangulator] Promote 3D CSV failed:", e)

        except UserCancelled:
            raise
        except Exception:
            raise
                
        




    def calculate_transformation_matrix(self, points_R1 : np.ndarray, points_R2 : np.ndarray) -> np.ndarray:
        """
        Compute the transformation matrix to switch from frame R1 to R2.

        Args:
            points_R1: np.array of size (3, 3) representing 3 points in R1.
            points_R2: np.array of size (3, 3) representing the same 3 points in R2.

        Returns:
            T: np.array of size (4, 4) representing the homogeneous transformation matrix.
        """

        O1, X1, Y1 = points_R1[0, :], points_R1[1, :], points_R1[2, :]

        # Points dans R2
        O2, X2, Y2 = points_R2

        # Calcul des axes pour R1
        x_R1 = (X1 - O1) / np.linalg.norm(X1 - O1)
        temp_y_R1 = (Y1 - O1)
        y_R1 = temp_y_R1 - np.dot(temp_y_R1, x_R1) * x_R1  # Orthogonaliser
        y_R1 /= np.linalg.norm(y_R1)
        z_R1 = np.cross(x_R1, y_R1)

        # Base R1
        R1_basis = np.column_stack((x_R1, y_R1, z_R1))

        # Calcul des axes pour R2
        x_R2 = (X2 - O2) / np.linalg.norm(X2 - O2)
        temp_y_R2 = (Y2 - O2)
        y_R2 = temp_y_R2 - np.dot(temp_y_R2, x_R2) * x_R2  # Orthogonaliser
        y_R2 /= np.linalg.norm(y_R2)
        z_R2 = np.cross(x_R2, y_R2)

        # Base R2
        R2_basis = np.column_stack((x_R2, y_R2, z_R2))

        # Matrice de rotation
        R = R2_basis @ np.linalg.inv(R1_basis)

        # Translation
        t = O2 - R @ O1

        # Matrice de transformation homogène
        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = t
        return T





if __name__ == "__main__":
    from config.Hdf5 import Hdf5_Calib
    project_path = r"D:\Users\Etudiant\Documents\MoCapIA5\mocapia_3\TestProject11"
    experiment_name = r"MoCap_Demo5"



    # Read the three points (O, X, Y) of each camera — from the JSON generated by video_utils.py.
    points_json = os.path.join(project_path, experiment_name, "calibration", "change_ref_points.json")
    with open(points_json, "r", encoding="utf-8") as f:
        data = json.load(f)  # in the form {"C3501325621627": [[xO,yO],[xX,yX],[xY,yY]], ...}

    # Convert to a np.array and feed it to the triangulation; at least two cameras are required.
    cam_points = {cam: np.array(pts, dtype=float) for cam, pts in data.items()}

    hdf5_calib = Hdf5_Calib(f"{project_path}/{experiment_name}/calibration/{experiment_name}_calibration_param.hdf5")
    ext = ExtrinsicCalib(project_path, experiment_name, (6, 5), 120)
    # ext = ExtrinsicCalib(project_path, experiment_name, (11, 10), 47)
    # pt_3D, _ = ext.triangulate_points({"C3501350052453": np.array(pt_1), "C3501325621627": np.array(pt_2)})
    # TSS1 ip: "C3501350052453", TSS2 ip: "C3501325621627",TSS3 ip: "C3501325588979"， TSS4 ip: "C3501325623877"
    pt_3D, _ = ext.triangulate_points(cam_points)   
    

    tri = Triangulator(project_path, experiment_name, "Capture 1", "test")
    point_R2 = np.array([[0, 0, 0], [160, 0, 0], [0, 120, 0]])
    transformation_matrix = tri.calculate_transformation_matrix(pt_3D, point_R2)
    save_T(project_path, experiment_name, transformation_matrix)
    print("Saved T to JSON:\n", transformation_matrix)
    



    # tri.point_to_csv({"C3501350052453": [1], "C3501325621627": [1],"C3501325588979":[1], "C3501325623877": [1]}, transformation_matrix)



    #"C3501325588979":[1]
