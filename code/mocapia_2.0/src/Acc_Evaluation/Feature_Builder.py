import os
import numpy as np
import pandas as pd
from typing import NamedTuple, List, Optional


from Pose_Estimation.csv_utils import read_csv_data
from Acc_Evaluation.Path_utils import make_output_path



class SegmentDef(NamedTuple):
    name: str
    a: str
    b: str

class AngleDef(NamedTuple):
    name: str      # e.g. "Left Knee Flexion"
    a: str         # proximal marker, e.g. "LHip"
    b: str         # joint marker, e.g. "LKnee"
    c: str         # distal marker, e.g. "LAnkle"
segments = [
    SegmentDef("Left Upper Arm (Humerus)", "LShoulder", "LElbow"),
    SegmentDef("Left Forearm (Radius/Ulna)", "LElbow", "LWrist"),
    SegmentDef("Right Upper Arm (Humerus)", "RShoulder", "RElbow"),
    SegmentDef("Right Forearm (Radius/Ulna)", "RElbow", "RWrist"),
    SegmentDef("Left Thigh (Femur)", "LHip", "LKnee"),
    SegmentDef("Left Shank (Tibia)", "LKnee", "LAnkle"),
    SegmentDef("Right Thigh (Femur)", "RHip", "RKnee"),
    SegmentDef("Right Shank (Tibia)", "RKnee", "RAnkle"),
    SegmentDef("Shoulder Width", "LShoulder", "RShoulder"),
    SegmentDef("Hip Width", "LHip", "RHip"),
]
ANGLES = [
    # Knee angle: Hip-Knee-Ankle
    AngleDef("Left Knee Angle", "LHip", "LKnee", "LAnkle"),
    AngleDef("Right Knee Angle", "RHip", "RKnee", "RAnkle"),

    # Elbow angle: Shoulder-Elbow-Wrist
    AngleDef("Left Elbow Angle", "LShoulder", "LElbow", "LWrist"),
    AngleDef("Right Elbow Angle", "RShoulder", "RElbow", "RWrist"),

    # Optional: Hip angle: Shoulder/Hip/Knee (depends on your marker set)
    AngleDef("Left Hip Angle", "LShoulder", "LHip", "LKnee"),
    AngleDef("Right Hip Angle", "RShoulder", "RHip", "RKnee"),
]

class Feature_Builder(object):
    """
    Build per-frame features from raw 3D CSV (MoCapIA format).
    This class is the 'slow' stage: heavy computations, then export CSV caches.
    """

    def __init__(self, csv_path):
        self.csv_path = csv_path

        self.fps = None  # Optional[int]
        self.frames = None  # pd.Series
        self.time = None  # pd.Series
        self.markers = None  # List[str]
        self.Q_coords = None  # pd.DataFrame

        self.X = None  # np.ndarray (F,M,3)
        self.valid_mask = None  # np.ndarray (F,M)
   
    def _auto_convert_to_mm(self):
        coords = self.Q_coords.values
        max_abs = abs(coords[:1000]).max()

        if max_abs < 10:  
            print("[Unit Detection] Detected meters → converting to mm")
            self.Q_coords *= 1000


    def load(self):
        Q_coords, frames_col, time_col, markers, header_lines = read_csv_data(self.csv_path)

        self.Q_coords = Q_coords
        self.frames = frames_col
        self.time = time_col
        self.markers = markers

        try:
            self.fps = int(header_lines[1].strip())
        except Exception:
            self.fps = 30 # Default to 30 if not found
        self._auto_convert_to_mm()
        self.X = self._build_tensor()
        self.valid_mask = self._compute_valid_mask()
        
        return self

    def _ensure_loaded(self):
        if self.X is None or self.valid_mask is None or self.markers is None:
            raise RuntimeError("Not loaded. Call .load() first.")

    def _build_tensor(self):
        nF = len(self.frames)
        nM = len(self.markers)
        X = np.zeros((nF, nM, 3), dtype=float)
        for j, m in enumerate(self.markers):
            X[:, j, 0] = self.Q_coords["%s_x" % m].values
            X[:, j, 1] = self.Q_coords["%s_y" % m].values
            X[:, j, 2] = self.Q_coords["%s_z" % m].values
        return X

    def _compute_valid_mask(self):
        finite = np.isfinite(self.X).all(axis=2)
        non_zero = (np.abs(self.X).sum(axis=2) > 1e-9)
        return finite & non_zero

    def get_marker_index(self, marker):
        self._ensure_loaded()
        try:
            return self.markers.index(marker)
        except ValueError:
            raise KeyError("Marker '%s' not found." % marker)

    def get_xyz(self, marker):
        idx = self.get_marker_index(marker)
        return self.X[:, idx, :]

    def _pair_valid(self, a, b):
        ia = self.get_marker_index(a)
        ib = self.get_marker_index(b)
        return self.valid_mask[:, ia] & self.valid_mask[:, ib]
    def _triple_valid(self, a, b, c):
        ia = self.get_marker_index(a)
        ib = self.get_marker_index(b)
        ic = self.get_marker_index(c)
        return self.valid_mask[:, ia] & self.valid_mask[:, ib] & self.valid_mask[:, ic]

    @staticmethod
    def _angle_3d(A, B, C, eps=1e-9):
        """
        A,B,C: arrays shape (N,3) for valid frames only
        Returns angle in degrees, shape (N,)
        """
        v1 = A - B  # BA
        v2 = C - B  # BC
        n1 = np.linalg.norm(v1, axis=1)
        n2 = np.linalg.norm(v2, axis=1)

        denom = (n1 * n2) + eps
        cosang = np.sum(v1 * v2, axis=1) / denom
        cosang = np.clip(cosang, -1.0, 1.0)
        ang = 180.0-np.degrees(np.arccos(cosang))
        return ang

    # -----------------------------
    # Feature 1: Segment lengths
    # -----------------------------
    def segment_length_series(self, a, b, fill_value=np.nan):
        A = self.get_xyz(a)
        B = self.get_xyz(b)
        valid = self._pair_valid(a, b)

        L = np.full((A.shape[0],), fill_value, dtype=float)
        L[valid] = np.linalg.norm(A[valid] - B[valid], axis=1)
        return L
    
    def joint_angle_series(self, a, b, c, fill_value=np.nan):
        """
        Joint angle at b for triplet a-b-c (degrees).
        Invalid frames -> fill_value (default NaN)
        """
        self._ensure_loaded()

        if (a not in self.markers) or (b not in self.markers) or (c not in self.markers):
            return np.full((len(self.frames),), fill_value, dtype=float)

        A = self.get_xyz(a)
        B = self.get_xyz(b)
        C = self.get_xyz(c)

        valid = self._triple_valid(a, b, c)
        out = np.full((A.shape[0],), fill_value, dtype=float)
        if valid.any():
            out[valid] = self._angle_3d(A[valid], B[valid], C[valid])
        return out

    def build_segment_length_df(self, segments):
        """
        Return per-frame segment length features.
        Columns:
          Frames, Time, <name>__<a>-<b>
        """
        self._ensure_loaded()

        df = pd.DataFrame({
            "Frames": self.frames.values,
            "Time": self.time.values
        })

        for seg in segments:
            col = "%s__%s-%s" % (seg.name, seg.a, seg.b)
            if (seg.a not in self.markers) or (seg.b not in self.markers):
                df[col] = np.nan
            else:
                df[col] = self.segment_length_series(seg.a, seg.b, fill_value=np.nan)

        return df
    
    def build_joint_angle_df(self, angles):
        """
        angles: List[AngleDef]
        Output columns:
        Frames, Time, <name>__<a>-<b>-<c>  (degrees)
        """
        self._ensure_loaded()

        df = pd.DataFrame({
        "Frames": self.frames.values,
        "Time": self.time.values
        })

        for ang in angles:
            col = "%s__%s-%s-%s" % (ang.name, ang.a, ang.b, ang.c)
            df[col] = self.joint_angle_series(ang.a, ang.b, ang.c, fill_value=np.nan)

        return df

    def export_segment_lengths(self, segments, csv_out_path=None):
        if csv_out_path is None:
            csv_out_path = make_output_path(self.csv_path,kind="features", tag="segment_lengths")

        df = self.build_segment_length_df(segments)
        df.to_csv(csv_out_path, index=False)
        return df, csv_out_path

    def export_joint_angles(self, angles, csv_out_path=None):
        if csv_out_path is None:
            csv_out_path = make_output_path(self.csv_path, kind="features", tag="angles")

        df = self.build_joint_angle_df(angles)
        df.to_csv(csv_out_path, index=False)
        return df, csv_out_path

    def summary(self):
        self._ensure_loaded()
        print("=== FeatureBuilder Summary ===")
        print("File:", self.csv_path)
        print("FPS:", self.fps)
        print("Frames:", int(self.X.shape[0]))
        print("Markers:", int(self.X.shape[1]))
        print("First markers:", self.markers[:20])
        print("==============================")

if __name__ == "__main__":
   
   

    raw_csv = r"D:\Users\Etudiant\Documents\MOCAPIA5\mocapia_3\ProjectsFOLDERS\TestCalibProject_CJL\test_calib\analysis\CJL_mov1\CJL_mov1_3D_points_filt_butterworth_LSTM.csv"

    builder = Feature_Builder(raw_csv).load()
    builder.summary()


    df_len, path_len = builder.export_segment_lengths(segments)
    print("Segment length file saved to:", path_len)
    print("Shape:", df_len.shape)
    print(df_len.head())

    df_ang, path_ang = builder.export_joint_angles(ANGLES)
    print("Joint angle file saved to:", path_ang)
    print("Shape:", df_ang.shape)
    print(df_ang.head())