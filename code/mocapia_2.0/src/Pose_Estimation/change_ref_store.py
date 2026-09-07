# Pose_Estimation/change_ref_store.py
import os, json
from datetime import datetime
import numpy as np

FILENAME = "change_ref.json"  # Stored under the calibration directory of each experiment

def _change_ref_dir(project_path: str, experiment_name: str) -> str:
    # If your project directory structure differs, modify it here in one place
    d = os.path.join(project_path, experiment_name, "change_ref")
    os.makedirs(d, exist_ok=True)
    return d

def _json_path(project_path: str, experiment_name: str) -> str:
    return os.path.join(_change_ref_dir(project_path, experiment_name), FILENAME)

def save_T(project_path: str, experiment_name: str, T):
    """T: 4x4 numpy.ndarray or iterable -> save as JSON"""
    arr = np.array(T, dtype=float).tolist()
    payload = {
        "transform_R1_to_R2": arr,
        "created_at": datetime.now().isoformat(timespec="seconds")
    }
    with open(_json_path(project_path, experiment_name), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def load_T(project_path: str, experiment_name: str):
    """Return numpy.ndarray(4,4) or None"""
    p = _json_path(project_path, experiment_name)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        T = data.get("transform_R1_to_R2")
        if T is None:
            return None
        return np.array(T, dtype=float)
    except Exception:
        return None
