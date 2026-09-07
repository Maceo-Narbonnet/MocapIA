from PyQt5.QtCore import QThread, pyqtSignal
from Pose_Estimation.Triangulator import Triangulator
from config.Project import MocapProject
from config.Config_Manager import StatusManager
from config.Logger import Logger
from Pose_Estimation.Triangulator import UserCancelled

class RTMPoseThread(QThread):
    """Thread used to run the pose estimation algorithm for multiple cameras."""
    progress3d = pyqtSignal(int, int)   # current, total
    failed = pyqtSignal(str)
    csv_ready_for_filtering = pyqtSignal(str)

    def __init__(self, experiment_name: str, capture_name: str):
        super().__init__()
        status = StatusManager()

        # Store these attributes for later use in run()
        self.project_path = status.status_data["current_project"]["path"]
        self.experiment_name = experiment_name
        self.capture_name = capture_name
        
        self._stop = False

        # Pass the progress callback here to avoid creating another Triangulator in run()
        self.triangulator = Triangulator(
            project_path=self.project_path,
            experiment_name=self.experiment_name,
            capture_name=self.capture_name,
            csv_name="",
            progress_cb=self._tri_progress_cb,   # 3D stage progress callback
            stop_cb=self._should_stop,
        )

        self.project = MocapProject(self.project_path)
        self.logger = Logger.get_logger()
        self.was_cancelled = False
        
    def cancel(self):        
        self._stop = True
        try:
            self.requestInterruption()
        except Exception:
            pass

    def _should_stop(self) -> bool:      
        return self._stop or self.isInterruptionRequested()


    def _tri_progress_cb(self, phase: str, current: int, total: int):
        """Callback used by Triangulator to emit progress updates during 3D triangulation."""
        if phase == "3d":
            self.progress3d.emit(int(current), int(total))

    def run(self, show_video: bool = True):
        """Run the pose estimation algorithm in two steps: 2D inference then 3D triangulation."""
        self.runing = True  # Set running to True when starting
        try:
            # 1) 2D inference (if JSON files already exist, you can skip this step)
            self.logger.info(
                f"Started pose estimation on project: {self.project_path}, "
                f"experiment: {self.experiment_name}, capture: {self.capture_name}"
            )
            self.triangulator.get_2dpoints_all_videos(show_video)
            self.logger.info("2D inference completed")

            # 2) 3D triangulation + CSV export (progress is emitted through progress_cb)
            self.logger.info("Starting 3D triangulation")
            subject_ids = {ip: [1] for ip in self.project.get_experiment_camera_ips(self.experiment_name)}
            self.triangulator.point_to_csv(subject_ids=subject_ids, T=None)
            csv_output_path = self.triangulator.csv_3d_path
            self.logger.info("CSV file successfully created")
            # Après la création du CSV
            self.logger.info(f"CSV file created at: {csv_output_path}")
            self.csv_ready_for_filtering.emit(csv_output_path)
            self.logger.info("Signal csv_ready_for_filtering emitted")

            
        except UserCancelled:
            # Cancelled by user
            self.triangulator.cleanup_tmp(force=True)
            self.was_cancelled = True
            return

        except Exception as e:
            self.logger.error(f"Error in RTMPoseThread: {str(e)}")
            self.runing = False
        finally:
            self.runing = False


