from PyQt5.QtCore import QThread, QObject, pyqtSignal, pyqtSlot
from typing import Tuple
from pathlib import Path
import os

from config.Project import MocapProject
from Pose_Estimation.extrinsic_calib import ExtrinsicCalib


class PerformDetectionWorker(QObject):
    # Progress: current, total
    progress = pyqtSignal(int, int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        project_path: str, 
        experiment_name: str,
        chessboard_size: Tuple[int, int],
        square_size: float,
        nb_img: int = 41,
        draw_corners: bool = False, # only this parameter needs to be changed if we launch the MainWindow
    ):
        super().__init__()
        self.draw_corners = draw_corners
        self.project_path = project_path
        self.experiment_name = experiment_name  
        self.project = MocapProject(project_path)

        # HDF5 output path
        self.chessboard_size = chessboard_size
        self.square_size = square_size

        # Temporary root directory & detections hdf5
        self.tmp_folder_path = os.path.join(project_path, experiment_name, "calibration", "tmp")
        os.makedirs(self.tmp_folder_path, exist_ok=True)
        self.nb_images = nb_img

    def _count_images(self) -> int:
        total = 0
        root = Path(self.tmp_folder_path)
        if root.exists():
            for d in root.glob("*"):
                if d.is_dir():
                    total += sum(1 for f in d.glob("*.jpg"))
        return total

    @pyqtSlot()
    def run(self):
        """Perform chessboard detection in tmp/<ip>_tmp/ folders; currently provides coarse-grained progress (0% → 100%)."""
        try:
            total = self._count_images()
            # Emit 0/total at the start (so the UI shows “entering detection stage”)
            self.progress.emit(0, max(1, total))

            calib = ExtrinsicCalib(self.project_path, self.experiment_name, self.chessboard_size, self.square_size)
            
            calib.convert_pickle_to_hdf5()
            print("[OK] convert pickle to hdf5", flush=True)

            # Add progress callback; each processed image triggers this, relayed to self.progress.emit(done, total)
            calib.perform_detections(
                draw_corners=self.draw_corners, 
                progress_cb=lambda d, t: self.progress.emit(int(d), int(max(1, t)))
            )

            # Post-processing (same as in your original logic)
            calib.convert_pickle_to_hdf5()
            calib.extract_calibration_matrix()
            calib.extract_projection_matrix()

            # Done: emit total/total
            self.progress.emit(max(1, total), max(1, total))
            self.finished.emit()

        except KeyError as e:
            self.error.emit(f"SYNC ERROR: Make sure videos are time-synchronized GoPros. Detail: {e}")
        except FileNotFoundError as e:
            self.error.emit(f"FILE ERROR: Wrong file path. Detail: {e}")
        except Exception as e:
            self.error.emit(f"UNKNOWN ERROR: {e}")


class PerformDetectionThread(QThread):
    def __init__(self, project_path, experiment_name, chessboard_size, square_size, parent=None):
        super().__init__(parent)
        self.worker = PerformDetectionWorker(project_path, experiment_name, chessboard_size, square_size)
        self.worker.moveToThread(self)
        self.started.connect(self.worker.run)
        self.worker.finished.connect(self.quit)

    def cancel(self):
        try:
            self.worker.cancel()
        except:
            pass
        self.quit()
