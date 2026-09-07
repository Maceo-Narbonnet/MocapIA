# # services/ai_analysis_service.py
# from PyQt5.QtCore import QObject, pyqtSignal
# from Ui.threads.RTMPoseThread import RTMPoseThread
# import os

# class AIAnalysisService(QObject):
#     """Thin wrapper around RTMPoseThread. No UI here."""
#     started  = pyqtSignal(str, str)      # (experiment, capture)
#     progress = pyqtSignal(int, int)      # (current, total)
#     failed   = pyqtSignal(str)           # message
#     finished = pyqtSignal(str, str)      # (experiment, capture)
#     cancelled = pyqtSignal(str, str)      # (experiment, capture)

#     def __init__(self, ctx, parent=None):
#         super().__init__(parent)
#         self.ctx = ctx
#         self._thread = None

#     def start(self, experiment: str, capture: str):
#         # stop previous if still running
#         if self._thread and getattr(self._thread, "isRunning", lambda: False)():
#             self.stop()

#         # ensure output dir exists: <project>/<experiment>/analysis/<capture>
#         try:
#             base = getattr(self.ctx, "project_path", "")
#             outdir = os.path.join(base, experiment, "analysis", capture)
#             os.makedirs(outdir, exist_ok=True)
#         except Exception:
#             pass

#         th = RTMPoseThread(experiment, capture)
#         self._thread = th

#         # wire thread signals to service signals (if available)
#         if hasattr(th, "progress3d"):
#             th.progress3d.connect(self.progress.emit)
#         if hasattr(th, "failed"):
#             th.failed.connect(self.failed.emit)
#         def _relay_finish():
#             try:
#                 if getattr(th, "was_cancelled", False):
#                     self.cancelled.emit(experiment, capture)
#                 else:
#                     self.finished.emit(experiment, capture)
#             finally:
#                 if self._thread is th:
#                     self._thread = None

#         th.finished.connect(_relay_finish)

#         self.started.emit(experiment, capture)
#         th.start()

#     def stop(self):
#         th = self._thread
#         self._thread = None
#         if th and hasattr(th, "cancel"):
#             try:
#                 th.cancel()
#             except Exception:
#                 pass
from PyQt5.QtCore import QObject, pyqtSignal
import os

# --- Adjust these imports according to your real project structure ---
from Ui.threads.RTMPoseThread import RTMPoseThread
from Ui.threads.FilteringThread import FilteringThread
from Ui.threads.markerAugmentationThread import MarkerAugmentationThread
from threads.kinematicsThread import KinematicsThread

from config.Config_Manager import ConfigManager
from Pose_Estimation.csv_utils import csv_to_trc
from Pose_Estimation.trc_utils import convert_trc_to_opensim
from Pose_Estimation.change_ref_pipeline import apply_T_to_csv

class AIAnalysisService(QObject):
    """
    Full AI pipeline orchestrator:
    RTMPose → Filtering → Augmentation → TRC → OpenSim → Pose2Sim IK → (optional RRA)
    """

    started  = pyqtSignal(str, str)
    progress = pyqtSignal(int, int)
    failed   = pyqtSignal(str)
    finished = pyqtSignal(str, str)
    cancelled = pyqtSignal(str, str)

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx

        self._rt_thread = None
        self._filtering_thread = None
        self._augmentation_thread = None
        self._kinematics_thread = None

        self.conda_env_name = "Pose2Sim"   # your Pose2Sim conda env
        self.rra_enabled = False           # enable RRA or not

        self._current_experiment = ""
        self._current_capture = ""

        self.logger = getattr(ctx, "logger", None)


    # ==========================================================
    # MAIN ENTRY POINT
    # ==========================================================

    def start(self, experiment: str, capture: str):
        """Start full pipeline."""
        self._current_experiment = experiment
        self._current_capture = capture

        self.stop()

        base = getattr(self.ctx, "project_path", "")
        outdir = os.path.join(base, experiment, "analysis", capture)
        os.makedirs(outdir, exist_ok=True)

        # --- already_done logic ---
        cfg = ConfigManager()
        already_done = bool(cfg.config_data.get("RTMPose_triangulation", {}).get("already_done", False))

        if already_done:
            if self._start_from_existing_csv(experiment, capture):
                self.started.emit(experiment, capture)
                return

        # otherwise → run RTMPose
        self.started.emit(experiment, capture)
        self._start_rtmpose(experiment, capture)


    def stop(self):
        """Cancel all running threads in the pipeline."""
        for attr in ("_rt_thread", "_filtering_thread", "_augmentation_thread", "_kinematics_thread"):
            th = getattr(self, attr, None)
            setattr(self, attr, None)
            if th and hasattr(th, "cancel"):
                try:
                    th.cancel()
                except Exception:
                    pass


    # ==========================================================
    # UTILITIES
    # ==========================================================

    def _log(self, msg: str):
        if self.logger:
            self.logger.info(msg)
        else:
            print(msg)

    def _is_alive(self, th):
        return th and hasattr(th, "isRunning") and th.isRunning()


    # ==========================================================
    # STEP 1 — RTMPose
    # ==========================================================

    def _start_rtmpose(self, experiment, capture):
        th = RTMPoseThread(experiment, capture)
        self._rt_thread = th

        if hasattr(th, "progress3d"):
            th.progress3d.connect(self.progress.emit)

        th.failed.connect(self._on_rtmpose_failed)

        def _finish():
            if getattr(th, "was_cancelled", False):
                self.cancelled.emit(experiment, capture)
            else:
                self._on_rtmpose_finished(experiment, capture)

        th.finished.connect(_finish)
        th.start()


    def _on_rtmpose_failed(self, msg):
        self.failed.emit(msg)


    def _on_rtmpose_finished(self, experiment, capture):
        self._log("[RTMPOSE] finished.")
        self._start_filtering_from_analysis_dir(experiment, capture)


    # ==========================================================
    # STEP 0 — already_done CSV
    # ==========================================================
    def _start_from_existing_csv(self, experiment, capture):
        base = getattr(self.ctx, "project_path", "")
        adir = os.path.join(base, experiment, "analysis", capture)

        # search for 3D CSV
        csvs = [
            f for f in os.listdir(adir)
            if f.lower().endswith(".csv") and "3d_points" in f.lower()
        ]

        if not csvs:
            self.failed.emit(f"'already_done' is True but no CSV found in {adir}")
            return False

        csv_path = os.path.join(adir, csvs[0])

        # ----------------------------------
        # ✅ NEW: change_ref guard
        # ----------------------------------
        original_csv = os.path.splitext(csv_path)[0] + "_original.csv"

        if not os.path.isfile(original_csv):
            self._log("[ChangeRef] original CSV not found → applying T")

            try:
                apply_T_to_csv(
                    project_path=base,
                    experiment_name=experiment,
                    capture_name=capture
                )
            except Exception as e:
                self.failed.emit(f"ChangeRef error:\n{e}")
                return False
        else:
            self._log("[ChangeRef] original CSV exists → skip apply_T")

        # continue pipeline（Filtering）
        self._log(f"[POSE] Using existing CSV: {csv_path}")
        self._start_filtering(csv_path)
        return True

    # ==========================================================
    # STEP 2 — FILTERING
    # ==========================================================

    def _start_filtering_from_analysis_dir(self, experiment, capture):
        base = getattr(self.ctx, "project_path", "")
        adir = os.path.join(base, experiment, "analysis", capture)

        csvs = [f for f in os.listdir(adir)
                if f.lower().endswith(".csv") and "3d_points" in f.lower()]

        if not csvs:
            self.failed.emit("No RTMPose CSV found.")
            return

        self._start_filtering(os.path.join(adir, csvs[0]))


    def _start_filtering(self, csv_path):
        cfg = ConfigManager()
        config_path = cfg.config_json

        th = FilteringThread(config_path, csv_path)
        self._filtering_thread = th

        th.filtering_progress.connect(lambda m: self._log(f"[FILTER] {m}"))
        th.filtering_finished.connect(self._on_filtering_finished)
        th.filtering_error.connect(lambda e: self.failed.emit(f"Filtering error:\n{e}"))

        th.start()


    def _on_filtering_finished(self, output_csv):
        self._log("[FILTER] done.")
        self._start_augmentation(output_csv)


    # ==========================================================
    # STEP 3 — AUGMENTATION
    # ==========================================================

    def _start_augmentation(self, csv_path):
        cfg = ConfigManager()
        config_path = cfg.config_json

        th = MarkerAugmentationThread(config_path, csv_path)
        self._augmentation_thread = th

        th.augmentation_progress.connect(lambda m: self._log(f"[AUG] {m}"))
        th.augmentation_finished.connect(self._on_augmentation_finished)
        th.augmentation_error.connect(lambda e: self.failed.emit(f"Augmentation error:\n{e}"))

        th.start()


    # ==========================================================
    # STEP 4 — CSV → TRC → OpenSim
    # ==========================================================

    def _on_augmentation_finished(self, output_csv):
        self._log("[AUG] done.")

        base, _ = os.path.splitext(output_csv)
        trc_path = base + ".trc"

        # CSV → TRC
        try:
            csv_to_trc(output_csv, trc_path)
        except Exception as e:
            self.failed.emit(f"CSV→TRC error:\n{e}")
            return

        # TRC → OpenSim
        try:
            convert_trc_to_opensim(trc_path, trc_path)
        except Exception as e:
            self.failed.emit(f"TRC→OpenSim error:\n{e}")
            return

        # → Next: Pose2Sim inverse kinematics!
        self.start_external_kinematics(trc_path)


    # ==========================================================
    # STEP 5 — Pose2Sim IK (KinematicsThread)
    # ==========================================================

    def start_external_kinematics(self, trc_path):
        """Start Pose2Sim IK."""
        self._log("Launching Pose2Sim Kinematics...")

        outdir = os.path.dirname(trc_path)

        th = KinematicsThread(
            trc_file_path=trc_path,
            output_dir=outdir,
            conda_env=self.conda_env_name
        )
        self._kinematics_thread = th

        th.kinematics_progress.connect(lambda m: self._log(f"[IK] {m}"))
        th.kinematics_finished.connect(self._on_kinematics_finished)
        th.kinematics_error.connect(self._on_kinematics_error)

        th.start()


    def _on_kinematics_finished(self, outdir):
        self._log("[IK] complete.")

        # # RRA optional step:
        # if self.rra_enabled:
        #     self._log("[RRA] Starting RRA...")
        #     self.start_rra_analysis(outdir)

        # Entire pipeline done!
        self.finished.emit(self._current_experiment, self._current_capture)


    def _on_kinematics_error(self, err):
        self.failed.emit(f"Kinematics error:\n{err}")
