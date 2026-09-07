"""This file contains utility functions for video processing."""
import ffmpeg
import re
import cv2
import json
from typing import List, Dict
import os, time

def extract_images_from_video(video_path:str, save_path:str,number:int =200, image_format:str = "jpg", progress_cb=None, clear_existing: bool = False) -> None:
    """Open the video at the specified path and extract a number of frames with equal intervals.
    If the save_path directory does not exist, it will be created.
    Args :
        video_path : Path to the video file.
        save_path : Path to the directory where the extracted images will be saved.
        number : Number of images to extract.
        format : Image format to save. (jgp, png, """

    assert number > 0, "Number of frames must be greater than 0."
    assert isinstance(number, int), "Number of frames must be an integer."
    assert image_format == "jpg" or image_format == "png", "Image format must be 'jpg' or 'png'."
    assert isinstance(video_path, str), "Video path must be a string."
    assert isinstance(save_path, str), "Save path must be a string."

    if not os.path.exists(save_path):
        os.makedirs(save_path)
        
    if clear_existing:
        for fn in os.listdir(save_path):
            if fn.lower().endswith(("." + image_format).lower()):
                try:
                    os.remove(os.path.join(save_path, fn))
                except Exception:
                    pass

    # Open the video file
    video_capture = cv2.VideoCapture(video_path)

    # Check if video opened successfully
    if not video_capture.isOpened():
        raise Exception(f"Could not open video at {video_path}")

    # Get the total number of frames in the video
    total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))

    # Calculate the interval at which frames will be extracted
    interval = max(1, total_frames // number)

    frame_count = 0
    extracted_count = 0
    total = int(number)

    while True:
        success, frame = video_capture.read()
        if not success:
            break

        # Extract frames at the calculated interval
        if frame_count % interval == 0 and extracted_count < number:
            # Generate file name for the extracted image
            image_file = os.path.join(save_path, f"frame_{extracted_count:04d}.{image_format}")
            # Save the extracted frame as an image
            cv2.imwrite(image_file, frame)
            extracted_count += 1
            if callable(progress_cb):
                try:
                    progress_cb(extracted_count, total)
                except Exception:
                    pass

        frame_count += 1

        # Stop once we've extracted the required number of frames
        if extracted_count >= number:
            break

    # Release the video capture object
    video_capture.release()
    print(f"Extracted {extracted_count} frames and saved them to {save_path}")


def clear_folder(folder_path: str, format: str = None,
                 remove_dir_if_empty: bool = False,
                 retries: int = 1, retry_delay: float = 0.2) -> None:
    """Delete files in the folder (optionally by extension). Optionally remove the directory if it's empty."""
    assert isinstance(folder_path, str), "Folder path must be a string."
    if not os.path.exists(folder_path):
        # Keep the same logic as the original version; could also return silently instead
        raise Exception(f"Folder does not exist at {folder_path}")

    last_err = None
    for _ in range(max(1, retries)):
        try:
            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                if os.path.isfile(file_path):
                    if format:
                        if file.lower().endswith(format.lower()):
                            os.remove(file_path)
                    else:
                        os.remove(file_path)
            if remove_dir_if_empty:
                try:
                    os.rmdir(folder_path)  # only if empty
                except OSError:
                    pass
            print(
                f"Deleted files in {folder_path} with format '{format}'"
                if format else f"Deleted all files in {folder_path}"
            )
            return
        except Exception as e:
            last_err = e
            time.sleep(retry_delay)
    # If the number of retries is exceeded and it still fails: raise the last error (or choose to fail silently)
    if last_err:
        raise last_err



def get_video_timecode(video_path:str) -> dict:
    """Get the timecode in format HH:MM:SS:FF from the video file.
    Args:
        video_path : Path to the video file.
    Returns:
        Dictionary containing metadata information."""

    probe = ffmpeg.probe(video_path)
    return probe["streams"][0]["tags"]["timecode"]

def get_video_duration(video_path:str) -> float:
    """get the duration of a video in seconds using ffmpeg."""
    probe = ffmpeg.probe(video_path)
    return float(probe["streams"][0]["duration"])

def timecode_to_seconds(timecode:str, framerate:float)->float:
    """Convert a timecode in format HH:MM:SS:FF to seconds.
    Args:
        timecode : Timecode in format HH:MM:SS:FF.
    Returns:
        Time in seconds."""
    timecode = re.split(r'[:;]', timecode) # Split the timecode string into hours, minutes, seconds, and frames
    hours = int(timecode[0])
    minutes = int(timecode[1])
    seconds = int(timecode[2])
    frames = int(timecode[3])
    return hours*3600 + minutes*60 + seconds + frames/framerate



#! slower way to synchronize videos
# def synchronize_videos(video_paths: List[str], save_paths: List[str]) -> None:
#     """Synchronize video frame by frame using the timecodes metadata."""
#     assert len(video_paths) == len(save_paths), "The number of video paths must be equal to the number of save paths."

#     caps = [cv2.VideoCapture(video_path) for video_path in video_paths]
#     fpss = [cap.get(cv2.CAP_PROP_FPS) for cap in caps]

#     fps = fpss[0]
#     print(fpss)
#     if not all(fpss[0] == fpss[i] for i in range(1, len(fpss))):
#         raise Exception("All videos must have the same framerate.")

#     # Useful values for synchronization
#     timecodes_start = [timecode_to_seconds(get_video_timecode(video_path), fps) for video_path in video_paths]
#     timecodes_end = [get_video_duration(video_path) + timecodes_start[i] for i, video_path in enumerate(video_paths)]
#     new_start = max(timecodes_start)
#     new_end = min(timecodes_end)
#     start_frame_indices = [int(fps * (new_start - timecode)) for timecode in timecodes_start]
#     end_frame_indices = [int(fps * (new_end - timecode)) for timecode in timecodes_start]

#     # Verify that all videos have the same number of frames (same duration)
#     frame_diffs = [end_frame_indices[i] - start_frame_indices[i] for i in range(len(video_paths))]

#     # Execute `cut_video` in parallel using ThreadPoolExecutor
#     with ThreadPoolExecutor(max_workers=len(video_paths)) as executor:
#         futures = [
#             executor.submit(cut_video, video_paths[i], save_paths[i], start_frame_indices[i], end_frame_indices[i])
#             for i in range(len(video_paths))
#         ]

#         # Optionally, wait for all tasks to complete
#         for future in tqdm(futures, desc="Synchronizing videos"):
#             future.result()  # Ensure exceptions are raised if any occur in the threads

# def cut_video(video_path, save_path, fps_indice_start, fps_indice_end):
#     """Cut the video at the specified path and save the frames between the specified indices."""
#     cap = cv2.VideoCapture(video_path)
#     if not cap.isOpened():
#         raise Exception(f"Could not open video at {video_path}")

#     # Useful parameters of the video
#     fps = cap.get(cv2.CAP_PROP_FPS)
#     width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#     height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#     fourcc = cv2.VideoWriter_fourcc(*'mp4v')

#     # Create the video writer object
#     out = cv2.VideoWriter(save_path, fourcc, fps, (width, height))

#     # Loop through the video frames and write the frames in the specified interval
#     frame_idx = 0
#     with tqdm(total=fps_indice_end - fps_indice_start, desc=f"Building video: {video_path}") as pbar:
#         while True:
#             ret, frame = cap.read()
#             if not ret:
#                 break  # End of the video

#             # Keep only the frames in the specified interval
#             if fps_indice_start <= frame_idx < fps_indice_end:
#                 out.write(frame)
#             frame_idx += 1
#             pbar.update(1)

#             # Stop the loop when we reach the end frame index
#             if frame_idx >= fps_indice_end:
#                 break

#     # Release the video capture and writer objects
#     cap.release()
#     out.release()


# *Old version, using Matplotlib for point selection, would conflict with the UI interface.
# def get_points_from_image(image_path, num_points=3):
#     """
#     Affiche une image, permet de cliquer sur 'num_points' points, 
#     et renvoie les coordonnées 2D en pixels de ces points.

#     :param image_path: Chemin vers l'image à afficher.
#     :param num_points: Nombre de points à cliquer (par défaut: 3).
#     :return: Liste des coordonnées des points cliqués sous la forme [(x1, y1), (x2, y2), ...]
#     """
#     # Charger l'image
#     img = mpimg.imread(image_path)

#     # Afficher l'image
#     fig, ax = plt.subplots()
#     ax.imshow(img)
#     ax.set_title(f"Cliquez sur {num_points} points")

#     # Demander à l'utilisateur de cliquer sur les points
#     points = plt.ginput(num_points)  # Capture les coordonnées des clics

#     # Fermer la fenêtre après avoir capturé les points
#     plt.close()

#     # Retourner les coordonnées des points cliqués
#     return points

def get_points_from_image(image_path: str, num_points: int = 3):
    """
    OpenCV point picker:
    - Left click to select points in order
    - ESC or closing the window = cancel (return an empty list)
    - 'u' or Backspace = undo last point
    - 'r' = reset all points
    - Enter = finish early if num_points is already reached
    """
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    base = img  # Keep a clean copy of the original image for redrawing
    disp = base.copy()
    h, w = disp.shape[:2]
    win = f"Cliquez sur {num_points} points"

    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, min(1920, w), min(1080, h))
    try:
        cv2.setWindowProperty(win, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass

    points = []

    def redraw():
        """Redraw the overlay according to the current list of selected points"""
        nonlocal disp
        disp = base.copy()
        for i, (x, y) in enumerate(points):
            cv2.circle(disp, (int(x), int(y)), 5, (255, 255, 255), -1)  # Draw small white circles
            cv2.putText(
                disp, str(i + 1), (int(x) + 6, int(y) - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA
            )
        cv2.imshow(win, disp)

    def _on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < num_points:
            points.append((float(x), float(y)))
            redraw()

    cv2.setMouseCallback(win, _on_mouse)
    cv2.imshow(win, disp)

    # Event loop: exits when enough points are picked, the user cancels, or the window is closed
    while True:
        # If the user clicks the "X" to close the window, treat it as a cancel action
        try:
            vis = cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE)
            if vis < 1:
                points = []
                break
        except cv2.error:
            # On some platforms closing the window raises cv2.error; treat this the same way
            points = []
            break

        key = cv2.waitKey(20) & 0xFFFF
        if key == 27:            # ESC → cancel
            points = []
            break
        elif key in (8, 127) or key == ord('u'):  # Backspace/Delete/u → undo last point
            if points:
                points.pop()
                redraw()
        elif key == ord('r'):    # r → reset all points
            points.clear()
            redraw()
        elif key in (10, 13):    # Enter/Return
            if len(points) >= num_points:
                break

        if len(points) >= num_points:
            break

    # Close the window and flush the event queue to avoid hanging
    try:
        cv2.destroyWindow(win)
        cv2.waitKey(1)
    except Exception:
        pass

    return points


class UserCancelled(Exception):
    """The user closed the picker window or pressed ESC."""
    pass


def pick_points_for_cameras(camera_image_map: dict, num_points: int = 3) -> dict:
    """
    Pick points on each camera image in sequence. 
    If the user cancels on any camera (by pressing ESC or closing the window), 
    a UserCancelled exception is raised.
    """
    result = {}
    for cam_id, img_path in camera_image_map.items():
        print(f"[pick] {cam_id} -> {img_path}")
        pts = get_points_from_image(img_path, num_points=num_points)

        # User cancelled: returns an empty list; we raise a lightweight exception to propagate it
        if not pts or len(pts) < num_points:
            raise UserCancelled(f"cancelled on {cam_id}")

        # Normal case: ensure coordinates are floats, and keep the order O, X, Y
        result[cam_id] = [[float(x), float(y)] for (x, y) in pts]
    return result



def save_change_ref_points(project_path: str, experiment_name: str, cam_points_dict: dict,
                           filename: str = "change_ref_points.json") -> str:
    """
    Save the per-camera 2D coordinates of the three points to <project>/<experiment>/calibration/change_ref_points.json
    """
    calib_dir = os.path.join(project_path, experiment_name, "calibration")
    os.makedirs(calib_dir, exist_ok=True)
    outpath = os.path.join(calib_dir, filename)
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(cam_points_dict, f, ensure_ascii=False, indent=2)
    print(f"[save] change-ref points -> {outpath}")
    return outpath

_NAME_NUM_RE = re.compile(r'(\d+)$') # Parse the number at the end of the name: for example, "Hero12_3" → 3.


# Match patterns in the path such as "TSS_1", "TSS-2", "TSS 3", etc.
_TSS_IN_PATH_RE = re.compile(r"TSS[_\-\s]?(\d+)", re.IGNORECASE)
_IP_RE = re.compile(r"C\d{6,}", re.IGNORECASE)  # e.g. C3501350052453

def _load_name_to_ip(project_path: str, experiment_name: str) -> Dict[str, str]:
    """Reads the <project>/<experiment>/config.json file’s camera_setup section and returns a mapping {name -> ip}."""
    cfg = os.path.join(project_path, experiment_name, "config.json")
    if not os.path.isfile(cfg):
        return {}
    with open(cfg, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    out = {}
    for c in data.get("camera_setup", []):
        name = (c.get("name") or "").strip()
        ip   = (c.get("ip")   or "").strip()
        if name and ip:
            out[name] = ip
    return out


def _guess_name_from_path(path: str, candidate_names: List[str]) -> str:
    """If the path contains one of the candidate camera names, return that name;
    if multiple names match, the longest name takes precedence."""
    p = path.lower().replace("\\", "/")
    for name in sorted(candidate_names, key=len, reverse=True):
        if name.lower() in p:
            return name
    return ""


def build_camera_image_map_from_videos_using_config(
    video_paths: List[str],
    project_path: str,
    experiment_name: str,
    out_base_dir: str,
) -> Dict[str, str]:
    """
    Match video files to cameras based on the following priority:
      1) If the file name/path contains the camera IP (e.g. C3501...), use it directly.
      2) If the path contains the camera name (e.g. Hero12_1), 
         use the name→IP mapping from config.json.
      3) If neither is found, fall back to pairing in the order of 
         video_paths and the camera order in config.json.
         
    Then extract 1 frame (frame_index) from each video and save it to:
        out_base_dir/<ip>/frame_0000.jpg

    Returns a mapping {ip: jpg_path}.
    """
    name2ip = _load_name_to_ip(project_path, experiment_name)
    cam_names = list(name2ip.keys())
    cam_ips_in_order = [name2ip[n] for n in cam_names]

    pairs: List[tuple] = []         # (ip, video_path)
    used_ips = set()

    # ① First, check whether the file name/path directly contains the IP
    for vp in video_paths:
        m = _IP_RE.search(os.path.basename(vp))
        m = m or _IP_RE.search(vp)
        if m:
            ip = m.group(0)
            if ip in cam_ips_in_order and ip not in used_ips:
                pairs.append((ip, vp))
                used_ips.add(ip)

    # ② Then, try matching using the name→IP mapping (Hero12_#)
    used_videos = {p for _, p in pairs}
    for vp in video_paths:
        if vp in used_videos:
            continue
        name = _guess_name_from_path(vp, cam_names)
        if name:
            ip = name2ip.get(name)
            if ip and ip not in used_ips:
                pairs.append((ip, vp))
                used_ips.add(ip)
                used_videos.add(vp)

    # ③ Fallback: match remaining videos and IPs in their original order
    remaining_videos = [vp for vp in video_paths if vp not in used_videos]
    remaining_ips = [ip for ip in cam_ips_in_order if ip not in used_ips]
    for vp, ip in zip(remaining_videos, remaining_ips):
        pairs.append((ip, vp))
        used_ips.add(ip)

    # ④ Extract the first frame and save it to out_base_dir/<ip>/frame_0000.jpg
    cam_map: Dict[str, str] = {}
    for ip, vp in pairs:
        out_dir = os.path.join(out_base_dir, ip)
        os.makedirs(out_dir, exist_ok=True)
        extract_images_from_video(
            video_path=vp,
            save_path=out_dir,
            number=1,
            image_format="jpg",
            clear_existing=True  # Clean up old frames to avoid multiple images in the folder
        )
        # Since number=1, the output file will be named frame_0000.jpg
        cam_map[ip] = os.path.join(out_dir, "frame_0000.jpg")

    return cam_map


if __name__ == "__main__":
    
    # demo: 
    video_paths = [
        r"D:\Users\Etudiant\Desktop\MoCap_Demo dossier\MoCap_Demo7\TSS2\GX010290.mp4",
        r"D:\Users\Etudiant\Desktop\MoCap_Demo dossier\MoCap_Demo7\TSS3\GX010115.mp4",
        r"D:\Users\Etudiant\Desktop\MoCap_Demo dossier\MoCap_Demo7\TSS4\GX010113.mp4"
    ]
    project_path = r"D:\Users\Etudiant\Documents\MoCapIA5\mocapia_3\TestProject11"
    experiment_name = r"MoCap_Demo2"
    out_base_dir = os.path.join(project_path, experiment_name, "change_ref")

    camera_image_map = build_camera_image_map_from_videos_using_config(
        video_paths, project_path, experiment_name, out_base_dir
    )
    cam_points = pick_points_for_cameras(camera_image_map, num_points=3)
    
    json_path = save_change_ref_points(project_path, experiment_name, cam_points)