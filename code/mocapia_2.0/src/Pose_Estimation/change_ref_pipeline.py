from typing import List, Dict
import os, json, numpy as np, h5py
from .video_utils import (
    build_camera_image_map_from_videos_using_config,
    pick_points_for_cameras,
)
from config.Hdf5 import Hdf5_Calib
from .extrinsic_calib import ExtrinsicCalib
from .Triangulator import Triangulator
from .change_ref_store import save_T
from .video_utils import UserCancelled
import pandas as pd
from pathlib import Path
class UserCancelled(Exception):
    """User closed the OpenCV picker or cancelled the operation."""
    pass



def run_change_reference(
    video_paths: List[str],
    project_path: str,
    experiment_name: str,
    out_base_dir: str,
    capture_name: str,
    xlen: float = 160.0,
    ylen: float = 120.0,
) -> str:
    """
    1) Extract frames → generate {ip: frame.jpg}
    2) Interactively select 3 points (O, X, Y) → save change_ref_points.json
    3) Read three points per camera → triangulate to 3D (R1)
    4) Build R2 points [[0,0,0],[xlen,0,0],[0,ylen,0]] → compute 4x4 transform T
    5) Save to change_ref.json and also write to HDF5 dataset 'T'
    6) Return path to change_ref.json
    """
    print("[DEBUG] run_change_reference video_paths:", video_paths)
    change_ref_dir = os.path.join(project_path, experiment_name, "change_ref")
    calib_dir = os.path.join(project_path, experiment_name, "calibration")
    os.makedirs(change_ref_dir, exist_ok=True)

    points_json = os.path.join(change_ref_dir, "change_ref_points.json")

    # —— 1) + 2) extract frames and select points
    cam_img_map: Dict[str, str] = build_camera_image_map_from_videos_using_config(
        video_paths=video_paths,
        project_path=project_path,
        experiment_name=experiment_name,
        out_base_dir=out_base_dir,
    )
    if not cam_img_map:
        raise RuntimeError("No camera frames generated. Please check video paths and configuration mapping.")

    try:
        cam_points_dict = pick_points_for_cameras(cam_img_map, num_points=3)
    except UserCancelled:
        # When the user actively cancels: just return, don’t crash the whole Qt application.
        return ""

    if not cam_points_dict or min(len(v) for v in cam_points_dict.values()) < 3:
        raise RuntimeError("Insufficient points. Each camera requires 3 points.")

    with open(points_json, "w", encoding="utf-8") as f:
        json.dump(cam_points_dict, f, ensure_ascii=False, indent=2)

    # —— 3) Read three points and perform triangulation —— #
    with open(points_json, "r", encoding="utf-8") as f:
        data = json.load(f)  # {"<ip>": [[xO,yO],[xX,yX],[xY,yY]], ...}

    cam_points = {cam: np.asarray(pts, dtype=float) for cam, pts in data.items()}
    if len(cam_points) < 2:
        raise RuntimeError("At least two cameras are required for triangulation.")

    h5_path = os.path.join(calib_dir, f"{experiment_name}_calibration_param.hdf5")
    _ = Hdf5_Calib(h5_path)  
    # ext = ExtrinsicCalib(project_path, experiment_name, (11, 10), 47)
    ext = ExtrinsicCalib(project_path, experiment_name, (6, 5), 120)

    # ext.triangulate_points takes {ip: (3x2)} → returns (3x3) 3D coordinates of the three points
    pts_R1_3D, _ = ext.triangulate_points(cam_points)   # Expected shape (3,3)
    pts_R1_3D = np.asarray(pts_R1_3D, dtype=float)
    if pts_R1_3D.shape != (3, 3):
        raise RuntimeError(f"Unexpected triangulation shape: {pts_R1_3D.shape}, expected (3,3).")

    # —— 4) Compute the R1→R2 4x4 transformation T —— #
    tri = Triangulator(project_path, experiment_name, capture_name, "tmp")
    pts_R2 = np.array([[0.0, 0.0, 0.0], [xlen, 0.0, 0.0], [0.0, ylen, 0.0]], dtype=float)
    T = tri.calculate_transformation_matrix(pts_R1_3D, pts_R2)  # Expected 4x4
    T = np.asarray(T, dtype=float)
    if T.shape != (4, 4):
        raise RuntimeError(f"Calculated transformation matrix T has an unexpected shape: {T.shape}, expected (4, 4).")

    # —— 5) Save to JSON and also write to HDF5 —— #
    save_T(project_path, experiment_name, T)  # Writes calibration/change_ref.json
    json_out = os.path.join(change_ref_dir, "change_ref.json")

    try:
        with h5py.File(h5_path, "a") as f:
            if "T" in f:
                del f["T"]
            f.create_dataset("T", data=T.astype("float64"))
    except Exception as e:
        print(f"[warn] Failed to write HDF5 dataset 'T': {e}")
    json_out = os.path.normpath(json_out)
    apply_T_to_csv(project_path, experiment_name, capture_name)
    return json_out
def apply_T_to_csv(project_path: str, experiment_name: str, capture_name: str):
    """
    Apply the change_ref.json transformation matrix T to the 3D_points CSV,
    overwrite the CSV, and create a backup named *_original.csv.
    """

    # ① Locate the CSV file
    csv_path = os.path.join(
        project_path,
        experiment_name,
        "analysis",
        capture_name,
        f"{capture_name}_3D_points.csv"
    )

    if not os.path.isfile(csv_path):
        print("[ChangeRef] CSV not found:", csv_path)
        return

    # ② Path to change_ref.json
    json_path = os.path.join(
        project_path,
        experiment_name,
        "change_ref",
        "change_ref.json"
    )

    if not os.path.isfile(json_path):
        print("[ChangeRef] change_ref.json not found:", json_path)
        return

    #  Load transformation matrix T
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    T = np.array(data["transform_R1_to_R2"], dtype=float)

    #  Read the original CSV header
    with open(csv_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    header_lines = lines[:5]

    joints_line = lines[2].strip().split(',')
    axes_line   = lines[3].strip().split(',')

    if joints_line[0] == '':
        joints_line[0] = 'Frames'

    columns = []
    joint_name = None
    for j, a in zip(joints_line, axes_line):
        if a == 'X':
            joint_name = j
        columns.append((joint_name, a))
    multi_cols = pd.MultiIndex.from_tuples(columns, names=['Joint','Axis'])

    # Read numeric data
    df = pd.read_csv(csv_path, skiprows=5, header=None)
    if df.shape[1] > len(multi_cols):
        df = df.iloc[:, :len(multi_cols)]
    df.columns = multi_cols

    # Extract XYZ positions
    xyz_cols = [(j, ax) for (j, ax) in df.columns if ax in ('X', 'Y', 'Z')]
    N = len(df)

    # Apply transformation
    coords = df[xyz_cols].to_numpy().reshape(N, -1, 3)
    ones = np.ones((N, coords.shape[1], 1))
    points_h = np.concatenate([coords, ones], axis=2)
    flat = points_h.reshape(-1, 4).T
    trans = (T @ flat).T[:, :3]
    out_coords = trans.reshape(coords.shape)

    df_out = df.copy()
    df_out[xyz_cols] = out_coords.reshape(N, -1)

    #  Write transformed CSV back to file and create a backup
    out_path_backup = str(Path(csv_path).with_name(Path(csv_path).stem + "_original.csv"))
    if not os.path.exists(out_path_backup):
        os.rename(csv_path, out_path_backup)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        for line in header_lines:
            f.write(line if line.endswith("\n") else line + "\n")
        df_out.to_csv(f, index=False, header=False)

    print("✔ CSV updated successfully:", csv_path)
