# services/recording_service.py
import os, time as t
from PyQt5.QtCore import QObject
from threads.CaptureThread import GoProCapture
from config.Config_Manager import ConfigManager

class RecordingService(QObject):
    """
    Start/stop recording to PC for all configured cameras.
    """
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._threads = []

    def start(self):
        # Compute output directory: <project>/<experiment>/captures
        try:
            proj_path = getattr(self.ctx, "project_path", os.getcwd())
            exp_name  = getattr(self.ctx, "experiment_name", "default_experiment")
            out_dir   = os.path.join(proj_path, exp_name, "captures")
        except Exception:
            out_dir   = os.path.join(os.getcwd(), "captures")
        os.makedirs(out_dir, exist_ok=True)

        # Stop old threads if any
        self.stop()

        # Get camera list & parameters (reuse your ConfigManager logic)
        cfg = ConfigManager()
        ips_or_serials = cfg.get_used_config()
        # You can also fetch resolution/fps/fov from cfg if needed
        resolution, fps, fov = "1080p", "30", "Linear"

        # Start one GoProCapture per camera
        for cam in ips_or_serials:
            th = GoProCapture(cam, resolution, fps, fov, mode="pc", output_dir=out_dir)
            self._threads.append(th)
            th.start_recording()

    def stop(self):
        # Gracefully stop threads
        for th in self._threads:
            try:
                th.stop_recording()
            except Exception:
                pass
        self._threads.clear()
        t.sleep(0.2)
