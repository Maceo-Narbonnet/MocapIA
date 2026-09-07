# -*- coding: utf-8 -*-
import os
import numpy as np
import pandas as pd
from io import StringIO


# def _find_data_start(lines):
#     for i, line in enumerate(lines):
#         if line.strip().lower() == "endheader":
#             return i + 1
#     raise ValueError("endheader not found in STO file")


# def _extract_markers_in_order(columns):
#     """
#     Keep marker order as they appear in STO columns.
#     STO columns are like: marker_tx, marker_ty, marker_tz
#     """
#     markers = []
#     seen = set()
#     for c in columns:
#         if c.endswith("_tx"):
#             m = c[:-3]
#             if m not in seen:
#                 markers.append(m)
#                 seen.add(m)
#     return markers


# def sto_2_csv(
#     sto_path,
#     out_csv_path,
#     fps=30,
#     to_mm=True,
#     units="mm"
# ):
#     """
#     Convert OpenSim 'Model Marker Locations from IK' STO into
#     DLC-like 3D CSV with 5-line header:

#     Line1: Trajectories,,,,,
#     Line2: fps,,,,,
#     Line3: ,Marker1,,,Marker2,,,
#     Line4: Frames,X,Y,Z,X,Y,Z,...
#     Line5: ,mm,mm,mm,mm,mm,mm,...

#     Data: frame_index, then XYZ per marker.

#     Notes:
#     - Marker order preserved from STO columns order.
#     - If to_mm=True: multiply coordinates by 1000 (m -> mm).
#     """
#     with open(sto_path, "r", encoding="utf-8", errors="ignore") as f:
#         lines = f.readlines()

#     data_start = _find_data_start(lines)
#     df = pd.read_csv(StringIO("".join(lines[data_start:])), sep=r"\s+", engine="python")

#     # Ensure time exists (not strictly needed if we use 0..N-1 frames)
#     if "time" not in df.columns:
#         df = df.rename(columns={df.columns[0]: "time"})

#     markers = _extract_markers_in_order(df.columns)
#     nM = len(markers)
#     nF = int(df.shape[0])

#     if nM == 0:
#         raise ValueError("No markers found (expected columns ending with _tx/_ty/_tz).")

#     # Frames: use 0..N-1 (matches your read_csv_data time reconstruction)
#     frames = np.arange(nF, dtype=int)

#     # Build numeric data matrix: (nF, 1 + 3*nM)
#     data = np.empty((nF, 1 + 3 * nM), dtype=float)
#     data[:, 0] = frames

#     col_idx = 1
#     for m in markers:
#         for suf in ("_tx", "_ty", "_tz"):
#             c = m + suf
#             if c in df.columns:
#                 v = pd.to_numeric(df[c], errors="coerce").values.astype(float)
#             else:
#                 v = np.full((nF,), np.nan, dtype=float)

#             if to_mm:
#                 v = v * 1000.0

#             data[:, col_idx] = v
#             col_idx += 1

#     # ---------- Write 5-line header ----------
#     # total columns count = 1 + 3*nM
#     total_cols = 1 + 3 * nM

#     def line_of(values):
#         # ensure correct length
#         if len(values) != total_cols:
#             raise RuntimeError("Header line length mismatch.")
#         return ",".join(values) + "\n"

#     # Line 1
#     line1 = ["Trajectories"] + [""] * (total_cols - 1)

#     # Line 2
#     line2 = [str(int(fps))] + [""] * (total_cols - 1)

#     # Line 3: marker names aligned to 3 columns each
#     line3 = [""]
#     for m in markers:
#         line3 += [m, "", ""]
#     line3 = line3[:total_cols]  # safety

#     # Line 4: Frames + X Y Z ...
#     line4 = ["Frames"]
#     for _ in markers:
#         line4 += ["X", "Y", "Z"]
#     line4 = line4[:total_cols]

#     # Line 5: units row
#     line5 = [""] + [units] * (total_cols - 1)

#     os.makedirs(os.path.dirname(out_csv_path), exist_ok=True)

#     with open(out_csv_path, "w", newline="") as f:
#         f.write(line_of(line1))
#         f.write(line_of(line2))
#         f.write(line_of(line3))
#         f.write(line_of(line4))
#         f.write(line_of(line5))

#         # write data rows
#         for i in range(nF):
#             row = data[i, :]
#             # keep good precision
#             s = [str(int(row[0]))] + ["%.16f" % x if np.isfinite(x) else "" for x in row[1:]]
#             f.write(",".join(s) + "\n")

#     return out_csv_path
# -*- coding: utf-8 -*-
import os
import numpy as np
import pandas as pd
from io import StringIO
from typing import Dict, List, Tuple, Optional


# ============================================================
# 1) Marker name translation (study -> canonical)
# ============================================================

# 这是“最关键”的映射：把 IK sto 里的 study marker 翻译成你 pipeline 常用命名
# 目标：让 IK 版本能用同一套 ANGLES/SEGMENTS (LHip/LKnee/LAnkle/LShoulder/...)
DEFAULT_STUDY_TO_CANONICAL: Dict[str, str] = {
    # Hip joint centers -> Hip
    "LHJC_study": "LHip",
    "RHJC_study": "RHip",

    # Knee / Ankle joint centers (study) -> Knee / Ankle
    "L_knee_study": "LKnee",
    "r_knee_study": "RKnee",
    "L_ankle_study": "LAnkle",
    "r_ankle_study": "RAnkle",

    # Shoulder
    "L_shoulder_study": "LShoulder",
    "r_shoulder_study": "RShoulder",

    # Elbow / Wrist (use lateral elbow/wrist as your canonical, not medial)
    "L_lelbow_study": "LElbow",
    "r_lelbow_study": "RElbow",
    "L_lwrist_study": "LWrist",
    "r_lwrist_study": "RWrist",

    # (可选) 如果你想把 C7 也统一
    "C7_study": "C7",
}

# 这些“额外的 study 产物”我们一般不映射到 canonical（避免覆盖）
# 例如 r_mknee_study / r_mankle_study / r_melbow_study / r_mwrist_study 等
# 但你仍然想保留它们用于 LSTM 增益分析，所以默认保持原名。
# 如果你以后想映射，也可以加到 DEFAULT_STUDY_TO_CANONICAL 里。


def translate_markers(
    markers_in_order: List[str],
    mapping: Optional[Dict[str, str]] = None,
    keep_unmapped: bool = True,
    collision_strategy: str = "suffix"
) -> Tuple[List[str], Dict[str, str]]:
    """
    Translate marker names using mapping while preserving order.

    Args:
        markers_in_order: marker base names (no _tx/_ty/_tz suffix), in STO column order.
        mapping: dict original -> translated
        keep_unmapped: if True, unmapped markers keep original name
        collision_strategy:
            - "suffix": if translated name already exists, append _dup2/_dup3...
            - "keep_original": if collision, keep original name (no translation for that one)

    Returns:
        markers_out_order: translated marker names (same length)
        orig2out: dict original -> output_name (final, after collision handling)
    """
    if mapping is None:
        mapping = DEFAULT_STUDY_TO_CANONICAL

    used = set()
    out = []
    orig2out = {}

    for m in markers_in_order:
        m2 = mapping.get(m, m if keep_unmapped else "")

        if not m2:  # in case keep_unmapped=False and unmapped -> ""
            continue

        final = m2
        if final in used:
            if collision_strategy == "keep_original":
                final = m  # revert
                if final in used:
                    # still collision, force suffix
                    k = 2
                    while (final + "_dup%d" % k) in used:
                        k += 1
                    final = final + "_dup%d" % k
            else:
                # suffix
                k = 2
                while (final + "_dup%d" % k) in used:
                    k += 1
                final = final + "_dup%d" % k

        used.add(final)
        out.append(final)
        orig2out[m] = final

    return out, orig2out


# ============================================================
# 2) STO reading helpers (Model Marker Locations from IK)
# ============================================================

def _find_data_start(lines: List[str]) -> int:
    for i, line in enumerate(lines):
        if line.strip().lower() == "endheader":
            return i + 1
    raise ValueError("endheader not found in STO file")


def extract_sto_markers_in_order(df_columns: List[str]) -> List[str]:
    """
    Extract marker base names in order of appearance in STO columns.
    STO has columns like: marker_tx marker_ty marker_tz
    """
    markers = []
    seen = set()
    for c in df_columns:
        if c.endswith("_tx"):
            m = c[:-3]
            if m not in seen:
                markers.append(m)
                seen.add(m)
    return markers


# ============================================================
# 3) Convert STO -> Trajectories 5-line CSV (with translation)
# ============================================================

def sto_2_csv(
    sto_path: str,
    out_csv_path: str,
    fps: int = 30,
    to_mm: bool = True,
    units: str = "mm",
    marker_mapping: Optional[Dict[str, str]] = None,
    collision_strategy: str = "suffix"
) -> str:
    """
    Convert OpenSim "Model Marker Locations from IK" STO to DLC-like Trajectories CSV
    and translate marker names during conversion.

    Output header (5 lines):
      1) Trajectories,,,,,
      2) fps,,,,,
      3) ,Marker1,,,Marker2,,,
      4) Frames,X,Y,Z,X,Y,Z,...
      5) ,mm,mm,mm,...

    Data rows:
      frame_index, x1,y1,z1,x2,y2,z2,...

    Notes:
      - Marker order preserved from STO column order
      - If to_mm=True, multiply coordinates by 1000 (m -> mm)
      - marker_mapping applied to marker base names BEFORE writing CSV
    """
    with open(sto_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    data_start = _find_data_start(lines)

    df = pd.read_csv(StringIO("".join(lines[data_start:])), sep=r"\s+", engine="python")
    if "time" not in df.columns:
        df = df.rename(columns={df.columns[0]: "time"})

    markers_orig = extract_sto_markers_in_order(list(df.columns))
    if len(markers_orig) == 0:
        raise ValueError("No markers found in STO (expected *_tx/_ty/_tz columns).")

    # translate names (preserve order)
    markers_out, orig2out = translate_markers(
        markers_orig,
        mapping=marker_mapping,
        keep_unmapped=True,
        collision_strategy=collision_strategy
    )

    nM = len(markers_orig)
    nF = int(df.shape[0])

    # frames: 0..N-1 (与你 read_csv_data 时间重建兼容)
    frames = np.arange(nF, dtype=int)

    # Build data matrix
    total_cols = 1 + 3 * nM
    data = np.empty((nF, total_cols), dtype=float)
    data[:, 0] = frames

    col_idx = 1
    for m_orig in markers_orig:
        for suf in ("_tx", "_ty", "_tz"):
            c = m_orig + suf
            if c in df.columns:
                v = pd.to_numeric(df[c], errors="coerce").values.astype(float)
            else:
                v = np.full((nF,), np.nan, dtype=float)

            if to_mm:
                v = v * 1000.0

            data[:, col_idx] = v
            col_idx += 1

    # ----- write header -----
    def line_of(values: List[str]) -> str:
        if len(values) != total_cols:
            raise RuntimeError("Header line length mismatch.")
        return ",".join(values) + "\n"

    # line1
    line1 = ["Trajectories"] + [""] * (total_cols - 1)
    # line2
    line2 = [str(int(fps))] + [""] * (total_cols - 1)
    # line3: markers expanded (use translated names!)
    line3 = [""]
    for m_out in markers_out:
        line3 += [m_out, "", ""]
    line3 = line3[:total_cols]
    # line4
    line4 = ["Frames"]
    for _ in markers_out:
        line4 += ["X", "Y", "Z"]
    line4 = line4[:total_cols]
    # line5
    line5 = [""] + [units] * (total_cols - 1)

    os.makedirs(os.path.dirname(out_csv_path), exist_ok=True)

    with open(out_csv_path, "w", newline="") as f:
        f.write(line_of(line1))
        f.write(line_of(line2))
        f.write(line_of(line3))
        f.write(line_of(line4))
        f.write(line_of(line5))

        # data rows
        for i in range(nF):
            row = data[i, :]
            s = [str(int(row[0]))] + ["%.16f" % x if np.isfinite(x) else "" for x in row[1:]]
            f.write(",".join(s) + "\n")

    return out_csv_path


if __name__ == "__main__":

    sto_file = r"D:\Users\Etudiant\Documents\MOCAPIA5\mocapia_3\ProjectsFOLDERS\TestCalibProject_CJL\test_calib\analysis\CJL_mov1\kinematics\_ik_model_marker_locations.sto"
    out_csv = r"D:\Users\Etudiant\Documents\MOCAPIA5\mocapia_3\ProjectsFOLDERS\TestCalibProject_CJL\test_calib\analysis\CJL_mov1\CJL_mov1_3D_points_filt_butterworth_LSTM_IK.csv"

    sto_2_csv(sto_file, out_csv, fps=30, to_mm=True)

