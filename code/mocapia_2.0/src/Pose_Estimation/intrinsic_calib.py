import cv2
import os
import numpy as np
import cv2
import pickle
import subprocess
import re
import os
from Pose_Estimation.video_utils import (
    timecode_to_seconds,
    get_video_timecode,
    get_video_duration
)
from itertools import combinations


"""
an independent program to copy and paste intrinsics parameters for the camera you've chosen
"""

# --- Synchronisation et découpe des vidéos ---
def synchronize_videos(video_paths, save_paths, cam_names):
    assert len(video_paths) == len(save_paths), "Le nombre de vidéos et de fichiers de sortie doit correspondre."

    # Ouverture pour récupérer FPS
    caps = [cv2.VideoCapture(v) for v in video_paths]
    fpss = [cap.get(cv2.CAP_PROP_FPS) for cap in caps]
    fps = fpss[0]

    if fps == 0:
        raise Exception("FPS invalide, vérifiez vos fichiers vidéo.")
    if not all(abs(fps - f) < 0.01 for f in fpss):
        raise Exception("Toutes les vidéos doivent avoir le même FPS.")
    print(f"FPS des vidéos : {fpss}")

    # Calcul des timecodes synchronisés
    timecodes_start = [timecode_to_seconds(get_video_timecode(v), fps) for v in video_paths]
    timecodes_end = [get_video_duration(v) + timecodes_start[i] for i, v in enumerate(video_paths)]

    new_start = max(timecodes_start)
    new_end   = min(timecodes_end)

    start_frame_indices = [int(fps * (new_start - t)) for t in timecodes_start]
    end_frame_indices   = [int(fps * (new_end - t)) for t in timecodes_start]

    # Découpe avec FFmpeg
    for i, v in enumerate(video_paths):
        cam = cam_names[i]
        save_dir = save_paths[i]
        os.makedirs(save_dir, exist_ok=True)
        video_out = os.path.join(save_dir, f"{cam}_synch.mp4")
        frames_dir = os.path.join(save_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        start_time = start_frame_indices[i] / fps
        end_time   = end_frame_indices[i] / fps
        print(f"Découpe {v} de {start_time:.2f}s à {end_time:.2f}s -> {video_out}")

        # Découpe vidéo synchronisée
        command = [
            "ffmpeg", "-y",
            "-i", v,
            "-ss", str(start_time),
            "-to", str(end_time),
            "-c:v", "libx264",
            video_out
        ]
        subprocess.run(command, check=True)

        # Extraction des images
        extract_cmd = [
            "ffmpeg", "-y",
            "-i", video_out,
            os.path.join(frames_dir, f"{cam}_frame_%04d.png")
        ]
        subprocess.run(extract_cmd, check=True)

    print("✅ Synchronisation terminée.")

def intrinsic_calib(chessboard_size, square_size, images_path_dict):
    """
    Calibration of each camera using a folder of chessboard images.
    Args:
        chessboard_size: (cols, rows)
        square_size: size of a square in your defined unit (e.g., millimeters)
        images_path_dict: dictionary with camera names as keys and paths to image folders as values
    Returns
        results: a dictionary of intrinsic parameters.
    """
    results = {}
    objp = np.zeros((chessboard_size[0]*chessboard_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:chessboard_size[0], 0:chessboard_size[1]].T.reshape(-1,2)
    objp *= square_size
    
    for cam_name, folder in images_path_dict.items():
        objpoints = []
        imgpoints = []
        gray_shape = None
        print(f"{cam_name}: {len(objpoints)} images détectées")
        for filename in os.listdir(folder):
            print(f"{cam_name}: found file {filename}")
            img_path = os.path.join(folder, filename)
            img = cv2.imread(img_path)
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            ret, corners = cv2.findChessboardCorners(gray, chessboard_size, None)
            if ret:
                corners_subpix = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1), (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
                objpoints.append(objp)
                imgpoints.append(corners_subpix)
                gray_shape = gray.shape
        print(f"{cam_name}: {len(objpoints)} images used for calibration")
        print(f"objpoints: {objpoints}, imgpoints: {imgpoints}")
        if objpoints and imgpoints and gray_shape:
            ret, mtx, dist, _, _ = cv2.calibrateCamera(objpoints, imgpoints, gray_shape[::-1], None, None)
            results[cam_name] = {"ret": ret, "mtx": mtx, "dist": dist}
        else:
            results[cam_name] = None  # calibration impossible

    return results



if __name__ == "__main__":
    chessboard_size = (6, 5)
    square_size = 120  # mm

    videos = {
        "TSS1": r"D:\Users\Etudiant\Documents\MOCAPIA5\datasets\intrinsic_calib_videos\TSS1\GX010287.MP4",
        "TSS2": r"D:\Users\Etudiant\Documents\MOCAPIA5\datasets\intrinsic_calib_videos\TSS2\GX010318.MP4",
        "TSS3": r"D:\Users\Etudiant\Documents\MOCAPIA5\datasets\intrinsic_calib_videos\TSS3\GX010140.MP4",
        "TSS4": r"D:\Users\Etudiant\Documents\MOCAPIA5\datasets\intrinsic_calib_videos\TSS4\GX010139.MP4"
    }

    images_path = {
        "TSS1": r"D:\Users\Etudiant\Documents\MOCAPIA5\datasets\intrinsic_calib_videos\tmp\TSS1\frames",
        "TSS2": r"D:\Users\Etudiant\Documents\MOCAPIA5\datasets\intrinsic_calib_videos\tmp\TSS2\frames",
        "TSS3": r"D:\Users\Etudiant\Documents\MOCAPIA5\datasets\intrinsic_calib_videos\tmp\TSS3\frames",
        "TSS4": r"D:\Users\Etudiant\Documents\MOCAPIA5\datasets\intrinsic_calib_videos\tmp\TSS4\frames"
    }

    cam_names = ["TSS1", "TSS2", "TSS3", "TSS4"]
    print("Cameras:", cam_names)
    # Synchronisation et découpe des vidéos
    #synchronize_videos(list(videos.values()), list(images_path.values()), cam_names)
    results = intrinsic_calib(chessboard_size, square_size, images_path)
    for cam, res in results.items():
        print(f"--- Camera: {cam} ---")
        if res:
            mtx, dist = res["mtx"], res["dist"]
            print(f"mtx: {mtx}\n, dist: {dist}\n")
        else:
            print(f"Calibration failed for camera {cam}.")

