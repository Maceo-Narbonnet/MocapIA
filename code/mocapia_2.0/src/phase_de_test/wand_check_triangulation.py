import cv2
import pickle
import subprocess
import re
import os
import sys
import numpy as np
import h5py
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from itertools import combinations

# Assurez-vous que ces imports fonctionnent dans votre environnement local
from phase_de_test.Global_triangulation_test import triangulate_points_global
from Pose_Estimation.video_utils import (
    timecode_to_seconds,
    get_video_timecode,
    get_video_duration
)

# --- Synchronisation et découpe des vidéos ---
def synchronize_videos(video_paths, save_paths):
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
        start_time = start_frame_indices[i] / fps
        end_time   = end_frame_indices[i] / fps
        
        # On ne lance ffmpeg que si le fichier n'existe pas déjà pour gagner du temps
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
        # Instruction overlay: ordre des points
        cv2.putText(display, "Cliquez 3 points: O, X, Y (dans l'ordre)", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2, cv2.LINE_AA)
        cv2.putText(display, "ESC: annuler", (20, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 1, cv2.LINE_AA)
        for p in points:
            cv2.circle(display, p, 5, (0,0,255), -1)
        # Numérotation des points cliqués pour maintenir la correspondance entre caméras
        for idx, p in enumerate(points):
            cv2.putText(display, str(idx+1), (p[0]+8, p[1]-8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,0), 3, cv2.LINE_AA)
            cv2.putText(display, str(idx+1), (p[0]+8, p[1]-8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1, cv2.LINE_AA)
        cv2.imshow(cam_name, display)
        key = cv2.waitKey(1) & 0xFF

        if len(points) == 3:  # 3 points cliqués
            break
        if key == 27:  # ESC pour abandonner
            points = []
            break
    return points


def annotate_videos(videos, step=20):
    """Annotation synchronisée sur plusieurs caméras"""
    # Vérifier si on a déjà des annotations sauvegardées pour ne pas tout refaire
    if os.path.exists("annotations.pkl"):
        print("Fichier d'annotations existant trouvé. Chargement...")
        with open("annotations.pkl", "rb") as f:
            saved_data = pickle.load(f)
            # Si le pickle contient un tuple (annotations, referentiel), on dépack
            if isinstance(saved_data, tuple) and len(saved_data) == 2:
                 return saved_data[0], saved_data[1]
            return saved_data, {} # Cas legacy
            
    caps = {cam: cv2.VideoCapture(path) for cam, path in videos.items()}
    annotations = {}
    referentiel = {}

    total_frames = {cam: int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) for cam, cap in caps.items()}
    min_frames = min(total_frames.values())
    first_cam = list(videos.keys())[0]

    frame_num = 0

    while frame_num < min_frames:
        print(f"\nFrame candidate {frame_num}")

        # --- Première caméra ---
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
                    print(f"Impossible de lire frame {frame_num} de {cam}")
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
            if key == 32:  # espace = skip frame
                points = []
                break
            if key == 27: # Esc = fin annotation
                frame_num = min_frames # Force exit loop
                points = []
                break
        
        cv2.destroyWindow(first_cam)

        if frame_num >= min_frames: break

        # --- Annoter les autres caméras sur la même frame ---
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
    # Sauvegarde tuple pour garder referentiel
    with open("annotations.pkl", "wb") as f:
        pickle.dump((annotations, referentiel), f)
    print("Annotations sauvegardées !")
    return annotations, referentiel


# --- Triangulation (Local fallback implementation) ---
def triangulate_points_camera_pair(cam_ip_1, cam_ip_2, points_cam_1, points_cam_2, projection_matrices):
    P1 = projection_matrices[cam_ip_1]
    P2 = projection_matrices[cam_ip_2]
    pts1 = points_cam_1.T
    pts2 = points_cam_2.T
    points_3D_h = cv2.triangulatePoints(P1, P2, pts1, pts2)
    points_3D_h /= points_3D_h[3, :]
    return points_3D_h[:3, :].T

def triangulate_points(points_cam, projection_matrices):
    # Note: Ceci est une version simplifiée de ta fonction complexe avec logs
    # Elle sert de fallback si triangulate_points_global échoue ou pour le référentiel
    used_camera_ips = list(points_cam.keys())
    cam_pairs = list(combinations(used_camera_ips, 2))
    num_points = points_cam[used_camera_ips[0]].shape[0]
    points_3D_accum = []

    for cam_pair in cam_pairs:
        cam_ip_1, cam_ip_2 = cam_pair
        pts = triangulate_points_camera_pair(cam_ip_1, cam_ip_2, points_cam[cam_ip_1], points_cam[cam_ip_2], projection_matrices)
        points_3D_accum.append(pts)
    
    # Moyenne simple des paires (tu as un algo plus complexe de binning dans ton code original)
    points_3D_avg = np.mean(np.array(points_3D_accum), axis=0)
    return points_3D_avg, None

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

# --- Visualisation Comparaison (Global vs Local) ---
def plot_triangles_comparison(frames_points_global, errors_global, frames_points_local, errors_local, 
                              camera_positions=None, rvecs=None, cmap_name='jet', min_err=None, max_err=None, camera_scale=200):
    """
    Affiche les deux triangulations côte à côte : GLOBAL (gauche) et LOCAL (droite)
    camera_positions: Dict {cam_name: [x, y, z]} - positions réelles des caméras (déjà transformées)
    """
    frames_points_global = [np.asarray(p) for p in frames_points_global]
    frames_points_local = [np.asarray(p) for p in frames_points_local]
    errors_global = np.asarray(errors_global)
    errors_local = np.asarray(errors_local)

    # Déterminer les limites d'erreur globales
    valid_errors_global = [e for e in errors_global if e != np.inf]
    valid_errors_local = [e for e in errors_local if e != np.inf]
    
    if min_err is None: 
        min_err = min(np.min(valid_errors_global) if valid_errors_global else 0.0,
                      np.min(valid_errors_local) if valid_errors_local else 0.0)
    if max_err is None: 
        max_err = max(np.max(valid_errors_global) if valid_errors_global else 10.0,
                      np.max(valid_errors_local) if valid_errors_local else 10.0)
    
    try:
        cmap = plt.colormaps[cmap_name]
    except (KeyError, TypeError):
        cmap = plt.colormaps.get_cmap(cmap_name)

    fig = plt.figure(figsize=(20, 10))
    
    # --- SUBPLOT 1 : TRIANGULATION GLOBALE ---
    ax1 = fig.add_subplot(121, projection='3d')
    label_offset_z = 80
    
    for pts, err in zip(frames_points_global, errors_global):
        if err == np.inf:
            continue
        norm_err = np.clip((err - min_err) / (max_err - min_err + 1e-9), 0, 1)
        color = cmap(norm_err)
        
        tri = Poly3DCollection([pts], facecolors=color, edgecolors='k', linewidths=0.5, alpha=0.7)
        ax1.add_collection3d(tri)
        
        centroid = np.mean(pts, axis=0)
        text_pos = centroid + np.array([0, 0, label_offset_z])
        ax1.plot([centroid[0], text_pos[0]], [centroid[1], text_pos[1]], [centroid[2], text_pos[2]], 
                color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        ax1.text(text_pos[0], text_pos[1], text_pos[2], f"{err:.1f}", 
                color='black', fontsize=9, fontweight='bold', ha='center', va='center',
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8))
    
    if len(frames_points_global) > 0:
        valid_pts = [pts for pts, err in zip(frames_points_global, errors_global) if err != np.inf]
        if valid_pts:
            all_pts = np.vstack(valid_pts)
            ax1.scatter(all_pts[:,0], all_pts[:,1], all_pts[:,2], c='k', s=2, alpha=0.3)
    
    # Ajouter les caméras
    if camera_positions is not None:
        for cam_name, C in camera_positions.items():
            ax1.scatter(*C, c='magenta', s=60, marker='^', edgecolors='black')
            ax1.text(C[0], C[1], C[2] + 50, cam_name, color='magenta', fontsize=8, fontweight='bold')
            # Optionnel : ajouter les axes locaux si rvecs fourni
            if rvecs is not None and cam_name in rvecs:
                R, _ = cv2.Rodrigues(rvecs[cam_name])
                colors = ['r', 'g', 'b']
                for i in range(3):
                    start = C
                    end = C + R[:, i] * (camera_scale * 0.5)
                    ax1.plot([start[0], end[0]], [start[1], end[1]], [start[2], end[2]], 
                            c=colors[i], linewidth=1.5)
    
    ax1.set_xlabel("X (mm)")
    ax1.set_ylabel("Y (mm)")
    ax1.set_zlabel("Z (mm)")
    ax1.set_title("TRIANGULATION GLOBALE", fontsize=12, fontweight='bold', color='darkblue')
    ax1.view_init(elev=25, azim=-50)
    
    # --- SUBPLOT 2 : TRIANGULATION LOCALE ---
    ax2 = fig.add_subplot(122, projection='3d')
    
    for pts, err in zip(frames_points_local, errors_local):
        if err == np.inf:
            continue
        norm_err = np.clip((err - min_err) / (max_err - min_err + 1e-9), 0, 1)
        color = cmap(norm_err)
        
        tri = Poly3DCollection([pts], facecolors=color, edgecolors='k', linewidths=0.5, alpha=0.7)
        ax2.add_collection3d(tri)
        
        centroid = np.mean(pts, axis=0)
        text_pos = centroid + np.array([0, 0, label_offset_z])
        ax2.plot([centroid[0], text_pos[0]], [centroid[1], text_pos[1]], [centroid[2], text_pos[2]], 
                color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        ax2.text(text_pos[0], text_pos[1], text_pos[2], f"{err:.1f}", 
                color='black', fontsize=9, fontweight='bold', ha='center', va='center',
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8))
    
    if len(frames_points_local) > 0:
        valid_pts = [pts for pts, err in zip(frames_points_local, errors_local) if err != np.inf]
        if valid_pts:
            all_pts = np.vstack(valid_pts)
            ax2.scatter(all_pts[:,0], all_pts[:,1], all_pts[:,2], c='k', s=2, alpha=0.3)
    
    # Ajouter les caméras
    if camera_positions is not None:
        for cam_name, C in camera_positions.items():
            ax2.scatter(*C, c='magenta', s=60, marker='^', edgecolors='black')
            ax2.text(C[0], C[1], C[2] + 50, cam_name, color='magenta', fontsize=8, fontweight='bold')
            # Optionnel : ajouter les axes locaux si rvecs fourni
            if rvecs is not None and cam_name in rvecs:
                R, _ = cv2.Rodrigues(rvecs[cam_name])
                colors = ['r', 'g', 'b']
                for i in range(3):
                    start = C
                    end = C + R[:, i] * (camera_scale * 0.5)
                    ax2.plot([start[0], end[0]], [start[1], end[1]], [start[2], end[2]], 
                            c=colors[i], linewidth=1.5)
    
    ax2.set_xlabel("X (mm)")
    ax2.set_ylabel("Y (mm)")
    ax2.set_zlabel("Z (mm)")
    ax2.set_title("TRIANGULATION LOCALE", fontsize=12, fontweight='bold', color='darkred')
    ax2.view_init(elev=25, azim=-50)
    
    # Barre de couleur commune
    mappable = plt.cm.ScalarMappable(cmap=cmap)
    mappable.set_array([min_err, max_err])
    cbar = fig.colorbar(mappable, ax=[ax1, ax2], pad=0.05, shrink=0.6)
    cbar.set_label("Erreur moyenne (mm)")
    
    plt.suptitle("Comparaison : Triangulation Globale vs Locale", fontsize=14, fontweight='bold', y=0.98)
    plt.show()



def compute_reorientation_matrix(O, Xp, Yp):
    """
    Construit une matrice de réorientation orthonormée à partir de 3 points.
    Assure que les axes sont correctement alignés.
    
    O : origine
    Xp : point définissant la direction X
    Yp : point définissant la direction Y (utilisé pour calculer Z via produit vectoriel)
    """
    O = np.asarray(O).reshape(3,)
    Xp = np.asarray(Xp).reshape(3,)
    Yp = np.asarray(Yp).reshape(3,)
    
    # Vecteurs bruts
    x_raw = Xp - O
    y_raw = Yp - O
    
    # Normalisation X
    x_axis = x_raw / np.linalg.norm(x_raw)
    
    # Z = X × Y (règle main droite)
    z_axis = np.cross(x_axis, y_raw)
    z_axis = z_axis / np.linalg.norm(z_axis)
    
    # Y orthonormé = Z × X
    y_axis = np.cross(z_axis, x_axis)
    y_axis = y_axis / np.linalg.norm(y_axis)
    
    # Matrice de rotation
    R = np.column_stack((x_axis, y_axis, z_axis))
    
    # Affichage de diagnostic
    print(f"\n=== Diagnostic du Référentiel ===")
    print(f"Point O (origine) : {O}")
    print(f"Point X : {Xp}")
    print(f"Point Y : {Yp}")
    print(f"\nAxes du repère :")
    print(f"  X_axis (|X|={np.linalg.norm(x_axis):.4f}): {x_axis}")
    print(f"  Y_axis (|Y|={np.linalg.norm(y_axis):.4f}): {y_axis}")
    print(f"  Z_axis (|Z|={np.linalg.norm(z_axis):.4f}): {z_axis}")
    print(f"\nVérifications d'orthonormalité :")
    print(f"  X·Y = {np.dot(x_axis, y_axis):.6f} (doit être ~0)")
    print(f"  X·Z = {np.dot(x_axis, z_axis):.6f} (doit être ~0)")
    print(f"  Y·Z = {np.dot(y_axis, z_axis):.6f} (doit être ~0)")
    print(f"  det(R) = {np.linalg.det(R):.6f} (doit être ~1)")
    
    # Analyse de l'axe Z
    # Supposons que dans le repère monde, Z vertical ≈ [0, 0, 1]
    world_up = np.array([0, 0, 1])
    z_angle = np.degrees(np.arccos(np.clip(np.dot(z_axis, world_up), -1, 1)))
    print(f"\nAxe Z vs vertical du monde : {z_angle:.1f}° (idéalement ~0° ou ~180°)")
    if z_angle > 30 and z_angle < 150:
        print(f"⚠️ ATTENTION: Z n'est pas bien vertical ({z_angle:.1f}°) !")
        print(f"   Assurez-vous que les 3 points forment un repère ortho orienté correctement")
    
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
    
    # Mise à jour du dict videos avec les chemins synchronisés
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

    # 5. Définition du repère via la frame 0 (Referentiel)
    if not referentiel:
        print("Attention: Pas de référentiel (frame 0) annoté. Utilisation du repère monde par défaut.")
        # On crée une matrice identité pour que le code continue
        R_ref, O_ref = np.eye(3), np.zeros(3)
    else:
        ref_points_cam = {cam: np.array(referentiel[cam], dtype=np.float32) for cam in referentiel}
        # On utilise la triangulation simple ici pour le ref
        ref_points3D, _ = triangulate_points(ref_points_cam, projection_matrices)
        O_ref, Xp, Yp = ref_points3D[0], ref_points3D[1], ref_points3D[2]

        print(f"\n=== Points 3D Triangulés (Repère Monde) ===")
        print(f"O  : {O_ref}")
        print(f"X  : {Xp}")
        print(f"Y  : {Yp}")
        print(f"\nDifférences :")
        print(f"  X - O = {Xp - O_ref}  (doit être horizontal)")
        print(f"  Y - O = {Yp - O_ref}  (doit être horizontal)")
        print(f"\nVérification que points au sol :")
        print(f"  O[2] (Z) = {O_ref[2]:.1f}")
        print(f"  X[2] (Z) = {Xp[2]:.1f}")
        print(f"  Y[2] (Z) = {Yp[2]:.1f}")
        print(f"  Écart O-X : ΔZ = {abs(O_ref[2] - Xp[2]):.1f} mm (doit être ~0)")
        print(f"  Écart O-Y : ΔZ = {abs(O_ref[2] - Yp[2]):.1f} mm (doit être ~0)")

        # Validation: vérifier colinéarité et angle OX vs OY
        x_raw = Xp - O_ref
        y_raw = Yp - O_ref
        nx = np.linalg.norm(x_raw)
        ny = np.linalg.norm(y_raw)
        if nx > 0 and ny > 0:
            cosang = np.clip(np.dot(x_raw, y_raw) / (nx * ny), -1.0, 1.0)
            ang_deg = np.degrees(np.arccos(cosang))
            print(f"\nRéférentiel: |OX|={nx:.1f} mm, |OY|={ny:.1f} mm, angle(OX,OY)={ang_deg:.1f}°")
            if ang_deg < 10.0:
                print("⚠️ Alerte: OX et OY presque colinéaires (<10°). Choisis un Y loin de l'axe O→X.")
        else:
            print("⚠️ Norme nulle sur OX ou OY (points identiques?).")

        R_ref, O_ref = compute_reorientation_matrix(O_ref, Xp, Yp)
        detR = np.linalg.det(R_ref)
        print(f"✅ Matrice de réorientation calculée. det(R)={detR:.6f}")

    # 6. Triangulation et Validation frame par frame
    theoretical_distances = [250, 243, 290] # mm
    all_points_global = []
    all_points_local = []
    all_errors_global = []
    all_errors_local = []

    print("\n--- Validation (Comparaison Global vs Local) ---")
    print(f"{'Frame':<8} {'Err Global (mm)':<18} {'Err Local (mm)':<18} {'Meilleur':<12}")
    print("-" * 60)
    
    for frame_num in sorted(annotations.keys()):
        points_cam_arr = {cam: np.array(pts, dtype=np.float32) for cam, pts in annotations[frame_num].items()}
        
        # --- TRIANGULATION GLOBALE ---
        try:
            points_3D_global = triangulate_points_global(points_cam_arr, projection_matrices)
        except Exception as e:
            print(f"Erreur triangulation globale frame {frame_num}: {e}")
            points_3D_global = None
        
        # --- TRIANGULATION LOCALE (par paire) ---
        try:
            points_3D_local, _ = triangulate_points(points_cam_arr, projection_matrices)
        except Exception as e:
            print(f"Erreur triangulation locale frame {frame_num}: {e}")
            points_3D_local = None
        
        # Évaluation Global
        if points_3D_global is not None:
            points_3D_global_reorient = reorient_points(points_3D_global, R_ref, O_ref)
            res_global = validate_calibration(points_3D_global_reorient, theoretical_distances)
            err_global = res_global['mean_error']
            all_points_global.append(points_3D_global_reorient)
            all_errors_global.append(err_global)
        else:
            err_global = np.inf
            all_errors_global.append(err_global)
        
        # Évaluation Local
        if points_3D_local is not None:
            points_3D_local_reorient = reorient_points(points_3D_local, R_ref, O_ref)
            res_local = validate_calibration(points_3D_local_reorient, theoretical_distances)
            err_local = res_local['mean_error']
            all_points_local.append(points_3D_local_reorient)
            all_errors_local.append(err_local)
        else:
            err_local = np.inf
            all_errors_local.append(err_local)
        
        # Sélection meilleur
        if err_global <= err_local:
            best = "GLOBAL"
            all_points = all_points_global
        else:
            best = "LOCAL"
            all_points = all_points_local
        
        print(f"{frame_num:<8} {err_global:<18.2f} {err_local:<18.2f} {best:<12}")
    
    print("-" * 60)
    mean_global = np.mean([e for e in all_errors_global if e != np.inf])
    mean_local = np.mean([e for e in all_errors_local if e != np.inf])
    print(f"Moyenne Global: {mean_global:.2f} mm")
    print(f"Moyenne Local:  {mean_local:.2f} mm")
    print(f"✅ Meilleure méthode globale: {'GLOBAL' if mean_global <= mean_local else 'LOCAL'}")

    # 7. Affichage Final : Comparaison côte à côte
    print("\nAffichage COMPARATIF (Global vs Local) côte à côte...")
    
    # Calculer les positions finales des caméras dans le repère transformé
    camera_positions = {}
    for cam_name, rvec in rvecs.items():
        R_cam, _ = cv2.Rodrigues(rvec)
        t_cam = tvecs[cam_name].reshape(3,1)
        
        # Centre optique dans le monde
        C_world = -R_cam.T @ t_cam
        
        # Centre optique dans le nouveau repère
        C_new = reorient_points(C_world.T, R_ref, O_ref).T.reshape(3)
        camera_positions[cam_name] = C_new

    plot_triangles_comparison(all_points_global, all_errors_global, 
                             all_points_local, all_errors_local,
                             camera_positions=camera_positions, rvecs=rvecs)