from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from pathlib import Path
from Pose_Estimation.video_utils import extract_images_from_video

class ExtractionWorker(QObject):
    progress = pyqtSignal(int, int)   # (cur, total)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, sources, dst_map, frames_per_video: int):
        super().__init__()
        self.sources = list(sources)
        self.dst_map = dict(dst_map)
        self.k = int(frames_per_video)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @pyqtSlot()
    def run(self):
        try:
            total = self.k * len(self.sources)
            done_global = 0

            for src in self.sources:
                if self._cancelled:
                    break
                dst = Path(self.dst_map[src])
                dst.mkdir(parents=True, exist_ok=True)

                # 单视频回调：把“局部”进度换算成“全局”
                def per_video_cb(done_local, total_local):
                    nonlocal done_global
                    # 局部每+1帧，全局+1
                    done_global += 1
                    self.progress.emit(done_global, total)

                # 直接复用你的视频工具函数（连续编号、等距抽样）
                extract_images_from_video(str(src), str(dst), number=int(self.k), image_format="jpg", progress_cb=per_video_cb, clear_existing=True)

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
            
class ExtractionThread(QThread):
    def __init__(self, sources, dst_map, frames_per_video: int, parent=None):
        super().__init__(parent)
        self.worker = ExtractionWorker(sources, dst_map, frames_per_video)
        self.worker.moveToThread(self)
        self.started.connect(self.worker.run)
        self.worker.finished.connect(self.quit)  # 业务结束→退出事件循环

    def cancel(self):
        try: self.worker.cancel()
        except: pass
        self.quit()