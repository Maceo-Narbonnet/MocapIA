from typing import Tuple, Dict
import cv2
import numpy as np
import pickle
import os
import re
from tqdm import tqdm
from itertools import combinations
from config.Hdf5 import Hdf5_Calib, Hdf5_Detections
from config.Project import MocapProject
import threading
from concurrent.futures import ThreadPoolExecutor
from scipy.optimize import least_squares
import matplotlib.pyplot as plt
import traceback
from Pose_Estimation.reprojection_utiles import project_point, reprojection_error_func, optimize_3d_point
DetectionMatrix = np.ndarray
Point3D = np.ndarray


#!----------------------- Chessboard detection -----------------------!#
class ExtrinsicCalib:
    """This class implements a chessboard detection and camera calibration for multiple cameras."""

    def __init__(self, project_path:str,experiment_name:str, chessboard_size:Tuple[int, int], square_size:float, nb_img:int = 41):
        """Initialize the ExtrinsicCalib object.
        args : 
            project_path (str) : the path of the project
            experiment_name (str) : the name of the experiment
            chessboard_size (Tuple[int, int]) : the size of the chessboard in the experiment
            square_size (float) : the size of the square of the chessboard in mm
            nb_img (int) : the number of images to use for the calibration, the more image you have, the better the calibration will be"""

        self.project_path = project_path
        self.experiement_name = experiment_name
        self.project = MocapProject(project_path)
        self.hdf5_calib = Hdf5_Calib(f"{project_path}/{experiment_name}/calibration/{experiment_name}_calibration_param.hdf5")

        self.camera_ips = self.project.get_experiment_camera_ips(experiment_name) #get the camera ips of the experiment

        self.chessboard_size = chessboard_size
        self.square_size = square_size
        self.tmp_folder_path = os.path.join(project_path, experiment_name, "calibration", "tmp")
        if not os.path.isdir(self.tmp_folder_path): 
            os.makedirs(self.tmp_folder_path)
        self.hdf5_detection = Hdf5_Detections(f"{self.tmp_folder_path}\{experiment_name}_detections.hdf5")

        self.img_size = self.project.get_img_size(experiment_name)
        self.nb_images = nb_img
        self.frame_counter = 0


    def get_tmp_images_folders(self):
        """Return the sub tmp folder of each cameras after verification that the folder exists."""
        return [f"{self.tmp_folder_path}/{camera_ip}_tmp" for camera_ip in self.camera_ips if os.path.isdir(f"{self.tmp_folder_path}/{camera_ip}_tmp")]
    
    def chessboard_Errors(self, draw_image:bool=False)-> float:
        """Return the error of the chessboard corners detection, based on the theoric corners
        That's not useful because this fonction can be used after the writting of 2D coordinates in the HDF5, we prefer to write only the goods 2D coord. """
        # --- Générer points 3D du damier (repère local du damier) ---
        # chessboard_size = (6, 5)
        # square_size = 120  # mm
        objp = np.zeros((self.chessboard_size[0] * self.chessboard_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:self.chessboard_size[0], 0:self.chessboard_size[1]].T.reshape(-1, 2)
        objp *= square_size

        for cam_ip in self.camera_ips:
            K, dist = self.hdf5_calib.read_intrinsics(cam_ip)
            
            for i in range(self.nb_images):
                image = str(i)
                if not self.hdf5_detection.is_detected(cam_ip, image):
                    continue
                corners_cam = self.hdf5_detection.read_detections(cam_ip, image)
                corners_cam = corners_cam.squeeze()

                if corners_cam.shape[0] != objp.shape[0]:
                    print(f"Frame {image} ignorée : nombre de coins incorrect")
                    continue

                # --- Estimer la pose du damier avec solvePnP ---
                success, rvec, tvec = cv2.solvePnP(objp, corners_cam, K, dist)
                if not success:
                    print(f"Frame {image} : solvePnP a échoué")
                    continue
                # --- Reprojection des points ---
                pts2d_reproj, _ = cv2.projectPoints(objp, rvec, tvec, K, dist)
                pts2d_reproj = pts2d_reproj.squeeze()

                # --- Calcul de l'erreur de reprojection ---
                reproj_error = np.mean(np.linalg.norm(corners_cam - pts2d_reproj, axis=1))
                print(f"Frame {image} : erreur de reprojection moyenne = {reproj_error:.2f} px")

                if draw_image:
                    # --- Visualisation ---
                    img_path = os.path.join(self.tmp_folder_path, f"{cam_ip}_tmp/frame_{int(image):04d}.jpg")
                    if not os.path.exists(img_path):
                        continue
                    img = cv2.imread(img_path)
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                    for pt in corners_cam:
                        cv2.circle(img_rgb, (int(pt[0]), int(pt[1])), 5, (255, 0, 0), -1)  # rouge = détectés
                    for pt in pts2d_reproj:
                        cv2.drawMarker(img_rgb, (int(pt[0]), int(pt[1])), (0, 255, 0),
                                    markerType=cv2.MARKER_CROSS, markerSize=10, thickness=2)  # vert = reprojetés

                    plt.figure(figsize=(10, 8))
                    plt.imshow(img_rgb)
                    plt.axis('off')
                    plt.title(f"Caméra {cam_ip} - Frame {image} : rouge = détectés, vert = reprojetés, erreur = {reproj_error:.2f}px")
                    plt.show()


    def frame_chessboardError(self, cam_ip: int, filename: str, corners_cam: np.array, draw_corners: bool=False) -> float:
        """Calcule l'erreur de reprojection pour une image donnée."""
        try:
            print(f"[frame_chessboardError] Starting for cam={cam_ip}, file={filename}", flush=True)
            
            objp = np.zeros((self.chessboard_size[0] * self.chessboard_size[1], 3), np.float32)
            objp[:, :2] = np.mgrid[0:self.chessboard_size[0], 0:self.chessboard_size[1]].T.reshape(-1, 2)
            objp *= self.square_size
            print(f"[frame_chessboardError] objp created, shape={objp.shape}", flush=True)
            
            print(f"[frame_chessboardError] Reading intrinsics...", flush=True)
            mtx, dist = self.hdf5_calib.read_intrinsics(cam_ip)
            print(f"[frame_chessboardError] Intrinsics OK: mtx shape={mtx.shape}", flush=True)

            if corners_cam.shape[0] != objp.shape[0]:
                print(f"[frame_chessboardError] Wrong number of corners: {corners_cam.shape[0]} vs {objp.shape[0]}", flush=True)
                return None

            print(f"[frame_chessboardError] Calling solvePnP...", flush=True)
            success, rvec, tvec = cv2.solvePnP(objp, corners_cam, mtx, dist)
            print(f"[frame_chessboardError] solvePnP result: success={success}", flush=True)
            
            if not success: 
                print("solvePnp n'a pas fonctionné", flush=True)
                return None

            print(f"[frame_chessboardError] Calling projectPoints...", flush=True)
            pts2d_reproj, _ = cv2.projectPoints(objp, rvec, tvec, mtx, dist)
            pts2d_reproj = pts2d_reproj.squeeze()
            print(f"[frame_chessboardError] projectPoints OK", flush=True)

            reproj_error = np.mean(np.linalg.norm(corners_cam - pts2d_reproj, axis=1))
            print(f"[frame_chessboardError] reproj_error = {reproj_error:.4f}", flush=True)

            # --- Visualisation ---
            if draw_corners:
                # --- Visualisation ---
                img_path = os.path.join(self.tmp_folder_path, f"{cam_ip}_tmp/frame_{int(filename):04d}.jpg")
                if os.path.exists(img_path):
                    # Lecture de l'image
                    img_vis = cv2.imread(img_path)
                    
                    # Dessin des points détectés (Rouge)
                    for pt in corners_cam:
                        cv2.circle(img_vis, (int(pt[0]), int(pt[1])), 5, (0, 0, 255), -1)
                    
                    # Dessin des points reprojetés (Vert)
                    for pt in pts2d_reproj:
                        cv2.drawMarker(img_vis, (int(pt[0]), int(pt[1])), (0, 255, 0),
                                    markerType=cv2.MARKER_CROSS, markerSize=10, thickness=2)
                    
                    # Affichage avec OpenCV
                    window_name = f"Camera {cam_ip} - Reproj Error: {reproj_error:.2f}"
                    # Redimensionner si l'image est trop grande pour l'écran (optionnel, ex: 50%)
                    # img_vis = cv2.resize(img_vis, None, fx=0.5, fy=0.5)
                    
                    cv2.imshow(window_name, img_vis)
                    
                    print(f"--> Image affichée. Appuyez sur une touche pour continuer (ou 'q' pour quitter)...")
                    
                    # Attend une touche indéfiniment (0) pour laisser le temps de voir
                    key = cv2.waitKey(0) 
                    
                    # Ferme la fenêtre actuelle pour passer à la suivante proprement
                    cv2.destroyWindow(window_name)
                    
                    # Si on appuie sur 'q', on arrête tout
                    if key == ord('q'):
                        print("Arrêt demandé par l'utilisateur.")
                        exit()

            
            return reproj_error
            
        except Exception as e:
            import traceback
            print(f"[frame_chessboardError] EXCEPTION: {e}", flush=True)
            traceback.print_exc()
            return None

    def evaluate_calibration(self, reproj_errors: Dict[str, Dict[str, float]])-> None:
        """ Evaluate the calibration by returning the number of images selected for each camera"""

        for cam in reproj_errors.keys():
            nb_images_selected = len(reproj_errors[cam])

            if nb_images_selected < 5:
                print(f"⚠️ Camera {cam} has fewer than 5 images stored ({nb_images_selected} images)")
            elif nb_images_selected < 10:
                print(f" Nb of images for camera {cam} OK ({nb_images_selected} images)")
            else:
                print(f" Nb of images for camera {cam} very OKK ({nb_images_selected} images)")


    def perform_detections(self, draw_corners: bool = False, progress_cb=None):
        """
        Perform chessboard detection on images from all cameras and store results in HDF5.
        New version fully integrates intrinsic checking, reprojection error, detailed logs,
        and robust error handling from the diff.
        """

        import re
        import traceback

        # ---------------------------------------------------------------
        # 1) Get tmp folders and print them (from diff)
        # ---------------------------------------------------------------
        folder_list = list(self.get_tmp_images_folders())
        folder_list.sort(key=lambda p: str(p))

        print(f"[ExtrinsicCalib] TMP folders = {folder_list}", flush=True)

        # Reprojection error dictionary (per camera)
        reproj_errors = {}

        # Count total number of frames
        exts = (".jpg", ".jpeg", ".png", ".bmp")
        total = 0
        for folder_path in folder_list:
            try:
                files = [f for f in os.listdir(folder_path) if f.lower().endswith(exts)]
                total += len(files)
            except Exception:
                pass
        total = max(1, int(total))
        done = 0

        # ---------------------------------------------------------------
        # 2) Loop over each camera folder
        # ---------------------------------------------------------------
        for folder_path in folder_list:

            cam_ip = os.path.basename(folder_path).split("_")[0]
            reproj_errors[cam_ip] = {}
            print(f"[ExtrinsicCalib] Processing camera: {cam_ip}", flush=True)

            # --- Check intrinsics exist before processing images ---
            try:
                mtx, dist = self.hdf5_calib.read_intrinsics(cam_ip)
                print(f"[OK] Intrinsics loaded for {cam_ip}, shape={mtx.shape}", flush=True)
            except Exception as e:
                print(f"[FATAL] Cannot read intrinsics for {cam_ip}: {e}", flush=True)
                traceback.print_exc()
                continue

            # --- Get image filenames ---
            try:
                filenames = [f for f in os.listdir(folder_path) if f.lower().endswith(exts)]
                filenames.sort()
            except Exception:
                filenames = []

            # ---------------------------------------------------------------
            # 3) Process each image
            # ---------------------------------------------------------------
            for filename in filenames:
                img_path = os.path.join(folder_path, filename)

                try:
                    # ---- Step 0: read image safely ----
                    image = cv2.imread(img_path)
                    if image is None:
                        print(f"[ERROR] Cannot read image: {img_path}", flush=True)
                        continue

                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    eq_gray = cv2.equalizeHist(gray)

                    print(f"[ExtrinsicCalib] Frame {done}: processing...", flush=True)

                    # ---- Visualisation de l'image traitée (TOUJOURS) ----
                    if draw_corners:
                        img_display = image.copy()
                        cv2.putText(img_display, f"Cam: {cam_ip} | Frame: {filename}", 
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                        cv2.putText(img_display, f"Chessboard: {self.chessboard_size}", 
                                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                    # ---- Step 1: detect corners ----
                    ret, corners = cv2.findChessboardCorners(
                        eq_gray, self.chessboard_size,
                        cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
                    )
                    print(f"[ExtrinsicCalib] Chessboard found: {ret}", flush=True)

                    if draw_corners:
                        if ret:
                            cv2.drawChessboardCorners(img_display, self.chessboard_size, corners, ret)
                            cv2.putText(img_display, "DETECTE !", (10, 90), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        else:
                            cv2.putText(img_display, "NON DETECTE", (10, 90), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                        
                        cv2.imshow("Detection Chessboard", img_display)
                        key = cv2.waitKey(100)  # Affiche 100ms par image (automatique)
                        if key == ord('q'):
                            print("Arrêt demandé par l'utilisateur.")
                            cv2.destroyAllWindows()
                            return

                    if not ret:
                        print(f"[Chessboard] Not detected in {filename}", flush=True)
                        continue

                    # ---- Step 2: cornerSubPix ----
                    print("[DEBUG] Step 1: cornerSubPix...", flush=True)
                    corners_subpixed = cv2.cornerSubPix(
                        gray, corners, (11, 11), (-1, -1),
                        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                    )
                    print(f"[DEBUG] Step 1 OK: refined corners shape={corners_subpixed.shape}", flush=True)

                    # ---- Compute image ID ----
                    try:
                        image_id = str(int(re.split(r"[_.]", filename)[-2]))
                    except Exception:
                        image_id = str(done)

                    print(f"[DEBUG] Step 2: image_id = {image_id}", flush=True)

                    # ---- Step 3: compute reprojection error ----
                    print("[DEBUG] Step 3: Calling frame_chessboardError...", flush=True)
                    reproj_error = self.frame_chessboardError(
                        cam_ip,
                        image_id,
                        corners_subpixed.squeeze(),
                        draw_corners
                    )
                    print(f"[DEBUG] Step 3 OK: reproj_error = {reproj_error}", flush=True)

                    # ---- Step 4: write to HDF5 if valid ----
                    if reproj_error is not None and reproj_error <= 5:
                        reproj_errors[cam_ip][image_id] = reproj_error
                        print("[DEBUG] Step 4: Writing to HDF5...", flush=True)
                        self.hdf5_detection.write_detections(cam_ip, image_id, corners_subpixed)
                        print(f"[DEBUG] Step 4 OK: Frame {image_id} saved", flush=True)
                    else:
                        print(f"[SKIP] Frame {image_id} ignored (error={reproj_error}px)", flush=True)

                except Exception as e:
                    print(f"[EXCEPTION] Error processing {filename}: {e}", flush=True)
                    traceback.print_exc()
                finally:
                    done += 1
                    if callable(progress_cb):
                        try:
                            progress_cb(int(done), int(total))
                        except:
                            pass




    def get_detection_matrix(self) -> DetectionMatrix: #* TEST RAS
        """Return a matrix of the number of detected images in common between the cameras."""

        nb_cam = len(self.camera_ips)
        detection_matrix : DetectionMatrix = np.zeros((nb_cam, nb_cam), dtype=np.ndarray)

        for cam_indice_1, cam_ip_1 in enumerate(self.camera_ips):
            for cam_indice_2, cam_ip_2 in enumerate(self.camera_ips):
                if cam_indice_1 < cam_indice_2:
                    nb_detection = sum(value for value in self.hdf5_detection.get_detection_dictionnaries(cam_ip_1, cam_ip_2).values())
                    detection_matrix[cam_indice_1, cam_indice_2] = nb_detection
        detection_matrix += detection_matrix.T #fill the lower part of the matrix with the upper part, because the matrix is symetric
        return detection_matrix

    def convert_pickle_to_hdf5(self) -> None: #* TEST RAS
        """Convert the pickle intrinsics file to hdf5"""
        for camera_ip in self.camera_ips:
            pickle_path = os.path.join(self.project_path, self.experiement_name, "calibration", f"{camera_ip}_intrinsics.pickle")
            with open(pickle_path, 'rb') as f:
                data = pickle.load(f)
                print(f"---------------- pickle camip {camera_ip} ----------------")
                intrinsics = data[camera_ip]["mtx"], data[camera_ip]["dist"]
                #intrinsics = ([[902.0, 0.0, 968.4], [0.0, 899.6, 526.0], [0.0, 0.0, 1.0]], [[-0.053, -0.027, -0.0074, 0.0, 0.029]])
                print(f"intrinsics: {intrinsics}")
                self.hdf5_calib.write_intrinsics(camera_ip, intrinsics)


    def extract_calibration_matrix(self)->None:
        """Extract calibration matrix using the detected points in the hdf5 file. Save this to the calibration hdf5 file."""
        calibrated_cams = [] #contain the name of folder who are already calibrated
        # calibrated_cams_indices = [] #contain the indice of the calibrated cameras
        nb_detected_matrix = self.get_detection_matrix() #get the number of detected images in common between the cameras
        #define a reference camera
        ref_cam_indice = np.argmax(np.sum(nb_detected_matrix, axis=1)) #indice of the camera with the most detected images in common with the other cameras
        calibrated_cams.append(self.camera_ips[ref_cam_indice])
        self.hdf5_calib.write_ref(self.camera_ips[ref_cam_indice]) #write the reference camera in the hdf5 file
        R_ref = np.eye(3) #rotation matrix for the reference camera
        T_ref = np.zeros((3, 1)) #translation matrix for the reference camera
        self.hdf5_calib.write_extrinsics_matrix(self.camera_ips[ref_cam_indice], T_ref, R_ref) #write the extrinsics parameters in the hdf5 file
        
        while len(calibrated_cams) != len(self.camera_ips): #while all cameras are not calibrated
            #!----------------------- Find the camera to calibrate -----------------------!#
            #extracte a couple of camera, with one to calibrate and one calibrated
            row_to_keep = [i for i in range(nb_detected_matrix.shape[0]) if self.camera_ips[i] in calibrated_cams] #all ligne of the matrix that are calibrated
            column_to_keep= [j for j in range(nb_detected_matrix.shape[1]) if self.camera_ips[j] not in calibrated_cams] #all column of the matrix that are not calibrated
            sub_matrix = nb_detected_matrix[np.ix_(row_to_keep, column_to_keep)] #

            max_indices_submatrix = np.unravel_index(np.argmax(sub_matrix), sub_matrix.shape)

            #find the selected cameras for the calibration stereo
            calibrated_cam_indice = row_to_keep[max_indices_submatrix[0]]
            cam_to_calibrate_indice = column_to_keep[max_indices_submatrix[1]]


            #!----------------------- Make stereo calibration -----------------------!#
            calibrated_cam = self.camera_ips[calibrated_cam_indice]#now named cam1
            cam_to_calibrate = self.camera_ips[cam_to_calibrate_indice] #now named cam2

            mtx1, dist1 = self.hdf5_calib.read_intrinsics(calibrated_cam) #read the intrinsics parameters for each cameras
            mtx2, dist2 = self.hdf5_calib.read_intrinsics(cam_to_calibrate)

            objp = np.zeros((self.chessboard_size[0] * self.chessboard_size[1], 3), np.float32)
            objp[:, :2] = np.mgrid[0:self.chessboard_size[0], 0:self.chessboard_size[1]].T.reshape(-1, 2)
            objp =  self.square_size * objp

            imgpoints1, imgpoints2 = [], []
            detection_dict = self.hdf5_detection.get_detection_dictionnaries(calibrated_cam, cam_to_calibrate) #get the detected points for the two cameras
            for image in detection_dict.keys():
                if detection_dict[image]: #if the image is detected
                    #gets corners for each cameras
                    corners1 = self.hdf5_detection.read_detections(calibrated_cam, image)
                    corners2 = self.hdf5_detection.read_detections(cam_to_calibrate, image)

                    if corners1.shape[0] == objp.shape[0] and corners2.shape[0] == objp.shape[0]: #if the number of detected points is not the same for the two cameras
                        imgpoints1.append(corners1)
                        imgpoints2.append(corners2)

            objpoints = [objp for _ in range(len(imgpoints1))]

            if not imgpoints1 or not imgpoints2 or not objpoints:
                raise ValueError("imgpoints1, imgpoints2 or objpoints is empty. Did you run perform_detections()?")
            w , h = self.img_size[0], self.img_size[1]

            (
                _,
                _, #equal to mtx1, intrinsic parameters are already known
                _, #equal to dist1
                _, #equal to mtx2
                _, #equal to dist2
                R, #rotation matrix for the couple of cameras 
                T, #translation matrix for the couple of cameras
                _, #essential matrix
                _, #fundamental matrix
            ) = cv2.stereoCalibrate(
                objpoints,
                imgpoints1,
                imgpoints2,
                mtx1,
                dist1,
                mtx2,
                dist2,
                (h, w),
                flags=cv2.CALIB_FIX_INTRINSIC,
            )

            #!----------------------- Use transitivity to find Rref and Tref -----------------------!#
            if calibrated_cam != self.camera_ips[ref_cam_indice]: #if the calibrated camera is the reference camera 

                Rtrans = self.hdf5_calib.read_extrinsics(calibrated_cam)["R"] #use transitivty to find Rref and Tref
                Ttrans = self.hdf5_calib.read_extrinsics(calibrated_cam)["T"]
                Rref = np.dot(Rtrans, R)
                Tref = np.dot(Rtrans, T) + Ttrans

                self.hdf5_calib.write_extrinsics_matrix(cam_to_calibrate, Tref, Rref)
            else:
                self.hdf5_calib.write_extrinsics_matrix(cam_to_calibrate, T, R)

            calibrated_cams.append(cam_to_calibrate)


    def extract_projection_matrix(self):
        """After R and T are found, extract the position of the cameras in the world coordinate system."""
        for cam_ip in self.camera_ips:

            R = self.hdf5_calib.read_extrinsics(cam_ip)["R"]
            Rvec, _ = cv2.Rodrigues(R)
            T = self.hdf5_calib.read_extrinsics(cam_ip)["T"]
            mtx = self.hdf5_calib.read_intrinsics(cam_ip)[0]

            RT = np.hstack([R,T])
            P = np.dot(mtx, RT) #P is the projection matrix calculated using the formula P = K [R|T]
            print(f"----------------- cam_ip : {cam_ip} -----------------")
            print(f"VECTEUR de translation : {T}\n")
            print(f"VECTEUR de rotation : {Rvec}\n")
            #print(f"matrice de projection : {P}\n")
            self.hdf5_calib.write_extrinsics_projection(cam_ip, P)



    #! ----------------------- triangulate 2d points -----------------------!#
    # def triangulate_points_camera_pair(self, cam_ip_1:str, cam_ip_2:str, points_cam_1:np.ndarray, points_cam_2:np.ndarray)->np.ndarray:
    #     """Triangulate corresponding points from two different camera views using stereo calibration parameters and DLT algorithm.
    #     Args:
    #     - cam_ip_1 (str), cam_ip_2 (str): Camera IPs of the pair to use for triangulation.
    #     - points_cam_1 (numpy.ndarray): 2D points from the first camera view. nd.array with shape (n, 2).
    #     - points_cam_2 (numpy.ndarray): 2D points from the second camera view. nd.array with shape (n, 2).
    #     If one camera does not see a point, the value must be set to [np.nan, np.nan].
    #     Returns:
    #     - X (numpy.ndarray): 3D coordinates of the triangulated points. nd.array with shape (n, 3).
    #     """
    #     assert points_cam_1.shape == points_cam_2.shape, "Points must have the same shape"

    #     P1 = self.hdf5_calib.read_extrinsics(cam_ip_1)["P"]
    #     P2 = self.hdf5_calib.read_extrinsics(cam_ip_2)["P"]
    #     points_3D = []

    #     for pt1, pt2 in zip(points_cam_1, points_cam_2):

    #         # ✅ Correction : utiliser np.any(np.isnan(...)) au lieu de "np.nan in"
    #         if not np.any(np.isnan(pt1)) and not np.any(np.isnan(pt2)):

    #             #Construction of the matrix A for DLT
    #             A = np.array([
    #                 pt1[1] * P1[2, :] - P1[1, :],
    #                 P1[0, :] - pt1[0] * P1[2, :],
    #                 pt2[1] * P2[2, :] - P2[1, :],
    #                 P2[0, :] - pt2[0] * P2[2, :]
    #             ])

    #             #Solve the linear system
    #             try:
    #                 _, _, Vh = np.linalg.svd(A)
    #                 h_point = Vh[-1]

    #            # Convert the homogeneous coordinates to cartesian coordinates
    #                 if abs(h_point[3]) > 1e-8:  # Avoid division by zero
    #                     point_3D = h_point[:3] / h_point[3]
    #                     points_3D.append(point_3D)
    #                 else:
    #                     print(f"Warning: Point triangulation failed - homogeneous coordinate too small")
    #                     points_3D.append(np.array([np.nan, np.nan, np.nan]))
    #             except np.linalg.LinAlgError as e:
    #                 print(f"Warning: SVD failed for triangulation: {e}")
    #                 points_3D.append(np.array([np.nan, np.nan, np.nan]))

    #         else:
    #             points_3D.append(np.array([np.nan, np.nan, np.nan]))
    #     return np.array(points_3D)
    
    def triangulate_points_camera_pair(self, cam_ip_1: str, cam_ip_2: str, points_cam_1: np.ndarray, points_cam_2: np.ndarray) -> np.ndarray:
        """
        Triangulate corresponding points from two different camera views using stereo calibration parameters.
        Optimized version using OpenCV's vectorised triangulation.

        Args:
        - cam_ip_1 (str), cam_ip_2 (str): Camera IPs of the pair to use for triangulation.
        - points_cam_1 (numpy.ndarray): 2D points from the first camera view. nd.array with shape (n, 2).
        - points_cam_2 (numpy.ndarray): 2D points from the second camera view. nd.array with shape (n, 2).
        If one camera does not see a point, the value must be set to [np.nan, np.nan].

        Returns:
        - points_3D (numpy.ndarray): 3D coordinates of the triangulated points. nd.array with shape (n, 3).
        """
        assert points_cam_1.shape == points_cam_2.shape, "Points must have the same shape"

        # --- 1. Load Projection Matrices ---
        P1 = self.hdf5_calib.read_extrinsics(cam_ip_1)["P"]
        P2 = self.hdf5_calib.read_extrinsics(cam_ip_2)["P"]

        num_points = points_cam_1.shape[0]
        # Initialize output with NaNs (shape: N x 3)
        points_3D = np.full((num_points, 3), np.nan)

        # --- 2. Filter Valid Points (Masking) ---
        # Create a mask for points that are valid (not NaN) in BOTH cameras
        # axis=1 checks if x OR y is nan in the point [x, y]
        valid_mask = ~np.isnan(points_cam_1).any(axis=1) & ~np.isnan(points_cam_2).any(axis=1)
        
        count_valid_inputs = np.sum(valid_mask)
        
        if count_valid_inputs == 0:
            print(f"[Triangulation Log] {cam_ip_1}-{cam_ip_2}: No common valid points found.")
            return points_3D

        # Extract only valid points and Transpose for OpenCV
        # OpenCV expects shape (2, N) for points (channels first)
        pts1_valid = points_cam_1[valid_mask].T.astype(float)
        pts2_valid = points_cam_2[valid_mask].T.astype(float)

        # --- 3. Vectorized Triangulation (OpenCV) ---
        try:
            # Returns homogeneous coordinates (4, N) -> (x, y, z, w)
            points_4d_hom = cv2.triangulatePoints(P1, P2, pts1_valid, pts2_valid)
            
            # --- 4. Convert Homogeneous to Cartesian ---
            # Extract w (4th component)
            w = points_4d_hom[3, :]
            
            # Define a threshold for points at infinity or unstable triangulation
            w_threshold = 1e-8
            
            # Create a mask for numerically stable points (avoid division by very small numbers)
            stable_mask = np.abs(w) > w_threshold
            
            # Initialize temp storage for valid 3D points
            points_3d_valid = np.full((3, count_valid_inputs), np.nan)
            
            # Perform division only on stable points to get Cartesian (X, Y, Z) = (x/w, y/w, z/w)
            points_3d_valid[:, stable_mask] = points_4d_hom[:3, stable_mask] / w[stable_mask]
            
            # Transpose back to (N, 3) to match output format
            points_3d_valid = points_3d_valid.T
            
            # --- 5. Fill Result Array ---
            # We put the calculated values back into the slots where inputs were valid
            points_3D[valid_mask] = points_3d_valid

            # --- 6. Logging Information ---
            count_success = np.sum(stable_mask)
            count_rejected = count_valid_inputs - count_success
            
            # Uncomment for detailed logging per frame/pair
            # print(f"[Triangulation Log] {cam_ip_1}-{cam_ip_2}: "
            #       f"Inputs={num_points}, Valid pairs={count_valid_inputs}, "
            #       f"Success={count_success}, Rejected(w~0)={count_rejected}")

            if count_rejected > 0:
                 print(f"Warning: {count_rejected} points rejected due to small homogeneous coordinate (rays parallel or divergent).")

        except Exception as e:
            print(f"[Error] Triangulation failed for pair {cam_ip_1}-{cam_ip_2}: {e}")
        
        return points_3D

    def triangulate_points(self, points_cam:Dict[str, np.ndarray])->np.ndarray:
        """Use this function to triangulates points with all the camera pairs in the experiment. with DLT algorithm
        Args :
        - points_cam : a dictionnary with the camera ip as key and the points as value (nd.array with shape (n, 2))
        the key of the dict must be the camera ip. 
        The values are the 2D points of the view of the corresponding camera.
        If the camera dont see the point, the value must be set to [np.nan, np.nan]

        Returns :
        - points_3D : the 3D points, the centers of the cluster defined with the triangulated points of each couple of camera (nd.array with shape (n, 3))"""

        used_camera_ips = list(points_cam.keys())
        cam_pairs = list(combinations(used_camera_ips, 2))
        num_cam_pairs = len(cam_pairs)
        num_points = points_cam[used_camera_ips[0]].shape[0]
        points_3D_per_cams = np.full((num_points, 3, num_cam_pairs), np.nan) #initialize the array with nan values shape (n, 3, num_cam_pairs)

        log_path = r"D:\Users\Etudiant\Desktop\triangulation_debug_log2.txt"
        with open(log_path, "a") as log_file:
            log_file.write(f"\n--------------Frame: {self.frame_counter}--------------\n")
            for cam_pair_index, cam_pair in enumerate(cam_pairs):
                cam_ip_1, cam_ip_2 = cam_pair      # two cameras' ips of a camera pair
                points_cam_1 = points_cam[cam_ip_1]
                points_cam_2 = points_cam[cam_ip_2]
                points_3D = self.triangulate_points_camera_pair(cam_ip_1, cam_ip_2, points_cam_1, points_cam_2)
                points_3D_per_cams[:, :, cam_pair_index] = points_3D  # put all the keypoints' information of one camera setting in the 'cam_pair_index'
                
                # Record all triangulation results for this camera pair
                log_file.write(f"\n--- Camera Pair: ({cam_ip_1}, {cam_ip_2}) ---\n")
                for idx in range(num_points):
                    p = points_3D_per_cams[idx, :, cam_pair_index]
                    valid = not np.any(np.isnan(p))
                    log_file.write(f"Point {idx}: {p.tolist()} {'VALID' if valid else 'INVALID'}\n")
                
        # points_3D_avg = np.nanmedian(points_3D_per_cams, axis=2)  # shape (n, 3)
        points_3D_avg = np.zeros((num_points, 3))

        log_path = r"D:\Users\Etudiant\Desktop\triangulation_debug_log.txt"
        with open(log_path, "a") as log_file:
            log_file.write(f"\n--------------Frame: {self.frame_counter}--------------\n")
            for i in range(num_points):
                point_candidates = points_3D_per_cams[i, :, :]   # for the i'th point, we choose all the information of different camer settings

                log_file.write(f"Point {i}: {point_candidates.shape[1]} valid triangulations\n")
                
                result = np.zeros((3,))  # final x, y, z result

                bin_width = 10  # tolerance precision in millimeters; adjustable depending on the scene

                for dim in range(3):  # process each dimension x, y, z separately
                    dim_values = point_candidates[dim, :]
                    valid = ~np.isnan(dim_values)
                    dim_values = dim_values[valid]

                    if dim_values.shape[0] == 0:
                        result[dim] = np.nan
                        continue
                    # Dynamically adjust bin width: if values are large, increase tolerance
                    if np.nanmax(dim_values) > 1000:
                        bin_width = 80
                    else:
                        bin_width = 10
                    # Bin the values: floor to assign each value to a bin index
                    bins = np.floor(dim_values / bin_width) 
                    unique_bins, counts = np.unique(bins, return_counts=True)

                    # Find the most frequent bin
                    most_common_bin = unique_bins[np.argmax(counts)]
                    most_common_bin_count = counts[np.argmax(counts)] 
                    if(most_common_bin_count > 3):
                        # Extract all values belonging to this bin
                        mask = bins == most_common_bin
                        filtered = dim_values[mask]
                    else:
                        filtered = dim_values
                    # Compute the mean within this bin
                    result[dim] = np.nanmean(filtered)
                    log_file.write(f"  Dim {dim}: values={dim_values}\n")
                    log_file.write(f"  Bins: {bins}\n")
                    log_file.write(f"  Most common bin: {most_common_bin}, values in bin: {filtered}\n")
                    log_file.write(f"  Mean: {np.nanmean(filtered)}, Median: {np.nanmedian(filtered)}\n")

                points_3D_avg[i, :] = result
                log_file.write(f"  Final result: {result}\n\n")

        self.frame_counter += 1
        #find the center of the cluster of the triangulated points
        #return the center of the cluster of the triangulated points of each couple of camera, we have now a np.ndarray with shape (n, 3)
        return points_3D_avg, points_3D_per_cams
    

    def triangulate_points_global(self, points_cam, projection_matrices = None):
        """
        Global triangulation of 3D points from 2D points in multiple cameras  

        Args:
            points_cam: Dict {cam_ip: points_2d} where points_2d is a numpy array of shape (n,2)
            projection_matrices: Dict {cam_ip: P} where P is the projection matrix (3x4)

        Returns:
            points_3D: Numpy array of 3D triangulate points (shape: (n, 3)).
        """
        # ----------------------------------------
        # Auto-load projection matrices if missing
        # ----------------------------------------
        if projection_matrices is None:
            projection_matrices = {}
            for cam_ip in points_cam.keys():
                extr = self.hdf5_calib.read_extrinsics(cam_ip)
                if "P" not in extr:
                    raise ValueError(f"No projection matrix P for camera {cam_ip}")
                projection_matrices[cam_ip] = extr["P"]
                
        cam_ips = list(points_cam.keys())
        num_points = len(points_cam[cam_ips[0]])
        points_3D = np.full((num_points, 3), np.nan)

        # On suppose que projection_matrices est un dict {cam_ip: P}
        P_list = [projection_matrices[cam_ip] for cam_ip in cam_ips]

        for i in range(num_points):
            pts_2d_list = []
            for cam_ip in cam_ips:
                pts_2d = points_cam[cam_ip][i]
                if not np.any(np.isnan(pts_2d)):
                    pts_2d_list.append(pts_2d)
            if len(pts_2d_list) >= 2:
                # Initialisation avec DLT (deux premières caméras)
                pts1, pts2 = pts_2d_list[0], pts_2d_list[1]
                P1, P2 = P_list[0], P_list[1]
                point_3d_homogeneous = cv2.triangulatePoints(P1, P2, pts1.reshape(2,1), pts2.reshape(2,1))
                point_3d = point_3d_homogeneous[:3].flatten() / point_3d_homogeneous[3, 0]
                # def reprojection_error(x):
                #     error = []
                #     X_h = np.append(x, 1)
                #     for P, pts_2d in zip(P_list, pts_2d_list):
                #         proj_h = P @ X_h
                #         proj_2d = proj_h[:2] / proj_h[2]
                #         error.extend(proj_2d - pts_2d)
                #     return np.array(error)
                # result = least_squares(reprojection_error, point_3d, method='lm')
                # points_3D[i, :] = result.x
                point_3d_optimized = optimize_3d_point(P_list, pts_2d_list, point_3d)
                points_3D[i, :] = point_3d_optimized
        return points_3D
    


class ChessboardDetector:
    def __init__(self, chessboard_size, hdf5_detection, tmp_img_folders):
        self.chessboard_size = chessboard_size
        self.hdf5_detection = hdf5_detection
        self.hdf5_lock = threading.Lock()  # Verrou pour sécuriser l'écriture dans HDF5
        self.tmp_img_folders = tmp_img_folders


    def process_image(self, folder_path, filename):
        """Traite une seule image pour détecter un échiquier et stocker les résultats."""
        image_path = os.path.join(folder_path, filename)
        image = cv2.imread(image_path)
        if image is None:
            print(f"Erreur : Impossible de lire l'image {image_path}")
            return

        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        equalized_image = cv2.equalizeHist(gray_image)

        ret, corners = cv2.findChessboardCorners(
            equalized_image, self.chessboard_size,
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        if ret:
            corners_subpixed = cv2.cornerSubPix(
                gray_image, corners, (11, 11), (-1, -1),
                (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            )

            camera_ip = (folder_path.split("/")[-1]).split("_")[0]
            image_id = str(int(re.split(r"[_.]", filename)[-2]))

            # Verrouiller l'accès à HDF5 pour éviter les conflits
            with self.hdf5_lock:
                self.hdf5_detection.write_detections(camera_ip, image_id, corners_subpixed)
        else:
            print(f"Aucun échiquier détecté dans {filename}")

    def perform_detections(self):
        """Effectue la détection en parallèle sur toutes les images."""
        folder_list = self.tmp_img_folders

        with ThreadPoolExecutor() as executor:
            futures = []
            for folder_path in folder_list:
                for filename in os.listdir(folder_path):
                    futures.append(executor.submit(self.process_image, folder_path, filename))

            # Utiliser tqdm pour afficher la progression du traitement
            for _ in tqdm(futures, desc="Traitement des images"):
                _.result()  # S'assurer que toutes les tâches sont terminées
                




if __name__ == "__main__":
    project_path = r"D:\Users\Etudiant\Documents\MoCapIA4\mocapia_3\TestProject7"
    experiment_name = r"MoCap_Demo7"

    #big chessboard
    # chessboard_size = (5, 6)
    # square_size = 120 #mm
    #small chessboard
    chessboard_size = (11, 10)
    square_size = 47 #mm


    extrinsic_calib = ExtrinsicCalib(project_path, experiment_name, chessboard_size, square_size)
    extrinsic_calib.perform_detections(draw_corners=True)
    extrinsic_calib.convert_pickle_to_hdf5()
    extrinsic_calib.extract_calibration_matrix()
    extrinsic_calib.extract_projection_matrix()











