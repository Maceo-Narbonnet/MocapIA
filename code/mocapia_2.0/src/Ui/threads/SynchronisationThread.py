from PyQt5.QtCore import QThread, pyqtSignal, QObject
from typing import List
from PyQt5.QtWidgets import QMessageBox

from config.Logger import Logger
from Pose_Estimation.video_utils import (
     timecode_to_seconds, get_video_timecode, get_video_duration
)
import cv2
import re
import subprocess


class SynchronisationWorker(QObject):
    """Worker object that performs video synchronization using ffmpeg and emits progress."""
    progress = pyqtSignal(int)   # 0..100
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, video_paths: List[str], save_paths: List[str]):
        super().__init__()
        self.video_paths = video_paths
        self.save_paths = save_paths
        self.logger = Logger.get_logger()
        self._cancelled = False
        self._ffmpeg_proc = None

    def cancel(self):
        """Called when the dialog is closing or the user cancels. Sets the flag and tries to terminate ffmpeg."""
        self._cancelled = True
        try:
            if self._ffmpeg_proc and self._ffmpeg_proc.poll() is None:
                self._ffmpeg_proc.terminate()
        except Exception:
            pass

    def _emit(self, p: int):
        """Clamp progress into [0, 100] and emit."""
        try:
            p = max(0, min(int(p), 100))
            self.progress.emit(p)
        except Exception:
            pass

    def run(self):
        """Run the video synchronization process and emit cumulative progress across all videos."""
        self._emit(0)
        try:
            total_videos = len(self.video_paths)
            assert len(self.video_paths) == len(self.save_paths), \
                "The number of video paths must equal the number of save paths."

            # Read FPS for all inputs
            caps = [cv2.VideoCapture(video_path) for video_path in self.video_paths]
            fpss = [cap.get(cv2.CAP_PROP_FPS) for cap in caps]
            fps = fpss[0]
            if fps == 0:
                raise Exception("Invalid FPS value detected. Check the video files.")

            if not all(fps == fpss[i] for i in range(1, len(fpss))):
                raise Exception("All videos must have the same framerate.")

            # Compute overlap [new_start, new_end] and frame indices range per video
            timecodes_start = [timecode_to_seconds(get_video_timecode(v), fps) for v in self.video_paths]
            timecodes_end = [get_video_duration(v) + timecodes_start[i] for i, v in enumerate(self.video_paths)]
            new_start = max(timecodes_start)
            new_end = min(timecodes_end)

            start_frame_indices = [int(fps * (new_start - tc)) for tc in timecodes_start]
            end_frame_indices   = [int(fps * (new_end   - tc)) for tc in timecodes_start]

            # Pre-compute segment durations for global progress
            durations = [(end_frame_indices[i] - start_frame_indices[i]) / fps for i in range(total_videos)]
            total_duration = max(1e-6, sum(durations))
            offsets = [0.0]
            for i in range(1, total_videos):
                offsets.append(offsets[-1] + durations[i - 1])

            def process_video(index: int):
                start_time = start_frame_indices[index] / fps
                end_time   = end_frame_indices[index] / fps
                offset     = offsets[index]

                def update_progress(current_time_in_this_video: float):
                    """Map per-video time to global [0..100] progress."""
                    local = max(0.0, min(current_time_in_this_video - start_time, durations[index]))
                    progress_value = int(round((offset + local) / total_duration * 100))
                    self._emit(progress_value)

                command = [
                    "ffmpeg", "-y",
                    "-i", self.video_paths[index],
                    "-ss", str(start_time),
                    "-to", str(end_time),
                    "-c:v", "libx264",
                    self.save_paths[index],
                ]

                # Keep a handle to the child process so we can terminate it on cancel()
                self._ffmpeg_proc = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
                )

                # Parse ffmpeg stderr to estimate progress
                for line in self._ffmpeg_proc.stderr:
                    if self._cancelled:
                        try:
                            self._ffmpeg_proc.terminate()
                        except Exception:
                            pass
                        return

                    match = re.search(r"frame=\s*(\d+)", line)
                    if match:
                        current_frame = int(match.group(1))
                        current_time  = current_frame / max(1e-6, fps)
                        update_progress(current_time)

                self._ffmpeg_proc.wait()
                print(f"Video {index + 1}/{len(self.video_paths)} synchronized: {self.save_paths[index]}")
                # Snap to the segment end to avoid rounding gaps
                update_progress(start_time + durations[index])

            for i in range(total_videos):
                if self._cancelled:
                    break
                process_video(i)

        except KeyError as e:
            QMessageBox.warning(None, "Error", "SYNC ERROR: Make sure the videos are from time-synchronized GoPro cameras.")
            self.logger.error(f"SYNC ERROR: {e}")
        except FileNotFoundError as e:
            QMessageBox.warning(None, "Error", "FILE ERROR: Wrong file path.")
            self.logger.error(f"FILE ERROR: {e}")
        except Exception as e:
            QMessageBox.warning(None, "Error", f"UNKNOWN ERROR: {e}")
            self.logger.error(f"UNKNOWN ERROR: {e}")
        finally:
            self.is_running = False
            self._emit(100)     # ensure the progress bar is complete on normal finish
            self.finished.emit()


class SynchronisationThread(QThread):
    def __init__(self, video_paths, save_paths, parent=None):
        super().__init__(parent)
        self.worker = SynchronisationWorker(video_paths, save_paths)
        self.worker.moveToThread(self)
        self.started.connect(self.worker.run)
        self.worker.finished.connect(self.quit)

    def cancel(self):
        try: self.worker.cancel()
        except: pass
        self.quit()
