# -*- coding: utf-8 -*-
import os
import re
import numpy as np
import pandas as pd
from typing import List, Optional, Dict, Any
from Acc_Evaluation.Path_utils import make_output_path

ANGLE_RANGE_DB = {
    "Knee":  (0, 160),
    "Elbow": (0, 150),
    "Hip":   (0, 150),
}


class Report_Analyzer(object):
    """
    Analyze precomputed feature CSVs (fast stage).
    For segment_lengths.csv:
      columns = Frames, Time, <name>__<a>-<b>
    """

    def __init__(self, feature_csv_path, raw_csv_path=None):
        self.feature_csv_path = feature_csv_path
        self.raw_csv_path = raw_csv_path
        self.df = None

    def load(self):
        self.df = pd.read_csv(self.feature_csv_path)
        return self

    def _ensure_loaded(self):
        if self.df is None:
            raise RuntimeError("Not loaded. Call .load() first.")

    # --------------------------
    # Selection utilities
    # --------------------------
    def list_available_segments(self) -> List[str]:
        """Return all segment columns (excluding Frames/Time)."""
        self._ensure_loaded()
        return [c for c in self.df.columns if c not in ["Frames", "Time"]]

    @staticmethod
    def _parse_segment_col(col_name):
        """
        Parse "<name>__<a>-<b>" into dict.
        If pattern doesn't match, returns name=col_name.
        """
        if "__" in col_name:
            left, right = col_name.split("__", 1)
            return {"name": left, "pair": right, "col": col_name}
        return {"name": col_name, "pair": "", "col": col_name}

    def _filter_by_names(self, wanted_names: List[str]) -> List[str]:
        wanted = set([w.strip() for w in wanted_names if w.strip()])
        cols = self.list_available_segments()
        out = []
        for c in cols:
            info = self._parse_segment_col(c)
            if info["name"] in wanted:
                out.append(c)
        return out

    def _filter_by_pairs(self, wanted_pairs: List[str]) -> List[str]:
        """
        wanted_pairs examples:
          - "LHip-LKnee"
          - "LKnee-LAnkle"
          - order-insensitive if user writes "LAnkle-LKnee"
        """
        wanted_norm = set()
        for p in wanted_pairs:
            p = p.strip()
            if "-" not in p:
                continue
            a, b = p.split("-", 1)
            a, b = a.strip(), b.strip()
            wanted_norm.add("%s-%s" % (a, b))
            wanted_norm.add("%s-%s" % (b, a))  # order-insensitive

        cols = self.list_available_segments()
        out = []
        for c in cols:
            info = self._parse_segment_col(c)
            if info["pair"] in wanted_norm:
                out.append(c)
        return out

    def _filter_by_keywords(self, keywords: List[str]) -> List[str]:
        """
        Match keywords against the full column string.
        Example keywords: ["Shank", "Width", "Forearm", "Shoulder"]
        """
        keys = [k.strip().lower() for k in keywords if k.strip()]
        cols = self.list_available_segments()
        out = []
        for c in cols:
            s = c.lower()
            ok = True
            for k in keys:
                if k not in s:
                    ok = False
                    break
            if ok:
                out.append(c)
        return out

    def select_segments(
        self,
        names=None,
        pairs=None,
        keywords=None
    ):
        """
        Combine selection modes (union).
        If nothing specified -> return ALL segments.
        """

        self._ensure_loaded()

        all_cols = self.list_available_segments()

        # If user passed nothing OR all empty → analyze all
        if not names and not pairs and not keywords:
            return all_cols

        selected = set()

        if names:
            for c in self._filter_by_names(names):
                selected.add(c)

        if pairs:
            for c in self._filter_by_pairs(pairs):
                selected.add(c)

        if keywords:
            for c in self._filter_by_keywords(keywords):
                selected.add(c)

        # If user gave something but nothing matched → warn and return empty
        if len(selected) == 0:
            print("⚠ Warning: No segment matched selection.")
            return []

        # Keep original CSV order
        ordered = [c for c in all_cols if c in selected]
        return ordered

    # --------------------------
    # Reporting
    # --------------------------
    @staticmethod
    def _stats_from_array(arr: np.ndarray) -> Dict[str, Any]:
        ok = np.isfinite(arr)
        if ok.sum() == 0:
            return {
                "valid_ratio": 0.0,
                "n_valid": 0,
                "mean": np.nan,
                "std": np.nan,
                "cv": np.nan,
                "median": np.nan,
                "mad": np.nan,
                "p05": np.nan,
                "p95": np.nan,
            }

        v = arr[ok]
        mean = float(np.mean(v))
        std = float(np.std(v, ddof=1)) if v.size > 1 else 0.0
        cv = float(std / mean) if mean != 0 else np.nan
        median = float(np.median(v))
        mad = float(np.median(np.abs(v - median)))

        return {
            "valid_ratio": float(ok.mean()),
            "n_valid": int(ok.sum()),
            "mean": mean,
            "std": std,
            "cv": cv,
            "median": median,
            "mad": mad,
            "p05": float(np.percentile(v, 5)),
            "p95": float(np.percentile(v, 95)),
        }

    def make_segment_report(
        self,
        names=None,
        pairs=None,
        keywords=None,
        save_csv=False,
        csv_out_path=None
    ):
        """
        Create a report for selected segments.
        If nothing specified → analyze ALL.
        """

        self._ensure_loaded()

        cols = self.select_segments(names=names, pairs=pairs, keywords=keywords)

        if len(cols) == 0:
            print("No segments selected.")
            return pd.DataFrame()

        rows = []
        for col in cols:
            arr = pd.to_numeric(self.df[col], errors="coerce").values
            info = self._parse_segment_col(col)
            s = self._stats_from_array(arr)

            rows.append({
                "name": info["name"],
                "pair": info["pair"],
                **s
            })

        rep = pd.DataFrame(rows).sort_values(by="cv", ascending=True, na_position="last")

        if save_csv:
            if csv_out_path is None:
                raise ValueError("csv_out_path must be provided when save_csv=True")
            folder = os.path.dirname(csv_out_path)
            if folder and (not os.path.exists(folder)):
                os.makedirs(folder)
            rep.to_csv(csv_out_path, index=False)

        return rep
    @staticmethod
    def _get_angle_range(angle_name):
        for key, val in ANGLE_RANGE_DB.items():
            if key.lower() in angle_name.lower():
                return val
        return None
    
    def _get_angle_range(self, angle_name):
        """
        Infer range from angle_name using ANGLE_RANGE_DB keys.
        Example: 'Left Knee Angle' -> (0,160)
        """
        low = angle_name.lower()
        for joint, rng in ANGLE_RANGE_DB.items():
            if joint.lower() in low:
                return rng
        return None
    
    def _prep_signal_for_fft(self, theta_all):
        """
        theta_all: np.ndarray with NaNs
        Return: clean np.ndarray without NaNs (interpolated), demeaned
        """
        x = np.asarray(theta_all, dtype=float)
        n = x.shape[0]
        idx = np.arange(n)

        ok = np.isfinite(x)
        if ok.sum() < 3:
            return None

        # linear interpolation to fill NaNs
        x_filled = x.copy()
        x_filled[~ok] = np.interp(idx[~ok], idx[ok], x[ok])

        # remove mean (reduce DC)
        x_filled = x_filled - np.mean(x_filled)
        return x_filled
    
    def _hf_energy_ratio(self, x, fps, total_low=0.5, hf_low=10.0, hf_high=None):
        """
        x: clean signal (no NaNs), demeaned
        Return: (hf_ratio, dom_freq, total_power, hf_power)
        """
        n = x.shape[0]
        if n < 8:
            return (np.nan, np.nan, np.nan, np.nan)

        # window to reduce spectral leakage
        w = np.hanning(n)
        xw = x * w

        # rFFT
        X = np.fft.rfft(xw)
        freqs = np.fft.rfftfreq(n, d=1.0 / float(fps))

        # power spectrum
        P = (np.abs(X) ** 2)

        nyq = float(fps) / 2.0
        if hf_high is None:
            hf_high = nyq

        # masks
        total_mask = (freqs >= total_low) & (freqs <= nyq)
        hf_mask = (freqs >= hf_low) & (freqs <= hf_high)

        total_power = float(np.sum(P[total_mask])) if np.any(total_mask) else np.nan
        hf_power = float(np.sum(P[hf_mask])) if np.any(hf_mask) else np.nan

        if not np.isfinite(total_power) or total_power <= 0:
            hf_ratio = np.nan
        else:
            hf_ratio = float(hf_power / total_power)

        # dominant frequency in movement band (e.g. 0.5-5 Hz) is sometimes useful
        # Here we choose dom_freq as max power within total_mask but above total_low
        if np.any(total_mask):
            k = np.argmax(P[total_mask])
            dom_freq = float(freqs[total_mask][k])
        else:
            dom_freq = np.nan

        return (hf_ratio, dom_freq, total_power, hf_power)
    





    def angle_quality_report(
        self,
        fps,
        names=None,
        pairs=None,
        keywords=None,
        total_low=0.5,
        hf_low=10.0,
        hf_high=20.0
    ):
        """
        Combined time-domain + frequency-domain quality report for joint angles.

        Time-domain:
        - mean/min/max
        - out_of_range_ratio
        - rms_velocity, rms_acceleration
        - valid_ratio, n_valid

        Frequency-domain:
        - dominant_freq_hz
        - hf_energy_ratio (hf band / total band)

        Selection:
        If names/pairs/keywords empty -> analyze all angle columns.
        """
        self._ensure_loaded()

        dt = 1.0 / float(fps)

        if names or pairs or keywords:
            angle_cols = self.select_segments(names=names, pairs=pairs, keywords=keywords)
        else:
            angle_cols = [c for c in self.df.columns if c not in ["Frames", "Time"]]

        rows = []
        for col in angle_cols:
            info = self._parse_segment_col(col)
            angle_name = info["name"]
            triplet = info["pair"]

            theta_all = pd.to_numeric(self.df[col], errors="coerce").values
            ok = np.isfinite(theta_all)
            n_valid = int(ok.sum())
            valid_ratio = float(ok.mean()) if theta_all.size > 0 else np.nan

            if n_valid < 3:
                continue

            theta = theta_all[ok]

            # ---- time-domain dynamics ----
            vel = np.diff(theta) / dt
            acc = np.diff(vel) / dt

            rms_vel = float(np.sqrt(np.mean(vel ** 2))) if vel.size > 0 else np.nan
            rms_acc = float(np.sqrt(np.mean(acc ** 2))) if acc.size > 0 else np.nan

            # ---- range check ----
            rng = self._get_angle_range(angle_name)
            if rng is None:
                phys_min, phys_max = np.nan, np.nan
                out_ratio = np.nan
            else:
                phys_min, phys_max = float(rng[0]), float(rng[1])
                out_ratio = float(np.mean((theta < phys_min) | (theta > phys_max)))

            # ---- frequency-domain ----
            x = self._prep_signal_for_fft(theta_all)  # uses full series with interpolation
            if x is None:
                hf_ratio, dom_freq, total_p, hf_p= np.nan, np.nan, np.nan, np.nan
            else:
               hf_ratio, dom_freq, total_p, hf_p= self._hf_energy_ratio(
                    x, fps=fps, total_low=total_low, hf_low=hf_low, hf_high=hf_high
                )

            rows.append({
                "name": angle_name,
                "triplet": triplet,

                "mean": float(np.mean(theta)),
                "min": float(np.min(theta)),
                "max": float(np.max(theta)),

                "physio_min": phys_min,
                "physio_max": phys_max,
                "out_of_range_ratio": out_ratio,

                "rms_velocity": rms_vel,
                "rms_acceleration": rms_acc,

                "dominant_freq_hz": dom_freq,
                "hf_energy_ratio": hf_ratio,
                "hf_band_hz": "%.1f-%.1f" % (float(hf_low), float(hf_high)),
                "total_low_hz": float(total_low),
                "total_power": total_p,
                "hf_power": hf_p,


                "valid_ratio": valid_ratio,
                "n_valid": n_valid,
            })

        dfq = pd.DataFrame(rows)

        # sort: low out_of_range, low hf_ratio, then low rms_acc
        if not dfq.empty:
            dfq = dfq.sort_values(
                by=["out_of_range_ratio", "hf_energy_ratio", "rms_acceleration"],
                ascending=[True, True, True],
                na_position="last"
            )

        return dfq

    
    def export_report(self, report_df, report_tag, csv_out_path=None):
        if csv_out_path is None:
            if self.raw_csv_path is None:
                raise ValueError("raw_csv_path is required to auto-generate report path.")
            csv_out_path = make_output_path(self.raw_csv_path, kind="reports", tag=report_tag)
        folder = os.path.dirname(csv_out_path)
        if folder and (not os.path.exists(folder)):
            os.makedirs(folder)
        report_df.to_csv(csv_out_path, index=False)
        return csv_out_path


if __name__ == "__main__":
    raw_csv = r"D:\Users\Etudiant\Documents\MOCAPIA5\mocapia_3\ProjectsFOLDERS\TestCalibProject_CJL\test_calib\analysis\CJL_mov1\CJL_mov1_3D_points.csv"

    # 这里是“特征文件路径”，也改成自动生成（不会打架）
    segement_feature_csv = make_output_path(raw_csv, kind="features", tag="segment_lengths")

    segment_analyzer = Report_Analyzer(feature_csv_path=segement_feature_csv, raw_csv_path=raw_csv).load()

    rep_segment = segment_analyzer.make_segment_report()  
    out_segment_report = segment_analyzer.export_report(rep_segment, report_tag="segment_report")
    
    angle_feature_csv = make_output_path(raw_csv, kind="features", tag="angles")
    angle_analyzer = Report_Analyzer(feature_csv_path=angle_feature_csv, raw_csv_path=raw_csv).load()
    rep_angle = angle_analyzer.angle_quality_report(fps=30)
    out_angle_report = angle_analyzer.export_report(rep_angle, report_tag="angle_quality_report")

    print("Segment Report:", out_segment_report)
    print(rep_segment.to_string(index=False))
    print("\nAngle Quality Report:")
    print(rep_angle.to_string(index=False))