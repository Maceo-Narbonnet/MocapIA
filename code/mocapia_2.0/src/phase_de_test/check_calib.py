# # import h5py
# # import numpy as np
# # import cv2

# # # --- CONFIG ---
# # calib_file = r"D:\Users\Etudiant\Documents\MOCAPIA5\mocapia_3\TestProject12\MoCap_Demo7\calibration\MoCap_Demo7_calibration_param.hdf5"  # paramètres caméras
# # detect_file = r"D:\Users\Etudiant\Documents\MOCAPIA5\mocapia_3\TestProject12\MoCap_Demo7\calibration\tmp\MoCap_Demo7_detections.hdf5"    # détections coins
# # nx, ny = 11, 10                                    # taille du damier
# # square_size = 47                                   # mm

# # # --- CHARGER LES PARAMÈTRES CAMÉRA ---
# # with h5py.File(calib_file, "r") as f_calib, h5py.File(detect_file, "r") as f_det:
# #     for cam_id in f_det.keys():
# #         print(f"\n--- Caméra {cam_id} ---")

# #         # intrinsics
# #         K = f_calib["intrinsics"][cam_id]["mtx"][:]   # matrice intrinsèque 3x3
# #         dist = f_calib["intrinsics"][cam_id]["dist"][:]  # coeffs distorsion

# #         # extrinsics
# #         R = f_calib["extrinsics"][cam_id]["R"][:]   # matrice rotation 3x3
# #         T = f_calib["extrinsics"][cam_id]["T"][:]   # vecteur translation (3,)
# #         print("T :\n", np.array(T),"\n")

# #         # convertir R en vecteur de rotation (Rodrigues)
# #         rvec, _ = cv2.Rodrigues(R)
# #         tvec = T.reshape(3,1)

# #         # points 3D du damier
# #         objp = np.zeros((nx*ny, 3), np.float32)
# #         objp[:, :2] = np.mgrid[0:nx, 0:ny].T.reshape(-1,2)
# #         objp *= square_size  # mm

# #         # parcourir toutes les frames
# #         cam_group = f_det[cam_id]
# #         for frame_id in cam_group.keys():
# #             corners_detected = cam_group[frame_id][:]  # shape (N,2)
# #             #print("pts 3D :\n", np.array(corners_detected),"\n")
# #             if corners_detected.shape[0] != nx*ny:
# #                 print(f"Frame {frame_id}: coins détectés ({corners_detected.shape[0]}) ≠ attendu ({nx*ny})")
# #                 continue

# #             # projeter les points 3D en 2D
# #             corners_projected, _ = cv2.projectPoints(objp, rvec, tvec, K, dist)
# #             corners_projected = corners_projected.squeeze()  # (N,2)
# #             #print("pts 3D :\n", np.array(corners_projected),"\n")
# #             # calcul de l’erreur de reprojection
# #             error = np.linalg.norm(corners_detected - corners_projected, axis=1).mean()
# #             print(f"Frame {frame_id}: erreur de reprojection = {error:.2f} pixels")


# import cv2
# import numpy as np
# import h5py
# import matplotlib.pyplot as plt

# # --- chemins vers tes fichiers ---
# calib_file = r"D:\Users\Etudiant\Documents\MoCapIA5\mocapia_3\TestProject12\MoCap_Demo7\calibration\MoCap_Demo7_calibration_param.hdf5"
# detection_file = r"D:\Users\Etudiant\Documents\MoCapIA5\mocapia_3\TestProject12\MoCap_Demo7\calibration\tmp\MoCap_Demo7_detections.hdf5"
# image_file = r"D:\Users\Etudiant\Documents\MOCAPIA5\mocapia_3\TestProject12\MoCap_Demo7\calibration\tmp\C3501325588979_tmp\frame_0000.jpg"


# camera_id = "C3501325588979"  # <-- adapte selon ta caméra
# frame_id = "0"                # <-- index d'une image

# # --- Charger calibration ---
# with h5py.File(calib_file, "r") as f:
#     K = np.array(f[f"intrinsics/{camera_id}/mtx"])
#     dist = np.array(f[f"intrinsics/{camera_id}/dist"])
#     R = np.array(f[f"extrinsics/{camera_id}/R"])
#     T = np.array(f[f"extrinsics/{camera_id}/T"])

# T = 10*T
# # Vérifie si R est matrice 3x3 → convertir en Rodrigues
# if R.shape == (3, 3):
#     rvec, _ = cv2.Rodrigues(R)
# else:
#     rvec = R

# tvec = T.reshape(3, 1)

# # --- Charger detections ---
# with h5py.File(detection_file, "r") as f:
#     pts2d = np.array(f[f"{camera_id}/{frame_id}"])  # (N,2)
# pts2d = pts2d.reshape(-1, 2)
# # --- Générer points 3D du damier ---
# chessboard_size = (11, 10)  # <-- adapte
# square_size = 47            # mm
# objp = np.zeros((chessboard_size[0] * chessboard_size[1], 3), np.float32)
# objp[:, :2] = np.mgrid[0:chessboard_size[0], 0:chessboard_size[1]].T.reshape(-1, 2)
# objp *= square_size

# # --- Projeter en 2D avec calibration ---
# pts2d_proj, _ = cv2.projectPoints(objp, rvec, tvec, K, dist)
# pts2d_proj = pts2d_proj.squeeze()
# #print("pts2d_proj:\n", pts2d_proj)
# # Exemple avec R et T de ton hdf5
# pt_cam = R @ objp.T + T  # shape (3, N)
# # print(pt_cam.T[:5])  # Affiche les 5 premiers points
# # T[2] = -T[2]
# #print("T:\n", T)
# # print("dist:\n", dist)
# # print("K:\n", K)
# # print("rvec:\n", rvec)
# # print("tvec:\n", tvec)

# # --- Visualisation ---
# # plt.figure(figsize=(8, 6))
# # print("Shape pts2d_reproj:", pts2d_proj.shape)
# # plt.scatter(pts2d[:, 0], pts2d[:, 1], c='r', label='Détectés')
# # plt.scatter(pts2d_proj[:, 0], pts2d_proj[:, 1], c='b', marker='+', label='Reprojetés')
# # plt.gca().invert_yaxis()  # car origine image en haut-gauche
# # plt.legend()
# # plt.title(f"Comparaison reprojection vs détection - caméra {camera_id}, frame {frame_id}")
# # plt.show()
# img = cv2.imread(image_file)
# img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
# # --- Superposer les points ---
# for pt in pts2d:
#     cv2.circle(img_rgb, (int(pt[0]), int(pt[1])), 5, (255, 0, 0), -1)  # rouge = détectés

# for pt in pts2d_proj:
#     cv2.drawMarker(img_rgb, (int(pt[0]), int(pt[1])), (0, 255, 0), markerType=cv2.MARKER_CROSS, markerSize=10, thickness=2)  # vert = reprojetés

# # --- Affichage ---
# plt.figure(figsize=(10, 8))
# plt.imshow(img_rgb)
# plt.axis('off')
# plt.title(f"Points détectés (rouge) vs reprojetés (vert) - caméra {camera_id}, frame {frame_id}")
# plt.show()

import cv2
import numpy as np
import h5py
import matplotlib.pyplot as plt
import glob
import os

# --- chemins ---
calib_file = r"D:\Users\Etudiant\Documents\MoCapIA5\mocapia_3\TestProject12\MoCap_Demo7\calibration\MoCap_Demo7_calibration_param.hdf5"
detection_file = r"D:\Users\Etudiant\Documents\MoCapIA5\mocapia_3\TestProject12\MoCap_Demo7\calibration\tmp\MoCap_Demo7_detections.hdf5"
image_folder = r"D:\Users\Etudiant\Documents\MOCAPIA5\mocapia_3\TestProject12\MoCap_Demo7\calibration\tmp\C3501325588979_tmp"

with h5py.File(detection_file, "r") as f:
    def print_structure(name, obj):
        print(name, "->", type(obj))
    f.visititems(print_structure)

camera_id = "C3501325588979"
draw_image = False
# --- Charger calibration ---
with h5py.File(calib_file, "r") as f:
    K = np.array(f[f"intrinsics/{camera_id}/mtx"])
    dist = np.array(f[f"intrinsics/{camera_id}/dist"])

# --- Générer points 3D du damier (repère local du damier) ---
chessboard_size = (11, 10)
square_size = 47  # mm
objp = np.zeros((chessboard_size[0] * chessboard_size[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:chessboard_size[0], 0:chessboard_size[1]].T.reshape(-1, 2)
objp *= square_size

# --- Charger detections ---
with h5py.File(detection_file, "r") as f:
    pts2d_all = {frame: np.array(f[f"{camera_id}/{frame}"]).reshape(-1, 2) for frame in f[f"{camera_id}"].keys()}

# --- Boucle sur toutes les frames ---
for frame_id, pts2d in pts2d_all.items():
    # Vérifie qu'on a des points
    if pts2d.shape[0] != objp.shape[0]:
        print(f"Frame {frame_id} ignorée : nombre de coins incorrect")
        continue

    # --- Estimer la pose du damier avec solvePnP ---
    success, rvec, tvec = cv2.solvePnP(objp, pts2d, K, dist)
    if not success:
        print(f"Frame {frame_id} : solvePnP a échoué")
        continue

    # --- Reprojection des points ---
    pts2d_reproj, _ = cv2.projectPoints(objp, rvec, tvec, K, dist)
    pts2d_reproj = pts2d_reproj.squeeze()

    # --- Calcul de l'erreur de reprojection ---
    reproj_error = np.mean(np.linalg.norm(pts2d - pts2d_reproj, axis=1))
    print(f"Frame {frame_id} : erreur de reprojection moyenne = {reproj_error:.2f} px")
    if draw_image:
        # --- Visualisation ---
        img_path = os.path.join(image_folder, f"frame_{int(frame_id):04d}.jpg")
        if not os.path.exists(img_path):
            continue
        img = cv2.imread(img_path)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        for pt in pts2d:
            cv2.circle(img_rgb, (int(pt[0]), int(pt[1])), 5, (255, 0, 0), -1)  # rouge = détectés
        for pt in pts2d_reproj:
            cv2.drawMarker(img_rgb, (int(pt[0]), int(pt[1])), (0, 255, 0),
                        markerType=cv2.MARKER_CROSS, markerSize=10, thickness=2)  # vert = reprojetés

        plt.figure(figsize=(10, 8))
        plt.imshow(img_rgb)
        plt.axis('off')
        plt.title(f"Frame {frame_id} : rouge = détectés, vert = reprojetés, erreur = {reproj_error:.2f}px")
        plt.show()
