# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime

def make_output_path(raw_csv_path,
                       kind,          # "features" or "reports"
                       tag,           # "segment_lengths" / "joint_angles" / "segment_report" / "angle_report"
                       out_dir="outputs",
                       ext=".csv",
                       with_timestamp=False):
    """
    Generates a non-conflicting output file path based on raw CSV path.

    Example:
      raw: .../analysis/CJL_mov1/CJL_mov1_3D_points.csv
      ->  .../analysis/CJL_mov1/outputs/features/CJL_mov1_3D_points__segment_lengths.csv
      ->  .../analysis/CJL_mov1/outputs/reports/CJL_mov1_3D_points__angle_report.csv
    """
    raw_path = Path(raw_csv_path)
    base = raw_path.stem  # "CJL_mov1_3D_points"

    out_dir_path = raw_path.parent / out_dir / kind
    out_dir_path.mkdir(parents=True, exist_ok=True)

    if with_timestamp:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = "%s__%s__%s%s" % (base, tag, ts, ext)
    else:
        filename = "%s__%s%s" % (base, tag, ext)

    return str(out_dir_path / filename)
