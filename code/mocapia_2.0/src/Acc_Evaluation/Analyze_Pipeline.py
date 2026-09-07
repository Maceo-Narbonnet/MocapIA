# -*- coding: utf-8 -*-
import os
import pandas as pd
from typing import Optional, Dict, Tuple

from Acc_Evaluation.Path_utils import make_output_path
from Acc_Evaluation.Feature_Builder import Feature_Builder, SegmentDef, AngleDef
from Acc_Evaluation.Report_Analyzer import Report_Analyzer
from Acc_Evaluation.Sto_utils import sto_2_csv

SEGMENTS = [
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
        AngleDef("Left Knee Angle", "LHip", "LKnee", "LAnkle"),
        AngleDef("Right Knee Angle", "RHip", "RKnee", "RAnkle"),
        AngleDef("Left Elbow Angle", "LShoulder", "LElbow", "LWrist"),
        AngleDef("Right Elbow Angle", "RShoulder", "RElbow", "RWrist"),
        AngleDef("Left Hip Angle", "LShoulder", "LHip", "LKnee"),
        AngleDef("Right Hip Angle", "RShoulder", "RHip", "RKnee"),
    ]


class Analyze_Pipeline(object):
    """
    Orchestrates:
      raw_csv -> features (if missing) -> reports
    Also supports comparing multiple processed versions of the same trial:
      Raw / Butterworth / Butterworth+LSTM
    """

    def __init__(self, raw_csv_path: str):
        self.raw_csv_path = raw_csv_path

    # ------------------------------------------------------------
    # Ensure features exist (create if missing)
    # ------------------------------------------------------------
    def ensure_segment_lengths(self, segments, feature_csv_path: Optional[str] = None) -> Tuple[str, bool]:
        if feature_csv_path is None:
            feature_csv_path = make_output_path(self.raw_csv_path, kind="features", tag="segment_lengths")

        if os.path.exists(feature_csv_path):
            return feature_csv_path, False  # (path, created_now?)

        builder = Feature_Builder(self.raw_csv_path).load()
        _, out_path = builder.export_segment_lengths(segments, csv_out_path=feature_csv_path)
        return out_path, True

    def ensure_joint_angles(self, angles, feature_csv_path: Optional[str] = None) -> Tuple[str, bool]:
        if feature_csv_path is None:
            feature_csv_path = make_output_path(self.raw_csv_path, kind="features", tag="angles")

        if os.path.exists(feature_csv_path):
            return feature_csv_path, False

        builder = Feature_Builder(self.raw_csv_path).load()
        _, out_path = builder.export_joint_angles(angles, csv_out_path=feature_csv_path)
        return out_path, True

    # ------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------
    def segment_report(self,
                       segments,
                       names=None, pairs=None, keywords=None,
                       report_tag: Optional[str] = None,
                       report_csv_path: Optional[str] = None):
        """
        Segment-length stability report (uses make_segment_report).
        """
        feature_path, created = self.ensure_segment_lengths(segments)

        analyzer = Report_Analyzer(feature_path, raw_csv_path=self.raw_csv_path).load()
        rep = analyzer.make_segment_report(names=names, pairs=pairs, keywords=keywords)

        if report_tag is None:
            report_tag = "segment_report"

        out = analyzer.export_report(rep, report_tag=report_tag, csv_out_path=report_csv_path)
        return rep, out, feature_path, created

    def angle_quality(self,
                      angles,
                      fps: float,
                      names=None, triplets=None, keywords=None,
                      report_tag: Optional[str] = None,
                      report_csv_path: Optional[str] = None,
                      hf_low: float = 10.0,
                      hf_high: Optional[float] = 20.0,
                      total_low: float = 0.5):
        """
        Angle quality report (time + frequency):
          - out_of_range_ratio
          - rms_velocity, rms_acceleration
          - dominant_freq_hz
          - hf_energy_ratio

        NOTE: For fps=30, Nyquist=15 -> recommend hf_high=15 or None.
        """
        feature_path, created = self.ensure_joint_angles(angles)

        analyzer = Report_Analyzer(feature_path, raw_csv_path=self.raw_csv_path).load()

        rep = analyzer.angle_quality_report(
            fps=fps,
            names=names,
            pairs=triplets,     # triplets mapped to pairs param
            keywords=keywords,
            total_low=total_low,
            hf_low=hf_low,
            hf_high=hf_high
        )

        if report_tag is None:
            report_tag = "angle_quality"

        out = analyzer.export_report(rep, report_tag=report_tag, csv_out_path=report_csv_path)
        return rep, out, feature_path, created
    
    def segment_quality(self,
                    segments,
                    names=None, pairs=None, keywords=None,
                    report_tag: Optional[str] = None,
                    report_csv_path: Optional[str] = None):
        """
        Segment length stability report (based on precomputed segment_lengths feature).
        Output columns come from Report_Analyzer.make_segment_report:
        name, pair, valid_ratio, n_valid, mean, std, cv, median, mad, p05, p95, ...
        """
        feature_path, created = self.ensure_segment_lengths(segments)

        analyzer = Report_Analyzer(feature_path, raw_csv_path=self.raw_csv_path).load()
        rep = analyzer.make_segment_report(names=names, pairs=pairs, keywords=keywords)

        if report_tag is None:
            report_tag = "segment_report"

        out = analyzer.export_report(rep, report_tag=report_tag, csv_out_path=report_csv_path)
        return rep, out, feature_path, created

    @staticmethod
    def _parse_fps_from_csv_header(csv_path, default_fps=60):
        """
        Works for both:
          - old MoCapIA 5-line header: line2 = "30"
          - Trajectories header: line2 = "30,,,,"
        """
        try:
            with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
                _ = f.readline()            # line1
                line2 = f.readline().strip()  # line2
            # take first cell before comma
            fps = int(line2.split(",")[0].strip())
            return fps if fps > 0 else default_fps
        except Exception:
            return default_fps

    @staticmethod
    def _ik_sto_path_from_folder(folder, base_name):
        """
        According to your rule:
          .../<base_name>/kinematics/_ik_model_marker_locations.sto
        """
        return os.path.join(folder, "kinematics", "_ik_model_marker_locations.sto")

    @staticmethod
    def _ik_csv_path_from_lstm_csv(lstm_csv_path):
        """
        If lstm_csv_path ends with ..._LSTM.csv => ..._LSTM_IK.csv
        If already ..._IK.csv => itself
        """
        if lstm_csv_path.endswith("_IK.csv"):
            return lstm_csv_path
        if lstm_csv_path.endswith(".csv"):
            return lstm_csv_path[:-4] + "_IK.csv"
        return lstm_csv_path + "_IK.csv"
    @staticmethod
    def ensure_ik_csv(folder, base_name, lstm_csv_path, overwrite=False):
        """
        Ensure IK CSV exists by converting STO if needed.

        Args:
          folder: trial folder (where Raw/Butter/LSTM csv are)
          base_name: e.g. "CJL_mov1"
          lstm_csv_path: path of ..._filt_butterworth_LSTM.csv
          overwrite: if True, regenerate IK CSV even if exists

        Returns:
          ik_csv_path (str) or None if STO not found
        """
        ik_csv_path = Analyze_Pipeline._ik_csv_path_from_lstm_csv(lstm_csv_path)

        if (not overwrite) and os.path.exists(ik_csv_path):
            return ik_csv_path

        sto_path = Analyze_Pipeline._ik_sto_path_from_folder(folder, base_name)
        if not os.path.exists(sto_path):
            # STO absent => cannot create IK csv
            return None

        # fps: prefer parse from LSTM CSV header (so IK aligns with that pipeline)
        fps = Analyze_Pipeline._parse_fps_from_csv_header(lstm_csv_path, default_fps=60)

        # Convert STO -> Trajectories CSV (with translation + m->mm)
        sto_2_csv(
            sto_path=sto_path,
            out_csv_path=ik_csv_path,
            fps=fps,
            to_mm=True
        )
        return ik_csv_path

    # ------------------------------------------------------------
    # Multi-version comparison (Raw / Butterworth / Butterworth+LSTM)
    # ------------------------------------------------------------
    @staticmethod
    def find_versions_in_folder(folder, base_name, auto_ik=True, overwrite_ik=False):
        """
        Returns dict {version_name: csv_path}
          version_name in: Raw, Butterworth, Butterworth+LSTM, IK
        """
        versions = {}

        # 1) scan csvs
        for fn in os.listdir(folder):
            if not fn.endswith(".csv"):
                continue
            if base_name not in fn:
                continue

            full = os.path.join(folder, fn)

            # IK
            if fn.endswith("_IK.csv"):
                versions["IK"] = full
                continue

            # LSTM
            if "_3D_points_filt_butterworth_LSTM" in fn:
                versions["Butterworth+LSTM"] = full
                continue

            # Butterworth
            if "_3D_points_filt_butterworth" in fn:
                versions["Butterworth"] = full
                continue

            # Raw
            if fn.endswith("_3D_points.csv"):
                versions["Raw"] = full
                continue

        # 2) auto-create IK from STO if requested
        if auto_ik and ("IK" not in versions) and ("Butterworth+LSTM" in versions):
            ik_csv = Analyze_Pipeline.ensure_ik_csv(
                folder=folder,
                base_name=base_name,
                lstm_csv_path=versions["Butterworth+LSTM"],
                overwrite=overwrite_ik
            )
            if ik_csv is not None and os.path.exists(ik_csv):
                versions["IK"] = ik_csv

        return versions



    @staticmethod
    def compare_three_versions_angles(folder: str,
                            base_name: str,
                            angles,
                            fps: float,
                            hf_low: float = 10.0,
                            hf_high: Optional[float] = None,
                            total_low: float = 0.5,
                            save: bool = True):
        """
        Compare angle quality across Raw / Butterworth / Butterworth+LSTM.

        Output (single file if save=True):
        folder/compare_angle_quality.csv

        The output is a pivot-style CSV with MultiIndex columns:
        - first header row: metric names (mean, min, max, ...)
        - second header row: version names (Raw, Butterworth, Butterworth+LSTM)
        Left side includes 'triplet' column (meta) + index 'name'.

        Returns:
        df_compare (DataFrame with MultiIndex columns), saved_path
        """
        versions = Analyze_Pipeline.find_versions_in_folder(folder, base_name)
        if not versions:
            raise FileNotFoundError(
                "No matching files found for base_name=%s in folder=%s" % (base_name, folder)
            )

        # ---- enforce strict order ----
        version_order = ["Raw", "Butterworth", "Butterworth+LSTM", "IK"]
        ordered_versions = [(v, versions[v]) for v in version_order if v in versions]

        if not ordered_versions:
            raise FileNotFoundError("None of Raw/Butterworth/Butterworth+LSTM found for base_name=%s" % base_name)

        all_reports = []

        for version_name, raw_csv_path in ordered_versions:
            pipe = Analyze_Pipeline(raw_csv_path)

            # For fps, Nyquist protection for hf_high
            nyq = float(fps) / 2.0
            _hf_high = hf_high
            if _hf_high is None:
                _hf_high = nyq
            else:
                _hf_high = min(float(_hf_high), nyq)

            report_tag = "angle_quality__%s" % version_name.replace("+", "_").replace(" ", "_")

            rep, out_report, feat_path, created = pipe.angle_quality(
                angles=angles,
                fps=fps,
                report_tag=report_tag,
                hf_low=hf_low,
                hf_high=_hf_high,
                total_low=total_low
            )

            # attach version
            rep = rep.copy()
            rep["version"] = version_name

            # NOTE: we do NOT keep paths/debug cols in final compare
            all_reports.append(rep)

        # ---- stack ----
        df_long = pd.concat(all_reports, ignore_index=True)

        # ---- remove columns we do NOT want in compare ----
        drop_cols = ["raw_csv", "feature_csv", "report_csv", "feature_created_now"]
        for c in drop_cols:
            if c in df_long.columns:
                df_long = df_long.drop(columns=[c])

        # ---- decide which columns are "metrics" to pivot ----
        # everything except name/triplet/version is treated as metric
        base_cols = ["name", "triplet", "version"]
        metric_cols = [c for c in df_long.columns if c not in base_cols]

        # ---- meta on the left: triplet (one per name) ----
        meta = (
            df_long[["name", "triplet"]]
            .drop_duplicates(subset=["name"])
            .set_index("name")
        )

        # pivot
        df_pivot = df_long.pivot_table(
            index="name",
            columns="version",
            values=metric_cols,
            aggfunc="first"
        )

        # enforce version order
        version_order = ["Raw", "Butterworth", "Butterworth+LSTM", "IK"]
        existing = [v for v in version_order if v in df_pivot.columns.levels[1]]
        df_pivot = df_pivot.reindex(columns=existing, level=1)

        # add triplet without breaking MultiIndex
        triplet_map = (
            df_long[["name", "triplet"]]
            .drop_duplicates(subset=["name"])
            .set_index("name")
        )
        output_dir = os.path.join(folder, "outputs")

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        df_compare = df_pivot.copy()
        df_compare.insert(0, "triplet", triplet_map["triplet"])

        # save
        saved_path = os.path.join(output_dir, "compare_angle_quality.csv")
        df_compare.to_csv(saved_path)

        return df_compare, saved_path
    
    @staticmethod
    def compare_three_versions_segments(folder: str,
                                    base_name: str,
                                    segments,
                                    save: bool = True):
        """
        Compare segment length report across Raw / Butterworth / Butterworth+LSTM.

        Output: pivot-style CSV with MultiIndex columns:
        - first header row: metric (mean, std, cv, ...)
        - second header row: version (Raw, Butterworth, Butterworth+LSTM)

        Saved path (if save=True):
        folder/outputs/compare_segment_report.csv

        Returns:
        df_compare, saved_path
        """
        versions = Analyze_Pipeline.find_versions_in_folder(folder, base_name)
        if not versions:
            raise FileNotFoundError(
                "No matching files found for base_name=%s in folder=%s" % (base_name, folder)
            )

        # strict order
        version_order = ["Raw", "Butterworth", "Butterworth+LSTM", "IK"]
        ordered_versions = [(v, versions[v]) for v in version_order if v in versions]
        if not ordered_versions:
            raise FileNotFoundError("None of Raw/Butterworth/Butterworth+LSTM found for base_name=%s" % base_name)

        all_reports = []

        for version_name, raw_csv_path in ordered_versions:
            pipe = Analyze_Pipeline(raw_csv_path)

            report_tag = "segment_report__%s" % version_name.replace("+", "_").replace(" ", "_")

            rep, out_report, feat_path, created = pipe.segment_quality(
                segments=segments,
                report_tag=report_tag
            )

            rep = rep.copy()
            rep["version"] = version_name
            all_reports.append(rep)

        df_long = pd.concat(all_reports, ignore_index=True)

        # drop unwanted/debug columns if any
        drop_cols = ["raw_csv", "feature_csv", "report_csv", "feature_created_now"]
        for c in drop_cols:
            if c in df_long.columns:
                df_long = df_long.drop(columns=[c])

        # everything except name/pair/version is metric
        base_cols = ["name", "pair", "version"]
        metric_cols = [c for c in df_long.columns if c not in base_cols]

        # meta on the left: pair (segment endpoints)
        pair_map = (
            df_long[["name", "pair"]]
            .drop_duplicates(subset=["name"])
            .set_index("name")
        )

        # pivot all metrics
        df_pivot = df_long.pivot_table(
            index="name",
            columns="version",
            values=metric_cols,
            aggfunc="first"
        )

        # enforce version order
        existing = [v for v in version_order if v in df_pivot.columns.levels[1]]
        df_pivot = df_pivot.reindex(columns=existing, level=1)

        # build final compare WITHOUT breaking MultiIndex
        df_compare = df_pivot.copy()
        df_compare.insert(0, "pair", pair_map["pair"])

        saved_path = None
        if save:
            output_dir = os.path.join(folder, "outputs")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            saved_path = os.path.join(output_dir, "compare_segment_report.csv")
            df_compare.to_csv(saved_path)  # keeps multi-row headers
            print("Saved:", saved_path)

        return df_compare, saved_path




# ------------------------------------------------------------
# MAIN TEST
# ------------------------------------------------------------
if __name__ == "__main__":
    # Example for CJL_mov1
    folder = r"D:\Users\Etudiant\Documents\MOCAPIA5\mocapia_3\ProjectsFOLDERS\AF3_CJL\AF6\analysis\SLOW"
    base_name = "SLOW"
    fps = 30  # set correctly

    # For fps=30, Nyquist=15 -> hf_high should be <= 15
    df_compare, saved = Analyze_Pipeline.compare_three_versions_angles(
        folder=folder,
        base_name=base_name,
        angles=ANGLES,
        fps=fps,
        hf_low=7.0,
        hf_high=15.0,
        total_low=0.5,
        save=True
    )

    print(df_compare)
    print("Saved:", saved)


    df_seg_compare, path_seg = Analyze_Pipeline.compare_three_versions_segments(
        folder=folder,
        base_name=base_name,
        segments=SEGMENTS,
        save=True
    )

    print(df_seg_compare)
    print("Saved:", path_seg)


