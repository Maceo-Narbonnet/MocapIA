import cv2
import pickle
import subprocess
import os
import sys
import numpy as np
import h5py
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from itertools import combinations

from Pose_Estimation.video_utils import (
    timecode_to_seconds,
    get_video_timecode,
    get_video_duration
)

# --- Synchronisation et découpe des vidéos ---
def synchronize_videos(video_paths, save_paths):
    assert len(video_paths) == len(save_paths), "Le nombre de vidéos et de fichiers de sortie doit correspondre."

    caps = [cv2.VideoCapture(v) for v in video_paths]
    fpss = [cap.get(cv2.CAP_PROP_FPS) for cap in caps]
    fps = fpss[0]

    if fps == 0:
        raise Exception("FPS invalide, vérifiez vos fichiers vidéo.")
    if not all(abs(fps - f) < 0.01 for f in fpss):
        raise Exception("Toutes les vidéos doivent avoir le même FPS.")
    print(f"FPS des vidéos : {fpss}")

    timecodes_start = [timecode_to_seconds(get_video_timecode(v), fps) for v in video_paths]
    timecodes_end = [get_video_duration(v) + timecodes_start[i] for i, v in enumerate(video_paths)]

    new_start = max(timecodes_start)
    new_end   = min(timecodes_end)

    start_frame_indices = [int(fps * (new_start - t)) for t in timecodes_start]
    end_frame_indices   = [int(fps * (new_end - t)) for t in timecodes_start]

    for i, v in enumerate(video_paths):
        start_time = start_frame_indices[i] / fps
        end_time   = end_frame_indices[i] / fps
        
        if not os.path.exists(save_paths[i]):
            print(f"Découpe {v} de {start_time:.2f}s à {end_time:.2f}s -> {save_paths[i]}")
            command = [
                "ffmpeg", "-y",
                "-i", v,
                "-ss", str(start_time),
                "-to", str(end_time),
                "-c:v", "libx264",
                save_paths[i]
            ]
            subprocess.run(command, check=True)
        else:
            print(f"Vidéo déjà synchronisée trouvée : {save_paths[i]}")

    print("✅ Synchronisation terminée.")


# --- Annotation manuelle ---
def click_points(event, x, y, flags, param):
    points = param
    if event == cv2.EVENT_LBUTTONDOWN:
        if len(points) < 3:
            points.append((x, y))
            print(f"Point ajouté: {(x, y)}")

def annotate_frame(frame, cam_name):
    """Annotation manuelle d'une frame, 3 points obligatoires"""
    points = []
    cv2.setMouseCallback(cam_name, click_points, points)

    while True:
        display = frame.copy()
        cv2.putText(display, "Cliquez 3 points: O, X, Y (dans l'ordre)", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2, cv2.LINE_AA)
        cv2.putText(display, "ESC: annuler", (20, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 1, cv2.LINE_AA)
        for p in points:
            cv2.circle(display, p, 5, (0,0,255), -1)
        for idx, p in enumerate(points):
            cv2.putText(display, str(idx+1), (p[0]+8, p[1]-8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,0), 3, cv2.LINE_AA)
            cv2.putText(display, str(idx+1), (p[0]+8, p[1]-8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1, cv2.LINE_AA)
        cv2.imshow(cam_name, display)
        key = cv2.waitKey(1) & 0xFF

        if len(points) == 3:
            break
        if key == 27:
            points = []
            break
    return points


def annotate_videos(videos, step=20):
    if os.path.exists("annotations.pkl"):
        print("Fichier d'annotations existant trouvé. Chargement...")
        with open("annotations.pkl", "rb") as f:
            saved_data = pickle.load(f)
            if isinstance(saved_data, tuple) and len(saved_data) == 2:
                 return saved_data[0], saved_data[1]
            return saved_data, {} 
            
    caps = {cam: cv2.VideoCapture(path) for cam, path in videos.items()}
    annotations = {}
    referentiel = {}

    total_frames = {cam: int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) for cam, cap in caps.items()}
    min_frames = min(total_frames.values())
    first_cam = list(videos.keys())[0]

    frame_num = 0

    while frame_num < min_frames:
        print(f"\nFrame candidate {frame_num}")

        cap = caps[first_cam]
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        if not ret:
            frame_num += step
            continue

        if frame_num == 0 and not referentiel:
            print("\n*** Sélection des 3 points de la baguette (référentiel) ***")
            for cam in videos.keys():
                cap_cam = caps[cam]
                cap_cam.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame_cam = cap_cam.read()

                if not ret:
                    continue

                cv2.imshow(cam, frame_cam)
                ref_points_cam = annotate_frame(frame_cam, cam)
                referentiel[cam] = ref_points_cam
                cv2.destroyWindow(cam)

            print("Référentiel 3D annoté pour toutes les caméras !")

        cv2.imshow(first_cam, frame)
        points = []
        cv2.setMouseCallback(first_cam, click_points, points)

        while True:
            display = frame.copy()
            for p in points:
                cv2.circle(display, p, 5, (0,0,255), -1)
            cv2.imshow(first_cam, display)
            key = cv2.waitKey(1) & 0xFF

            if len(points) == 3:
                break
            if key == 32: # Space skip
                points = []
                break
            if key == 27: # Esc exit
                frame_num = min_frames
                points = []
                break
        
        cv2.destroyWindow(first_cam)

        if frame_num >= min_frames: break

        if points:
            annotations[frame_num] = {first_cam: points}
            for cam in list(videos.keys())[1:]:
                cap_cam = caps[cam]
                cap_cam.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame_cam = cap_cam.read()
                if not ret:
                    continue
                cv2.imshow(cam, frame_cam)
                points_cam = annotate_frame(frame_cam, cam)
                annotations[frame_num][cam] = points_cam
                cv2.destroyWindow(cam)

        frame_num += step

    cv2.destroyAllWindows()
    with open("annotations.pkl", "wb") as f:
        pickle.dump((annotations, referentiel), f)
    print("Annotations sauvegardées !")
    return annotations, referentiel


# --- Triangulation Locale (Fonctions principales) ---
def triangulate_points_camera_pair(cam_ip_1, cam_ip_2, points_cam_1, points_cam_2, projection_matrices):
    P1 = projection_matrices[cam_ip_1]
    P2 = projection_matrices[cam_ip_2]
    pts1 = points_cam_1.T
    pts2 = points_cam_2.T
    points_3D_h = cv2.triangulatePoints(P1, P2, pts1, pts2)
    points_3D_h /= points_3D_h[3, :]
    return points_3D_h[:3, :].T

def triangulate_points_local(points_cam, projection_matrices):
    """Effectue la triangulation par paires et moyenne les résultats"""
    used_camera_ips = list(points_cam.keys())
    cam_pairs = list(combinations(used_camera_ips, 2))
    points_3D_accum = []

    for cam_pair in cam_pairs:
        cam_ip_1, cam_ip_2 = cam_pair
        pts = triangulate_points_camera_pair(cam_ip_1, cam_ip_2, points_cam[cam_ip_1], points_cam[cam_ip_2], projection_matrices)
        points_3D_accum.append(pts)
    
    # Moyenne des résultats des paires
    if not points_3D_accum:
        return None
    points_3D_avg = np.mean(np.array(points_3D_accum), axis=0)
    return points_3D_avg

# --- Validation ---
def validate_calibration(points_3D: np.ndarray, theoretical_distances: list) -> dict:
    computed_distances = []
    computed_distances.append(np.linalg.norm(points_3D[0] - points_3D[1]))
    computed_distances.append(np.linalg.norm(points_3D[1] - points_3D[2]))
    computed_distances.append(np.linalg.norm(points_3D[2] - points_3D[0]))
    errors = np.abs(np.array(computed_distances) - np.array(theoretical_distances))
    return {
        'computed_distances': computed_distances,
        'theoretical_distances': theoretical_distances,
        'errors': errors,
        'mean_error': np.mean(errors),
        'std_error': np.std(errors)
    }

def load_calibration_params(hdf5_path, camera_name_mapping):
    with h5py.File(hdf5_path, 'r') as f:
        camera_matrices = {}
        dist_coeffs = {}
        rvecs = {}
        tvecs = {}
        projection_matrices = {}

        for code_name, cam_id in camera_name_mapping.items():
            mtx = f[f'intrinsics/{cam_id}/mtx'][()]
            dist = f[f'intrinsics/{cam_id}/dist'][()]
            R = f[f'extrinsics/{cam_id}/R'][()]
            T = f[f'extrinsics/{cam_id}/T'][()]
            P = f[f'extrinsics/{cam_id}/P'][()]
            rvec, _ = cv2.Rodrigues(R)

            camera_matrices[code_name] = mtx
            dist_coeffs[code_name] = dist
            rvecs[code_name] = rvec
            tvecs[code_name] = T
            projection_matrices[code_name] = P
    return camera_matrices, dist_coeffs, rvecs, tvecs, projection_matrices

# --- Visualisation Locale Simplifiée ---
def plot_triangles_local(frames_points, errors, camera_positions=None, rvecs=None, cmap_name='jet', camera_scale=200):
    """Affiche uniquement la triangulation locale"""
    frames_points = [np.asarray(p) for p in frames_points]
    errors = np.asarray(errors)

    valid_errors = [e for e in errors if e != np.inf]
    min_err = np.min(valid_errors) if valid_errors else 0.0
    max_err = np.max(valid_errors) if valid_errors else 10.0
    
    try:
        cmap = plt.colormaps[cmap_name]
    except (KeyError, TypeError):
        cmap = plt.colormaps.get_cmap(cmap_name)

    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')
    label_offset_z = 80
    
    for pts, err in zip(frames_points, errors):
        if err == np.inf:
            continue
        norm_err = np.clip((err - min_err) / (max_err - min_err + 1e-9), 0, 1)
        color = cmap(norm_err)
        
        tri = Poly3DCollection([pts], facecolors=color, edgecolors='k', linewidths=0.5, alpha=0.7)
        ax.add_collection3d(tri)
        
        centroid = np.mean(pts, axis=0)
        text_pos = centroid + np.array([0, 0, label_offset_z])
        ax.plot([centroid[0], text_pos[0]], [centroid[1], text_pos[1]], [centroid[2], text_pos[2]], 
                color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        ax.text(text_pos[0], text_pos[1], text_pos[2], f"{err:.1f}", 
                color='black', fontsize=9, fontweight='bold', ha='center', va='center',
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8))
    
    # Points nuage
    if len(frames_points) > 0:
        valid_pts = [pts for pts, err in zip(frames_points, errors) if err != np.inf]
        if valid_pts:
            all_pts = np.vstack(valid_pts)
            ax.scatter(all_pts[:,0], all_pts[:,1], all_pts[:,2], c='k', s=2, alpha=0.3)
    
    # Caméras
    if camera_positions is not None:
        for cam_name, C in camera_positions.items():
            ax.scatter(*C, c='magenta', s=60, marker='^', edgecolors='black')
            ax.text(C[0], C[1], C[2] + 50, cam_name, color='magenta', fontsize=8, fontweight='bold')
            if rvecs is not None and cam_name in rvecs:
                R, _ = cv2.Rodrigues(rvecs[cam_name])
                colors = ['r', 'g', 'b']
                for i in range(3):
                    start = C
                    end = C + R[:, i] * (camera_scale * 0.5)
                    ax.plot([start[0], end[0]], [start[1], end[1]], [start[2], end[2]], c=colors[i], linewidth=1.5)
    
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_zlabel("Z (mm)")
    ax.set_title("TRIANGULATION LOCALE", fontsize=14, fontweight='bold', color='darkred')
    ax.view_init(elev=25, azim=-50)
    
    mappable = plt.cm.ScalarMappable(cmap=cmap)
    mappable.set_array([min_err, max_err])
    cbar = fig.colorbar(mappable, ax=ax, pad=0.05, shrink=0.6)
    cbar.set_label("Erreur moyenne (mm)")
    
    plt.show()

def compute_reorientation_matrix(O, Xp, Yp):
    """Construit une matrice de réorientation orthonormée."""
    O = np.asarray(O).reshape(3,)
    Xp = np.asarray(Xp).reshape(3,)
    Yp = np.asarray(Yp).reshape(3,)
    
    x_raw = Xp - O
    y_raw = Yp - O
    
    x_axis = x_raw / np.linalg.norm(x_raw)
    z_axis = np.cross(x_axis, y_raw)
    z_axis = z_axis / np.linalg.norm(z_axis)
    y_axis = np.cross(z_axis, x_axis)
    y_axis = y_axis / np.linalg.norm(y_axis)
    
    R = np.column_stack((x_axis, y_axis, z_axis))
    return R, O

def reorient_points(points, R, O):
    points = np.asarray(points)
    if points.ndim == 1:
        points = points.reshape(1, 3)
    return (R.T @ (points - O).T).T

# --- Main ---
if __name__ == "__main__":
    # 1. Configuration
    videos = {
        "TSS1": r"D:\Users\Etudiant\Documents\MOCAPIA5\datasets\Homogeinite_calib3\TSS1\wandTSS1.MP4",
        "TSS2": r"D:\Users\Etudiant\Documents\MOCAPIA5\datasets\Homogeinite_calib3\TSS2\wandTSS2.MP4",
        "TSS3": r"D:\Users\Etudiant\Documents\MOCAPIA5\datasets\Homogeinite_calib3\TSS3\wandTSS3.MP4",
        "TSS4": r"D:\Users\Etudiant\Documents\MOCAPIA5\datasets\Homogeinite_calib3\TSS4\wandTSS4.MP4"
    }

    camera_name_mapping = {
        "TSS1": "C3501350052453",
        "TSS2": "C3501325621627",
        "TSS3": "C3501325588979",
        "TSS4": "C3501325623877"
    }

    # 2. Synchronisation
    output_dir = r"D:\Users\Etudiant\Documents\MOCAPIA5\datasets\Wandtest"
    os.makedirs(output_dir, exist_ok=True)
    save_paths = [os.path.join(output_dir, f"{cam}_synch.mp4") for cam in videos.keys()]
    synchronize_videos(list(videos.values()), save_paths)
    videos_synch = {cam: save for cam, save in zip(videos.keys(), save_paths)}

    # 3. Annotation
    step_input = input("Afficher une frame sur combien ? (ex: 20) [Entrée = 20]: ")
    step = int(step_input) if step_input.isdigit() else 20
    annotations, referentiel = annotate_videos(videos_synch, step)

    if not annotations:
        print("Aucune annotation, arrêt du script.")
        sys.exit()

    # 4. Chargement Calibration
    hdf5_path = r"D:\Users\Etudiant\Documents\MOCAPIA5\mocapia_3\WandTest\wandtest1\calibration\wandtest1_calibration_param.hdf5"
    camera_matrices, dist_coeffs, rvecs, tvecs, projection_matrices = load_calibration_params(hdf5_path, camera_name_mapping)

    # 5. Définition du repère via la frame 0
    if not referentiel:
        print("Attention: Pas de référentiel. Utilisation du repère monde par défaut.")
        R_ref, O_ref = np.eye(3), np.zeros(3)
    else:
        ref_points_cam = {cam: np.array(referentiel[cam], dtype=np.float32) for cam in referentiel}
        # Triangulation locale pour le référentiel
        ref_points3D = triangulate_points_local(ref_points_cam, projection_matrices)
        O_ref, Xp, Yp = ref_points3D[0], ref_points3D[1], ref_points3D[2]
        R_ref, O_ref = compute_reorientation_matrix(O_ref, Xp, Yp)
        print(f"✅ Matrice de réorientation calculée. det(R)={np.linalg.det(R_ref):.6f}")

    # 6. Triangulation et Validation (LOCAL UNIQUEMENT)
    theoretical_distances = [250, 243, 290] # mm
    all_points = []
    all_errors = []

    print("\n--- Validation (Triangulation Locale Uniquement) ---")
    print(f"{'Frame':<8} {'Erreur Moyenne (mm)':<20}")
    print("-" * 40)
    
    for frame_num in sorted(annotations.keys()):
        points_cam_arr = {cam: np.array(pts, dtype=np.float32) for cam, pts in annotations[frame_num].items()}
        
        # Triangulation Locale
        try:
            points_3D = triangulate_points_local(points_cam_arr, projection_matrices)
        except Exception as e:
            print(f"Erreur frame {frame_num}: {e}")
            points_3D = None
        
        if points_3D is not None:
            points_3D_reorient = reorient_points(points_3D, R_ref, O_ref)
            res = validate_calibration(points_3D_reorient, theoretical_distances)
            err = res['mean_error']
            all_points.append(points_3D_reorient)
            all_errors.append(err)
        else:
            err = np.inf
            all_errors.append(err)
        
        print(f"{frame_num:<8} {err:<20.2f}")
    
    print("-" * 40)
    mean_error = np.mean([e for e in all_errors if e != np.inf])
    print(f"Moyenne Globale des erreurs (Local): {mean_error:.2f} mm")

    # 7. Affichage Final
    print("\nAffichage Triangulation Locale...")
    
    # Calcul position caméras
    camera_positions = {}
    for cam_name, rvec in rvecs.items():
        R_cam, _ = cv2.Rodrigues(rvec)
        t_cam = tvecs[cam_name].reshape(3,1)
        C_world = -R_cam.T @ t_cam
        C_new = reorient_points(C_world.T, R_ref, O_ref).T.reshape(3)
        camera_positions[cam_name] = C_new

    plot_triangles_local(all_points, all_errors, camera_positions=camera_positions, rvecs=rvecs)