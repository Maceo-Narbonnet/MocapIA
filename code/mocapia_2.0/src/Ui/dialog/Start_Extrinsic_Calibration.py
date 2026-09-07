from PyQt5.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QGridLayout, QSpinBox, QVBoxLayout, QScrollArea, QDialogButtonBox, QWidget, QProgressBar, QSizePolicy, QMessageBox, QFileDialog, QHBoxLayout
from Ui.threads.SynchronisationThread import SynchronisationThread
from Ui.threads.PerformDetectionThread import PerformDetectionThread
import os
import re, json 
from functools import partial
from threads.ExtractionThread import ExtractionThread
from pathlib import Path

            
class EnterVideoNumber(QDialog):
    def __init__(self, ctx, parent = None):
        super().__init__(parent)
        self.ctx = ctx
        self.project_path = ctx.project_path
        # set the title of the window
        self.setWindowTitle("Start Extrinsic Calibration")
        # creat the layout
        self.layout = QGridLayout()

        self.title = QLabel("Synchronization of the videos")
        self.layout.addWidget(self.title,0,0)
        # select the number of videos to sychronize
        self.label_video_count = QLabel("Number of cameras used:")
        self.spinbox_video_count = QSpinBox()
        self.spinbox_video_count.setMinimum(2)    #At least 2 videos to synchronize
        self.spinbox_video_count.setMaximum(4)    #At most 4 videos to synchronize
        self.spinbox_video_count.setSingleStep(1)  #set the length of step（the number every time click +/-）
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        
        self.layout.addWidget(self.label_video_count,1,0)
        self.layout.addWidget(self.spinbox_video_count,1,1)
        self.layout.addWidget(self.ok_button,2,0)
        self.layout.addWidget(self.cancel_button,2,1)

        self.setLayout(self.layout)

        self.ok_button.clicked.connect(self.on_ok_clicked)
        self.cancel_button.clicked.connect(self.close)

    def get_video_number(self):
        return self.spinbox_video_count.value()
    
    def on_ok_clicked(self):
        # Directly close the frame-count selection dialog
        self.accept()

        # — Auto input directory: <project>/<experiment>/raw/calibration —
        auto_dir = os.path.join(self.ctx.project_path, self.ctx.experiment_name, "raw", "calibration")

        # Let the second dialog determine video_count by inspecting how many videos are in that directory
        dialog = StartExtrinsicCalibration(
            video_count=self.get_video_number(),  # Initial value; not strictly needed
            ctx=self.ctx,
            parent=self,
            auto_input_dir=auto_dir,   #  pass the auto directory
            auto_overwrite=True        #  allow overwriting outputs
        )
        dialog.exec_()




class StartExtrinsicCalibration(QDialog):
    def __init__(self, video_count, ctx, parent=None, auto_input_dir=None, auto_overwrite=True):
        super().__init__(parent)
        self.ctx = ctx
        self.video_count = video_count    # record the number of input videos 
        self.project_path = ctx.project_path
        self.experiment_name = ctx.experiment_name
        self.auto_input_dir = auto_input_dir
        self.auto_overwrite = auto_overwrite
        self.synchronisation_thread = None
        self.extract_thread = None
        self.detect_thread = None
        # self.chessboard_size = (11, 10)
        # self.square_size = 47  # mm
        self.chessboard_size = (9, 8)  # 7x6 carrés = 6x5 coins intérieurs !
        self.square_size = 60  # mm
        # set the title of the window
        self.setWindowTitle("Start Extrinsic Calibration")
        self.resize(500, 100)
        # creat the layout
        self.layout = QGridLayout()

        self.title = QLabel("Synchronization of the videos")
        self.layout.addWidget(self.title,0,0)

        #create a progress bar 0% -> 100%
        self.progress_bar = QProgressBar() 
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)

        # scroll area to support several input widgets
        self.scroll_area = QScrollArea()
        self.scroll_area_widget = QWidget()
        self.scroll_layout = QGridLayout()
        self.scroll_area_widget.setLayout(self.scroll_layout)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.scroll_area_widget)
        self.layout.addWidget(self.scroll_area,1, 0, 1, 4)
        self.layout.addWidget(self.progress_bar, 2, 0, 1, 4)

    
        # the list to stock the input
        self.last_dir_videos = os.path.expanduser("~")
        self.input_paths = []
        self.output_paths = []

        # according to the number of videos selected by user to creeat the input QLineEdit()
                # according to the number of videos selected by user to create the input widgets
        for i in range(self.video_count):
            input_label = QLabel(f"Input Video {i+1} Path:")
            input_edit  = QLineEdit()
            input_edit.setReadOnly(True)  # read-only to avoid manual input errors

            browse_btn  = QPushButton("Browse…")
            browse_btn.clicked.connect(partial(self._browse_video_file, input_edit))

            # When the text changes, dynamically generate the output path
            input_edit.textChanged.connect(lambda text, idx=i: self.update_output_path(idx, text))

            # Layout: Label | Input field | Button
            self.scroll_layout.addWidget(input_label, i * 2, 0)
            self.scroll_layout.addWidget(input_edit,  i * 2, 1)
            self.scroll_layout.addWidget(browse_btn,  i * 2, 2)

            self.input_paths.append(input_edit)     
            self.output_paths.append("")            


        self.valid_button = QPushButton("Validate")
        self.cancel_button = QPushButton("Cancel")
        
        self.valid_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.cancel_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
 
        self.layout.setColumnStretch(0, 1)
        self.layout.setColumnStretch(2, 1)

        self.layout.addWidget(self.valid_button,3, 0)
        self.layout.addWidget(self.cancel_button,3, 2)

        self.setLayout(self.layout)
    
        self.valid_button.clicked.connect(self.on_valid_clicked)   #the fonction for clicking the 'valid' button
        self.cancel_button.clicked.connect(self.reject)    #Once clicking 'Cancel', close the window
        
        # — Auto mode: populate inputs from <project>/<experiment>/raw/calibration and enable overwrite —
        if self.auto_input_dir and os.path.isdir(self.auto_input_dir):
            self._auto_fill_from_dir()
            # Sync the video count with the UI (if directory video count != passed-in video_count, it's fine)
            print(f"[Auto] using {len(self._list_videos_in_dir(self.auto_input_dir))} files from {os.path.normpath(self.auto_input_dir)}")


    def _list_videos_in_dir(self, dirpath):
        exts = (".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm")
        if not dirpath or not os.path.isdir(dirpath):
            return []
        files = [os.path.join(dirpath, f) for f in os.listdir(dirpath)
                if f.lower().endswith(exts)]
        return sorted(files)  # 初步按文件名排序
    
    

    def _order_files_by_config(self, files):
        """
        Reorder 'files' according to camera_setup order in config.json
        (Hero12_<n> ascending). If matching fails, keep original order.
        """
        base = os.path.join(self.project_path, self.experiment_name)
        cfg_path = os.path.join(base, "config.json")
        if not os.path.isfile(cfg_path):
            return files

        try:
            with open(cfg_path, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
            cams = cfg.get("camera_setup", [])

            def cam_key(c):
                m = re.search(r"(\d+)$", str(c.get("name","")))
                return (0, int(m.group(1))) if m else (1, 10**9)

            cams_sorted = sorted(cams, key=cam_key)
            names = [c.get("name","") for c in cams_sorted]

            # Heuristic matching: use the numeric suffix in the camera name
            # to loosely match the filename (e.g., Hero12_1 matches files containing _1 or 1).
            def score(file):
                basename = os.path.basename(file)
                for i, n in enumerate(names):
                    num = re.search(r"(\d+)$", n or "")
                    if num and re.search(rf"(^|[^0-9]){num.group(1)}([^0-9]|$)", basename):
                        return (0, i)  # higher priority when number is matched
                return (1, files.index(file))  # otherwise keep original order
            return sorted(files, key=score)
        except Exception as e:
            print(f"[WARN] _order_files_by_config failed: {e}")
            return files

    def _auto_fill_from_dir(self):
        """
        Scan videos under self.auto_input_dir → auto-fill self.input_paths (read-only),
        and set output paths to the same directory (overwrite mode).
        """
        vids = self._list_videos_in_dir(self.auto_input_dir)
        if not vids:
            print(f"[Auto] no videos found in {self.auto_input_dir}")
            return

        vids = self._order_files_by_config(vids)

        # If UI has fewer rows than files, truncate; if more, fill only the first N rows.
        n = min(len(vids), len(self.input_paths))
        for i in range(n):
            self.input_paths[i].setText(vids[i])   # triggers textChanged → auto-populates output_paths

        # Output paths: overwrite in the same directory (e.g., foo.mp4 → foo_sync.mp4)
        for i in range(n):
            src = vids[i]
            stem, ext = os.path.splitext(os.path.basename(src))
            out = os.path.join(self.auto_input_dir, f"{stem}_sync{ext}")
            self.output_paths[i] = out

        # To prevent accidental edits, disable browse buttons (optional).
        # Since your browse buttons are local variables, you could:
        # 1) store them in a list and disable here; or
        # 2) simpler: keep these QLineEdit widgets readOnly (already True).


    
    def create_output_path(self, input_path, i):
        # get the root directory of the input file(MoCap_Demo5)
        root_folder = os.path.dirname(os.path.dirname(input_path))
        return os.path.join(root_folder, "calib", f"TSS{i}_sync.mp4")
    
    def update_output_path(self, idx, text):
        """ when the QLineEdit is modified, refresh output_paths """
        self.output_paths[idx] = self.create_output_path(text, idx+1)

    def show_error(self, msg):
        QMessageBox.warning(self, "Error", msg)


    def _count_all_tmp_images(self):
        total = 0
        root = getattr(self, "tmp_root", None)
        if not root:
            return 0
        root = Path(root)
        if root.exists():
            for d in root.glob("*"):
                if d.is_dir():
                    total += sum(1 for f in d.glob("*.jpg"))
        return total

    def _browse_video_file(self, target_edit: QLineEdit):
        VIDEO_FILTER = "Video Files (*.mp4 *.mov *.avi *.mkv *.m4v *.webm);;All Files (*)"
        # Start dir: use this row's text if valid, else fallback to shared last_dir
        txt = target_edit.text().strip()
        if txt and os.path.exists(txt):
            start_dir = os.path.dirname(txt)
        else:
            start_dir = self.last_dir_videos

        path, _ = QFileDialog.getOpenFileName(self, "Select a video file", start_dir, VIDEO_FILTER)
        if path:
            target_edit.setText(path)                  # Triggered by textChanged → refresh output_paths
            self.last_dir_videos = os.path.dirname(path)  # Update last_dir


    def _set_stage_progress(self, start: int, end: int, cur: int, total: int, fmt: str = ""):
        total = max(1, int(total))
        cur = max(0, min(int(cur), total))
        pct_float = start + (end - start) * (cur / total)
        pct = max(0, min(int(round(pct_float)), 100))
        try:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(pct))
            if fmt:
                self.progress_bar.setFormat(fmt)
        except RuntimeError:
            return

    def _set_stage_label(self, text: str):
        # You can also update a nearby QLabel instead;
        # here we simply use the progress bar’s format text.
        self.progress_bar.setFormat(text)
        
    def _build_extraction_plan_ipmapped(self):
        """
        Read <project>/<experiment>/config.json → camera_setup,
        and generate:
            sources: List[Path]        → synchronized *_sync video files (each one)
            dst_map: Dict[Path, Path]  → mapping of each source video → tmp folder by IP (tmp/<ip>_tmp)
        Directory structure:
            <project>/<experiment>/calibration/tmp/<IP>_tmp/
              ← one tmp folder per camera
        Notes:
        - Video filenames follow your naming convention: 'Hero12_<n>__*.mp4'
        - Use the name→IP mapping in config.json to route each camera’s video
          to the corresponding <IP>_tmp folder.
        """
        # ===== 1) Base paths =====
        project_path = Path(getattr(self, "project_path", "."))
        experiment   = getattr(self, "experiment_name", "Experiment")
        base = project_path / experiment
        calib_dir = base / "calibration"
        calib_dir.mkdir(parents=True, exist_ok=True)
        tmp_root = calib_dir / "tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)

        # ===== 2) Read config.json → name2ip mapping & ordered IP list =====
        cfg_path = base / "config.json"
        name2ip = {}
        ips = []
        if cfg_path.is_file():
            try:
                with cfg_path.open("r", encoding="utf-8-sig") as f:
                    cfg = json.load(f)
                cams = cfg.get("camera_setup", [])
                # Sort by the numeric suffix at the end of "Hero12_<n>"
                def keyfn(c):
                    m = re.search(r"(\d+)$", str(c.get("name", "")))
                    return (0, int(m.group(1))) if m else (1, 10**9)
                cams_sorted = sorted(cams, key=keyfn)
                name2ip = {
                    (c.get("name", "").strip()): (c.get("ip", "").strip())
                    for c in cams_sorted if c.get("name") and c.get("ip")
                }
                ips = [c.get("ip", "").strip() for c in cams_sorted if c.get("ip")]
            except Exception as e:
                print(f"[WARN] Failed to read config.json: {e}")

        if not ips:
            raise RuntimeError("Camera IP list is empty. Check config.json → camera_setup[].ip")

        # ===== 3) Pre-create IP → tmp directory mapping =====
        ip2dir = {}
        for ip in ips:
            if not ip:
                continue
            d = tmp_root / f"{ip}_tmp"
            d.mkdir(parents=True, exist_ok=True)
            ip2dir[ip] = d

        # ===== 4) Collect *_sync videos (with fallback rules) =====
        video_exts = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm",
                      ".MP4", ".MOV", ".MKV", ".AVI", ".M4V", ".WEBM"}
        sources = []

        # (a) self.output_paths may already contain synchronized files
        out_paths = [p for p in getattr(self, "output_paths", []) if p]
        for p in out_paths:
            pth = Path(p)
            if pth.is_file() and pth.suffix in video_exts:
                sources.append(pth)

        # (b) fallback: infer <stem>_sync.<ext> from input paths
        if not sources:
            inputs = [w.text().strip() for w in getattr(self, "input_paths", []) if w.text().strip()]
            for src in inputs:
                stem, ext = os.path.splitext(src)
                cand = Path(f"{stem}_sync{ext}")
                if cand.is_file() and cand.suffix in video_exts:
                    sources.append(cand)

            # (c) fallback: scan auto_input_dir or first input directory for *_sync.*
            if not sources:
                base_dir = getattr(self, "auto_input_dir", "") or (os.path.dirname(inputs[0]) if inputs else "")
                if base_dir and os.path.isdir(base_dir):
                    for f in os.listdir(base_dir):
                        if "_sync" in f and Path(f).suffix in video_exts:
                            cand = Path(base_dir) / f
                            if cand.is_file():
                                sources.append(cand)

        if not sources:
            raise RuntimeError("No synchronized videos found (no *_sync files).")

        # ===== 5) Build dst_map: from Hero12_n prefix → name2ip → ip2dir =====
        dst_map = {}  # {src: dst_dir}
        for src in sources:
            fname = src.name
            m = re.match(r"(Hero12_\d+)__", fname)  # parse 'Hero12_n__' prefix
            if not m:
                print(f"[WARN] Skip {fname}: missing 'Hero12_n__' prefix.")
                continue
            cam = m.group(1)
            ip = name2ip.get(cam, "")
            if not ip:
                print(f"[WARN] Skip {fname}: camera '{cam}' not found in config.json.")
                continue
            dst = ip2dir.get(ip)
            if not dst:
                dst = tmp_root / f"{ip}_tmp"
                dst.mkdir(parents=True, exist_ok=True)
                ip2dir[ip] = dst
            dst_map[src] = dst

        if not dst_map:
            raise RuntimeError("No valid (src → ip_tmp) mapping could be built from synchronized files.")

        return sources, dst_map, tmp_root

    def on_valid_clicked(self):
        # 1) Ask the user for how many frames to extract per video
        dlg = FrameNumberDialog(default=50, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        self.frames_per_video = dlg.value()

        # 2) Prepare paths and initialize progress display
        input_paths = [edit.text() for edit in self.input_paths]
        output_paths = self.output_paths
        self.progress_bar.setValue(0)
        self._set_stage_label("Synchronizing videos…")

        print(f"Valid clicked. Synchronizing videos from {input_paths} to {output_paths}...")

        try:
            # 3) Start synchronization thread; map progress (0..100) → global 0..30
            self.synchronisation_thread = SynchronisationThread(input_paths, output_paths)
            self.synchronisation_thread.worker.progress.connect(
                lambda p: self._set_stage_progress(0, 30, max(0, int(p)), 100, f"Synchronizing… {max(0, int(p))}%")
            )
            self.synchronisation_thread.worker.finished.connect(self.on_sync_finished)
            self.synchronisation_thread.worker.error.connect(self.show_error)
            self.synchronisation_thread.start()
            self.synchronisation_thread.worker.finished.connect(self.synchronisation_thread.quit)
            self.synchronisation_thread.finished.connect(self.synchronisation_thread.deleteLater)
            self.synchronisation_thread.worker.finished.connect(self.synchronisation_thread.worker.deleteLater)

        except Exception as e:
            print(f"Error during synchronization: {e}")
            self.show_error(str(e))
            
    def on_sync_finished(self):
        # Proceed to frame extraction phase
        self._set_stage_label("Extracting frames…")

        try:
            sources, dst_map, tmp_root = self._build_extraction_plan_ipmapped()
            self.tmp_root = tmp_root
        except Exception as e:
            self.show_error(str(e))
            return

        # Start extraction thread (global progress 30→40)
        self.extract_thread = ExtractionThread(
            sources=sources,
            dst_map=dst_map,
            frames_per_video=getattr(self, "frames_per_video", 50),
        )

        self.extract_thread.worker.progress.connect(
            lambda cur, total: self._set_stage_progress(30, 40, cur, total, f"Extracting… {cur}/{total}")
        )
        self.extract_thread.worker.finished.connect(self._on_extract_finished)
        self.extract_thread.worker.error.connect(self.show_error)

        self.extract_thread.start()
        t = self.extract_thread
        t.worker.finished.connect(t.quit)
        t.finished.connect(t.deleteLater)
        t.worker.finished.connect(t.worker.deleteLater)

    def _on_extract_finished(self):
        # Proceed to detection phase
        self._set_stage_label("Detecting chessboards…")
        self._start_detection()

    def _start_detection(self):
        total_imgs = self._count_all_tmp_images()
        # Start the detection thread (parameters depend on your implementation)
        self.detect_thread = PerformDetectionThread(
            project_path=self.project_path,
            experiment_name=self.experiment_name,
            chessboard_size=self.chessboard_size,
            square_size=self.square_size
        )

        # detect_thread.worker.progress:
        self.detect_thread.worker.progress.connect(
            lambda cur, total: self._set_stage_progress(
                40, 100, cur, total or max(1, total_imgs), f"Detecting… {cur}/{total or total_imgs}"
            )
        )
        self.detect_thread.worker.finished.connect(self._on_detection_finished)
        self.detect_thread.worker.error.connect(self.show_error)

        self.detect_thread.start()
        t = self.detect_thread
        t.worker.finished.connect(t.quit)
        t.finished.connect(t.deleteLater)
        t.worker.finished.connect(t.worker.deleteLater)

    def _on_detection_finished(self):
        self._set_stage_progress(40, 100, 1, 1, "Detection done (100%)")

    def _stop_thread(self, th):
        """Ask worker to cancel if available, then quit/wait/deleteLater. Safe no-op if th is None."""
        if not th:
            return
        try:
            # If the thread has a worker with a cancel() method, request stop first
            w = getattr(th, "worker", None)
            if w and hasattr(w, "cancel"):
                try: w.cancel()
                except Exception: pass
            # Exit the event loop and wait for it to finish
            th.quit()
            th.wait()
        except Exception:
            pass

    def _cancel_and_cleanup_threads(self):
        # Stop and clean all running threads
        for attr in ("synchronisation_thread", "extract_thread", "detect_thread"):
            self._stop_thread(getattr(self, attr, None))
            setattr(self, attr, None)

    # —— Called when the user presses Cancel or ESC: unified cancel entry point
    def reject(self):
        self._cancel_and_cleanup_threads()
        try:
            super().reject()  # close dialog
        except Exception:
            pass

    # —— Called when the user clicks the window’s close (X) button: also triggers cleanup
    def closeEvent(self, event):
        self._cancel_and_cleanup_threads()
        try:
            super().closeEvent(event)
        except Exception:
            pass


class FrameNumberDialog(QDialog):
    def __init__(self, default=50, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Extracted Frames")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Suggestion: 50 frames (modifiable)"))

        row = QHBoxLayout()
        row.addWidget(QLabel("Number of frames:"))
        self.spin = QSpinBox()
        self.spin.setRange(1, 2000)
        self.spin.setValue(default)
        row.addWidget(self.spin)
        lay.addLayout(row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
    
    def value(self) -> int:
            return int(self.spin.value())
