from PyQt5.QtCore import QThread, pyqtSignal
from Camera.GoProCam import GoProCam
from config.Logger import Logger
import os
import time
import subprocess


class GoProCapture(QThread):
    """
    Thread to control recording for one GoPro.

    mode="pc":  Start/stop webcam (RTSP) and save to local file via ffmpeg (computer-side recording).
    mode="sd":  Trigger on-camera recording (files stored on SD card) — kept for backward compatibility.
    """

    recording_started_signal = pyqtSignal()
    recording_stopped_signal = pyqtSignal()
    recording_error_signal = pyqtSignal(str)

    def __init__(self,
                 identifier,              # "ip:port" OR (serial, profile) OR serial
                 resolution: str,
                 fps: str,
                 fov: str,
                 mode: str = "pc",
                 output_dir: str = None,
                 parent=None):
        super().__init__(parent)
        self._explicit_stop = False   # 是否是用户主动点了 Stop
        self._ffmpeg_log_fh = None    # 记录日志文件句柄，方便清理

        self.gopro = GoProCam(identifier)
        self.resolution = resolution
        self.fps = fps
        self.fov = fov
        self.mode = (mode or "pc").lower()
        self.output_dir = output_dir or os.path.join(os.getcwd(), "captures")

        self.logger = Logger.get_logger()
        self.is_running = False

        # pc-recording members
        self._rtsp_port = 8556
        self._outfile = None
        self._ffmpeg_proc: subprocess.Popen | None = None

    # ----------------- helpers -----------------

    def _ensure_outdir(self):
        os.makedirs(self.output_dir, exist_ok=True)

    def _host_only(self) -> str:
        # "172.24.153.51:8080" -> "172.24.153.51"
        return str(self.gopro.gopro_ip).split(":")[0]

    def _rtsp_url(self) -> str:
        return f"rtsp://{self._host_only()}:{self._rtsp_port}/live"

    def _next_outfile(self) -> str:
        ts = time.strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.output_dir, f"gopro_{ts}.mp4")

    # ----------------- QThread loop -----------------
    # 仅用于 mode="pc"：我们在这里“看护” ffmpeg 进程；stop_recording 会终止它。

    def run(self):
        if self.mode != "pc":
            return
        try:
            # 看护 ffmpeg：如果异常退出，抛出错误；用户主动 Stop 会把 is_running 置 False
            while self.is_running:
                if self._ffmpeg_proc is None:
                    break
                code = self._ffmpeg_proc.poll()
                if code is not None:
                    # 提前退出：不是我们显式 stop 的
                    if not self._explicit_stop:
                        msg = f"ffmpeg quit unexpectedly (code={code}). See log: {getattr(self, '_ffmpeg_log_path', None)}"
                        self.logger.error("[PC] " + msg)
                        self.recording_error_signal.emit(msg)
                    break
                time.sleep(0.2)
        finally:
            self._cleanup_pc()
            self.recording_stopped_signal.emit()



    # ----------------- public controls -----------------

    def start_recording(self) -> None:
        """
        Start recording.
        - pc: start RTSP (if needed), spawn ffmpeg to save to local file, then start thread watchdog
        - sd: send shutter start on camera (files on SD)
        """
        if self.is_running:
            print("[PC] start_recording ignored: already running")
            return
        self.is_running = True
        self._explicit_stop = False  # 这次是一次全新的开始

        if self.mode == "pc":
            try:
                if not self.gopro.connect():
                    raise RuntimeError(f"Cannot connect {self.gopro.gopro_ip}")

                if not self.gopro.is_streaming():
                    if not self.gopro.start_webcam(port=self._rtsp_port):
                        raise RuntimeError("Failed to start RTSP on camera")

                time.sleep(0.4)

                self._ensure_outdir()
                self._outfile = self._next_outfile()
                rtsp = self._rtsp_url()

                ts = time.strftime("%Y%m%d_%H%M%S")
                self._ffmpeg_log_path = os.path.join(self.output_dir, f"ffmpeg_{ts}.log")
                self._ffmpeg_log_fh = open(self._ffmpeg_log_path, "wb")

                cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-rtsp_transport", "tcp",
                    "-rw_timeout", "5000000",
                    "-i", rtsp,
                    "-fflags", "+genpts",
                    "-c", "copy",
                    "-movflags", "+faststart",
                    "-f", "mp4",
                    self._outfile
                ]
                print(f"[PC] will save to: {self._outfile}")
                print("[PC] ffmpeg cmd:", " ".join(cmd))

                self._ffmpeg_proc = subprocess.Popen(
                    cmd + ["-y"],
                    stdin=subprocess.PIPE,                 # ← 允许我们 later 发送 'q'
                    stdout=subprocess.DEVNULL,
                    stderr=self._ffmpeg_log_fh
                )


                # 1 秒“存活自检”
                time.sleep(1.0)
                if self._ffmpeg_proc.poll() is not None:
                    code = self._ffmpeg_proc.returncode
                    raise RuntimeError(f"ffmpeg exited early (code={code}). See log: {self._ffmpeg_log_path}")

                self.logger.info(f"[PC] Recording {rtsp} -> {self._outfile}")
                self.recording_started_signal.emit()
                super().start()  # 启动 watchdog 线程（run）
                return

            except Exception as e:
                self.is_running = False
                self._cleanup_pc(error_context=str(e))
                self.logger.error(f"[PC] start_recording error: {e}")
                self.recording_error_signal.emit(str(e))
                return

        # ---- SD 模式（保留兼容）----
        try:
            if self.gopro.is_streaming():
                self.gopro.stop_webcam()
            self.gopro.enable_wired_control()
            self.gopro.start_video()
            self.logger.info(f"[SD] Recording started on {self.gopro.gopro_ip}")
            self.recording_started_signal.emit()
        except Exception as e:
            self.is_running = False
            self.logger.error(f"[SD] start_recording error: {e}")
            self.recording_error_signal.emit(str(e))



    def stop_recording(self) -> None:
        """
        Stop recording.
        - pc: terminate ffmpeg and (only here) stop RTSP on camera
        - sd: send shutter stop on camera
        """
        if not self.is_running:
            print("[PC] stop_recording ignored: not running")
            return

        self.is_running = False
        self._explicit_stop = True

        if self.mode == "pc":
            # 优雅退出：给 ffmpeg 发送 'q'，让它写 moov、封包完成
            try:
                if self._ffmpeg_proc and self._ffmpeg_proc.poll() is None:
                    try:
                        # 发送 'q' + flush
                        self._ffmpeg_proc.stdin.write(b"q")
                        self._ffmpeg_proc.stdin.flush()
                    except Exception:
                        pass
                    # 等待最多 5 秒让它正常收尾
                    try:
                        self._ffmpeg_proc.wait(timeout=5)
                    except Exception:
                        # 超时再兜底 terminate（极端情况）
                        self._ffmpeg_proc.terminate()
                        try:
                            self._ffmpeg_proc.wait(timeout=3)
                        except Exception:
                            self._ffmpeg_proc.kill()
            except Exception:
                pass

            # 额外：记录一下文件是否写成功（方便你看日志）
            try:
                if self._outfile and os.path.exists(self._outfile):
                    print(f"[PC] file saved: {self._outfile} ({os.path.getsize(self._outfile)} bytes)")
                else:
                    print(f"[PC] file not found after stop: {self._outfile}")
            except Exception as e:
                print("[PC] file check error:", e)

            # 让 watchdog 线程（run）自然退出
            self.wait(3000)
            return
                # ---- SD 模式 ----
        try:
            self.gopro.enable_wired_control()
            self.gopro.stop_video()
            self.logger.info(f"[SD] Recording stopped on {self.gopro.gopro_ip}")
            self.recording_stopped_signal.emit()
        except Exception as e:
            self.logger.error(f"[SD] stop_recording error: {e}")
            self.recording_error_signal.emit(str(e))

    # ----------------- internal cleanup -----------------


    def _cleanup_pc(self, error_context: str = ""):
        # 关 ffmpeg
        try:
            if self._ffmpeg_proc and self._ffmpeg_proc.poll() is None:
                self._ffmpeg_proc.terminate()
                try:
                    self._ffmpeg_proc.wait(timeout=3)
                except Exception:
                    self._ffmpeg_proc.kill()
        except Exception:
            pass
        self._ffmpeg_proc = None

        # 只有显式 stop 时，才停 RTSP；若是异常退出，不动相机，避免把“预览/别人”也关掉
        if self._explicit_stop:
            try:
                if self.gopro.is_streaming():
                    self.gopro.stop_webcam()
                    print("[PC] stop_webcam due to explicit stop")
            except Exception:
                pass

        # 关日志句柄
        try:
            if self._ffmpeg_log_fh:
                self._ffmpeg_log_fh.flush()
                self._ffmpeg_log_fh.close()
        except Exception:
            pass
        self._ffmpeg_log_fh = None

        # 打点
        if self._outfile:
            suffix = f" (error: {error_context})" if error_context else ""
            self.logger.info(f"[PC] Recording stopped for {self.gopro.gopro_ip} -> {self._outfile}{suffix}")

