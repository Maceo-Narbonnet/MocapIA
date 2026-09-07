# Ui/pages/ExperimentHomePage.py
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox,  QInputDialog, QGroupBox, QDialog, QProgressBar, QProgressDialog, QTextEdit
)
from PyQt5.QtCore import QDateTime, Qt
import os, json, re
from Ui.dialog.Start_Extrinsic_Calibration import EnterVideoNumber
from Ui.dialog.Change_Reference import ChangeRefDialog
from Pose_Estimation.Triangulator import Triangulator
from Ui.threads.SynchronisationThread import SynchronisationThread
from services.ai_analysis_service import AIAnalysisService
from Ui.dialog.Log_information import LogInformation
CAPTURE_ROOT_DIRNAME = "captures"   

def _ensure_dir(p): os.makedirs(p, exist_ok=True); return p
class SyncProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Synchronizing videos…")
        self.setWindowModality(Qt.ApplicationModal)
        self.setMinimumWidth(420)

        self.label = QLabel("Synchronizing videos. Please wait…")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.btn_cancel = QPushButton("Cancel")

        lay = QVBoxLayout(self)
        lay.addWidget(self.label)
        lay.addWidget(self.bar)
        lay.addWidget(self.btn_cancel)

        self.btn_cancel.clicked.connect(self.reject)

    def set_progress(self, p: int):
        self.bar.setValue(max(0, min(int(p), 100)))
class ExperimentHomePage(QWidget):
    """
    Experiment Home
    - Top: Project / Experiment + action buttons
    - Bottom: left = Capture list; right = Capture details/actions
    """
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        project_name = re.split(r'[\\/]', self.ctx.project_path)[-1]

        # ===== Top title + actions =====
        title_box = QVBoxLayout()
        self.project_label   = QLabel(f"Project : {project_name}")
        self.experiment_label= QLabel(f"Experiment : {getattr(ctx,'experiment_name','unknown')}")
        self.project_label.setStyleSheet("font-weight:600; font-size:14px;")
        self.experiment_label.setStyleSheet("font-size:13px;")
        title_box.addWidget(self.project_label)
        title_box.addWidget(self.experiment_label)

        btn_box = QHBoxLayout()
        self.btn_extrinsic = QPushButton("Start Extrinsic Calibration")
        self.btn_ref_frame = QPushButton("Set Reference Frame")
        self.btn_new_cap   = QPushButton("New Capture...")
        self.btn_start_ai  = QPushButton("Start AI Analysis")
        self.btn_open_analysis = QPushButton("Open Analysis")  # acts on the selected capture
        self.btn_logs = QPushButton("Logs")
        self.btn_start_ai.setToolTip("Run AI on the selected capture")
        for b in (self.btn_extrinsic, self.btn_ref_frame, self.btn_new_cap, self.btn_start_ai, self.btn_open_analysis,self.btn_logs):
            b.setMinimumHeight(28)
        btn_box.addWidget(self.btn_extrinsic)
        btn_box.addWidget(self.btn_ref_frame)
        btn_box.addWidget(self.btn_new_cap)
        btn_box.addWidget(self.btn_start_ai)
        btn_box.addWidget(self.btn_open_analysis)
        btn_box.addWidget(self.btn_logs)
        self.btn_extrinsic.clicked.connect(self._start_extrinsic_clicked)
        self.btn_ref_frame.clicked.connect(self._set_ref_frame_clicked)
        self.btn_start_ai.clicked.connect(self._start_ai_clicked)
        self.btn_logs.clicked.connect(self._open_logs_clicked)

        header = QHBoxLayout()
        header.addLayout(title_box, 1)
        header.addLayout(btn_box, 2)

        # ===== Bottom: left = table, right = details =====
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Camera", "Files", "Created"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setEditTriggers(self.table.NoEditTriggers)

        self.detail_box = QGroupBox("Capture Details")
        detail_layout = QVBoxLayout(self.detail_box)
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text)

        bottom = QHBoxLayout()
        bottom.addWidget(self.table, 3)
        bottom.addWidget(self.detail_box, 2)

        # ===== Root layout =====
        root = QVBoxLayout(self)
        root.addLayout(header)
        root.addLayout(bottom)
        self.setLayout(root)

        # ===== Signals =====
        self.table.itemSelectionChanged.connect(self._on_select_capture)
        self.btn_new_cap.clicked.connect(self._new_capture_flow)
        self.btn_open_analysis.clicked.connect(self._open_analysis_clicked)
                # --- AI service on this page ---
        self.ai = AIAnalysisService(ctx=self.ctx, parent=self)
        self._ai_progress = None


        self.ai.started.connect(self._on_ai_started)
        self.ai.progress.connect(self._on_ai_progress)
        self.ai.failed.connect(self._on_ai_failed)
        self.ai.finished.connect(self._on_ai_finished)
        self.ai.cancelled.connect(self._on_ai_cancelled)


    # ---------- Paths / Metadata ----------
    def _exp_root(self):
        pj, ex = getattr(self.ctx, "project_path", None), getattr(self.ctx, "experiment_name", None)
        return os.path.join(pj, ex) if pj and ex else None

    def _cap_root(self):
        r = self._exp_root()
        return _ensure_dir(os.path.join(r, CAPTURE_ROOT_DIRNAME)) if r else None


    def _ensure_ctx_ready(self) -> bool:
        if not getattr(self.ctx, "project_path", None) or not getattr(self.ctx, "experiment_name", None):
            QMessageBox.warning(self, "Missing info", "Please open a project and select/create an experiment first.")
            return False
        return True

    def _start_extrinsic_clicked(self):
        if not self._ensure_ctx_ready():
            return
        dlg = EnterVideoNumber(ctx=self.ctx, parent=self)
        dlg.exec_()  # Inside it continues your existing flow (select videos / extract frames / ...)

    def _set_ref_frame_clicked(self):
        # 1) Basic validation
        if not getattr(self.ctx, "project_path", None) or not getattr(self.ctx, "experiment_name", None):
            QMessageBox.warning(self, "Missing info", "Please open a project and select an experiment first.")
            return

        # 2) If there is a selection in the table, use that capture's videos as pre-selected inputs
        preselected = []
        cap_name = None
        rows = self.table.selectionModel().selectedRows() if hasattr(self, "table") else []
        if not rows:
            if self.table.rowCount() > 0:
                self.table.selectRow(0)
                rows = self.table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            cap_name = self.table.item(row, 0).text()
            cap_dir = os.path.join(self.ctx.project_path, self.ctx.experiment_name, "captures", cap_name)
            meta_path = os.path.join(cap_dir, "capture.json")

            try:
                if os.path.isfile(meta_path):
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    # Priority: absolute paths stored in "sources"
                    srcs = meta.get("sources") or []
                    for s in srcs:
                        p = s.get("path")
                        if p and os.path.isfile(p):
                            preselected.append(os.path.normpath(p))
                    # Fallback: filenames within the capture directory (legacy flow)
                    if not preselected:
                        files = meta.get("files") or []
                        for fn in files:
                            p = os.path.join(cap_dir, fn)
                            if os.path.isfile(p):
                                preselected.append(os.path.normpath(p))
            except Exception as e:
                print("read capture.json for preselect failed:", e)

        # If still nothing, a fallback could be opening raw/motion as the initial dir (optional)
        # raw_motion_dir = os.path.join(self.ctx.project_path, self.ctx.experiment_name, "raw", "motion")

        # 3) Open ChangeRefDialog and inject the pre-selected videos
        dlg = ChangeRefDialog(self.window(), preselected_video_paths=preselected, capture_name=cap_name)
        dlg.le_project.setText(self.ctx.project_path)
        dlg.le_exp.setText(self.ctx.experiment_name)
        dlg.le_out.setText(os.path.join(self.ctx.project_path, self.ctx.experiment_name, "change_ref"))
        dlg.exec_()

        # 4) After closing, if the Analysis page already has a CSV loaded, refresh it in place
        win = self.window()
        page = getattr(win, "_ensure_page", lambda *_: None)("analysis") if hasattr(win, "_ensure_page") else None
        if page and getattr(page, "csv_path", None):
            try:
                page._load_csv_file(page.csv_path)
                if hasattr(page, "csv_edit"):
                    page.csv_edit.setText(page.csv_path)
            except Exception as e:
                QMessageBox.information(self, "Refresh Analysis",
                                        f"Reference changed, but failed to refresh CSV:\n{e}")


    # ---------- Load / refresh list ----------

    def _load_capture_list(self):
        self.table.setRowCount(0)
        cap_root = self._cap_root()
        if not cap_root: return
        # Iterate subfolders and read capture.json
        for name in sorted(os.listdir(cap_root)):
            p = os.path.join(cap_root, name)
            if not os.path.isdir(p): continue
            meta = self._read_capture_meta(p)
            files_count = len(meta.get("files", [])) or len(meta.get("sources", []))
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(meta.get("name", name)))

            names = meta.get("camera_names")
            if not names:
                # Backward-compat: old capture.json without camera_names
                names = [ (s.get("camera") or "").strip()
                        for s in meta.get("sources", [])
                        if s.get("camera") ]
            cam_text = ", ".join([n for n in names if n]) or str(meta.get("camera") or "-")

            item_cam = QTableWidgetItem(cam_text)
            item_cam.setToolTip(cam_text)
            self.table.setItem(row, 1, item_cam)
            self.table.setItem(row, 2, QTableWidgetItem(str(files_count)))
            self.table.setItem(row, 3, QTableWidgetItem(meta.get("created", "-")))
            self.table.setRowHeight(row, 24)
        if self.table.rowCount():
            self.table.selectRow(self.table.rowCount() - 1)


    def _read_capture_meta(self, folder):
        meta = {"path": folder}
        jf = os.path.join(folder, "capture.json")
        try:
            if os.path.isfile(jf):
                with open(jf, "r", encoding="utf-8") as f:
                    meta.update(json.load(f))
        except Exception as e:
            print("read capture.json err:", e)
        return meta

    def _pick_motion_files_multi(self, start_dir: str):
        """
        Repeatedly open a file dialog to accumulate selected videos until the user cancels.
        Returns a de-duplicated list of absolute paths (sorted).
        """
        all_files = []
        last_dir = start_dir

        while True:
            files, _ = QFileDialog.getOpenFileNames(
                self,
                "Select videos (you can add multiple times)",
                last_dir,
                "Videos (*.mp4 *.mov *.avi *.mkv *.m4v *.webm);;All files (*)"
            )
            if not files:
                break
            all_files.extend(files)
            # Remember the directory of the last selection
            try:
                last_dir = os.path.dirname(files[0])
            except Exception:
                pass

            # Add more?
            more = QMessageBox.question(
                self, "Add more files?",
                "Do you want to add more videos?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if more != QMessageBox.Yes:
                break

        # De-duplicate and sort
        uniq = sorted(set(os.path.normpath(p) for p in all_files))
        return uniq


    def _new_capture_flow(self):
        exp_root = self._exp_root()
        if not exp_root:
            QMessageBox.warning(self, "No experiment", "Project/Experiment not set.")
            return

        # Fixed to Motion; initial directory: <project>/<experiment>/raw/motion
        raw_motion_dir = os.path.join(exp_root, "raw", "motion")
        if not os.path.isdir(raw_motion_dir):
            QMessageBox.warning(self, "No motion folder", f"Not found:\n{raw_motion_dir}")
            return

        # A) Let the user pick files multiple times until they are done
        files = self._pick_motion_files_multi(raw_motion_dir)
        if not files:
            return

        # B) Ask for an action name (the directory name = user input; auto-suffix if duplicated)
        action_name, ok = QInputDialog.getText(self, "Action name", "Give this motion a name:")
        if not ok:
            return
        action_name = (action_name or "").strip()
        if not action_name:
            QMessageBox.warning(self, "Invalid name", "Name cannot be empty.")
            return

        # Sanitize invalid filename characters (cross-platform subset)
        for ch in '\\/:*?"<>|':
            action_name = action_name.replace(ch, "_")

        # C) Create capture folder and metadata (no copy: sources point to absolute paths)
        # Folder name = action_name; if duplicated, append _2/_3/...
        base_name = action_name
        cap_dir = os.path.join(self._cap_root(), base_name)
        if os.path.exists(cap_dir):
            i = 2
            while os.path.exists(os.path.join(self._cap_root(), f"{base_name}_{i}")):
                i += 1
            action_name = f"{base_name}_{i}"
            cap_dir = os.path.join(self._cap_root(), action_name)
        cap_dir = _ensure_dir(cap_dir)
        cap_name = action_name  # keep folder name and display name consistent

        def _camera_of(path: str) -> str:
            # Assume structure: .../<CameraName>/<filename>
            return os.path.basename(os.path.dirname(path))

        name2ip = self._camera_name_to_ip_map()
        missing = []

        sources = []
        for p in files:
            cam_name = _camera_of(p)
            ip = name2ip.get(cam_name, "")
            if not ip:
                missing.append(cam_name)
            sources.append({"camera": cam_name, "ip": ip, "path": p})

        # Precompute camera_names (before writing meta)
        cam_names = sorted({
            (s.get("camera") or "").strip()
            for s in sources
            if s.get("camera")
        })

        # Optional: if some camera names have no IP mapping, inform the user (non-blocking)
        if missing:
            QMessageBox.information(
                self, "Missing camera IP",
                "These camera names were not found in config.json:\n- " + "\n- ".join(sorted(set(missing))) +
                "\n\nThe 'ip' field was left empty for them. Triangulator will not use these cameras. "
                "Please check 'camera_setup' in config.json."
            )

        meta = {
            "name": cap_name,                         # = folder name = user input (with possible auto suffix)
            "camera": "multi",                        # legacy compatibility
            "camera_names": cam_names,                # new field: list of all camera names
            "action": base_name,                      # original input (without auto suffix), for display
            "created": QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss"),
            "files": [os.path.basename(p) for p in files],  # for table display only
            "sources": sources,                       # core: absolute paths
            "paths": {"folder": cap_dir}
        }

        with open(os.path.join(cap_dir, "capture.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # --- Synchronize videos right after creation ---
        try:
            self._sync_videos_for_capture(
                self.ctx.project_path,
                self.ctx.experiment_name,
                cap_name
            )
        except Exception as e:
            print("[SYNC] Failed to synchronize videos:", e)

        # D) Refresh list + notify
        self._load_capture_list()
        QMessageBox.information(
            self, "Capture created",
            f"Action '{cap_name}' with {len(files)} file(s).\nSaved to: {cap_dir}"
        )


    def _sync_videos_for_capture(self, project_path: str, experiment_name: str, capture_name: str) -> None:
        """
        Use SynchronisationThread to synchronize videos and display a progress dialog.
        After synchronization, update capture.json so that sources.path points to the 
        synchronized <ip>.mp4 files.
        """
        cap_dir = os.path.join(project_path, experiment_name, "captures", capture_name)
        meta_path = os.path.join(cap_dir, "capture.json")
        if not os.path.isfile(meta_path):
            print(f"[SYNC] no capture.json at {meta_path}")
            return

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        sources = meta.get("sources") or []

        tri = Triangulator(project_path, experiment_name, capture_name)
        name2ip = tri._load_camera_name_to_id_mapping()   # e.g. {"Hero12_2": "C3501..."}

        # Build input and output paths
        video_paths, save_paths = [], []
        for s in sources:
            if not isinstance(s, dict):
                continue
            cam_name = s.get("camera")
            raw_path = s.get("path")
            cam_ip   = name2ip.get(cam_name, "")
            if not raw_path or not cam_ip:
                print(f"[SYNC] skip: camera_name={cam_name}, path={raw_path}")
                continue
            out_mp4 = os.path.join(cap_dir, f"{cam_ip}.mp4")
            video_paths.append(raw_path)
            save_paths.append(out_mp4)

        if len(video_paths) < 2:
            print("[SYNC] need >=2 videos to synchronize; skip")
            return

        # --- Run the synchronization thread and display a progress dialog ---
        dlg = SyncProgressDialog(self)
        # Keep a reference to the thread to prevent it from being garbage collected
        self._sync_thread = SynchronisationThread(video_paths, save_paths, parent=self)
        thr = self._sync_thread

        # Connect progress / error / finish signals
        thr.worker.progress.connect(dlg.set_progress)
        def _on_error(msg: str):
            dlg.label.setText(f"Error: {msg}")
        thr.worker.error.connect(_on_error)

        # When finished: close the dialog
        def _on_finish():
            try:
                dlg.accept()
            except Exception:
                pass
        thr.worker.finished.connect(_on_finish)

        # When cancelled: send cancel signal and close dialog
        def _on_cancel():
            try:
                thr.cancel()
            except Exception:
                pass
            dlg.reject()
        dlg.btn_cancel.clicked.disconnect()
        dlg.btn_cancel.clicked.connect(_on_cancel)

        # Start synchronization
        thr.start()
        ok = dlg.exec_()  # Modal display until accept/reject is called

        # If the user cancelled, just return without updating meta
        if ok != QDialog.Accepted:
            print("[SYNC] cancelled by user.")
            return

        # --- Synchronization completed: update capture.json so that each source points 
        #     to the new <ip>.mp4 file, and mark the capture as synced ---
        new_sources = []
        for s in sources:
            cam_name = s.get("camera")
            cam_ip   = name2ip.get(cam_name, "")
            if cam_ip:
                synced_path = os.path.join(cap_dir, f"{cam_ip}.mp4")
                if os.path.isfile(synced_path):
                    s["path"] = synced_path
            new_sources.append(s)

        meta["sources"] = new_sources
        meta["synced"] = True

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"[SYNC] capture.json updated → {meta_path}")


    def _start_ai_clicked(self):
        # Get the selected capture name (assuming it's in column 0)
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No capture", "Please select a capture first.")
            return
        item = self.table.item(row, 0)
        cap_name = item.text().strip() if item else ""
        if not cap_name:
            QMessageBox.information(self, "No capture", "Please select a valid capture.")
            return

        experiment = getattr(self.ctx, "experiment_name", "") or ""
        if not experiment:
            QMessageBox.information(self, "No experiment", "Please set an experiment first.")
            return


        # Start the AI process (using the AI service of this page directly)
        self.ai.start(experiment, cap_name)





    # ---------- Show details of the selected item ----------
    def _on_select_capture(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.detail_text.clear()
            return
        row = rows[0].row()
        name = self.table.item(row, 0).text()
        cap_dir = os.path.join(self._cap_root(), name)
        meta = self._read_capture_meta(cap_dir)
        txt = json.dumps(meta, ensure_ascii=False, indent=2)
        self.detail_text.setText(txt)

    # ---------- Open Analysis (you can wire this to an Analysis page in MainWindow) ----------
    def _open_analysis_clicked(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "No selection", "Please select a capture.")
            return

        row = rows[0].row()
        cap_name = self.table.item(row, 0).text()

        # analysis directory: <project>/<experiment>/analysis/<capture_name>/
        exp_root = self._exp_root()
        if not exp_root:
            QMessageBox.warning(self, "No experiment", "Project/Experiment not set.")
            return
        ana_dir = os.path.join(exp_root, "analysis", cap_name)
        if not os.path.isdir(ana_dir):
            QMessageBox.warning(
                self,
                "No analysis folder",
                f"Not found:\n{ana_dir}\n\nPlease run “Start AI Analysis” first to generate the results."
            )
            return

        # 1) Prefer *_3D_points*.csv
        candidates = [os.path.join(ana_dir, f) for f in os.listdir(ana_dir) if f.lower().endswith(".csv")]
        preferred = [p for p in candidates if "_3d_points" in os.path.basename(p).lower()]
        csv_path = preferred[0] if preferred else (candidates[0] if candidates else None)

        if not csv_path:
            QMessageBox.information(
                self,
                "CSV not found",
                f"No CSV found in:\n{ana_dir}\n\nPlease complete the AI analysis first (to generate the 3D CSV)."
            )
            return

        # 2) Delegate to the main window to switch page and load
        win = self.window()
        if hasattr(win, "open_analysis_with_csv"):
            win.open_analysis_with_csv(csv_path)
        else:
            # Compatibility: if MainWindow hasn't exposed that method, switch page manually and call AnalysisPage
            if hasattr(win, "_ensure_page") and hasattr(win, "_switch_to"):
                page = win._ensure_page("analysis")
                win._switch_to("analysis")
                try:
                    page._load_csv_file(csv_path)
                    if hasattr(page, "csv_edit"):
                        page.csv_edit.setText(csv_path)
                except Exception as e:
                    QMessageBox.critical(self, "Load CSV failed", str(e))
            else:
                QMessageBox.information(
                    self,
                    "Wiring missing",
                    "Cannot switch to the Analysis page. Please expose open_analysis_with_csv on MainWindow."
                )

    def on_enter(self):
        try:
            project_name = re.split(r'[\\/]', getattr(self.ctx, 'project_path', ''))[-1] or 'unknown'
            self.project_label.setText(f"Project : {project_name}")
            self.experiment_label.setText(f"Experiment : {getattr(self.ctx,'experiment_name','unknown')}")
            self._load_capture_list()
        except Exception:
            pass

    def _camera_name_to_ip_map(self) -> dict:
        """
        Read <project>/<experiment>/config.json 'camera_setup' and return
        {camera_name -> ip}, e.g., {"Hero12_1": "C3501350052453", ...}
        """
        import os, json
        try:
            exp_root = self._exp_root()
            if not exp_root:
                return {}
            cfg = os.path.join(exp_root, "config.json")
            if not os.path.isfile(cfg):
                return {}
            with open(cfg, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            mapping = {}
            for c in data.get("camera_setup", []):
                name = (c.get("name") or "").strip()
                ip   = (c.get("ip")   or "").strip()
                if name and ip:
                    mapping[name] = ip
            return mapping
        except Exception as e:
            print("read name->ip mapping failed:", e)
            return {}

    def on_leave(self):
        """Actions when leaving this page: typically nothing; stop QTimer here if present."""
        try:
            if hasattr(self, "refresh_timer"):
                self.refresh_timer.stop()
        except Exception:
            pass
        
    def _on_ai_started(self, *_):
        if self._ai_progress is None:
            dlg = QProgressDialog("AI analysis running…", None, 0, 0, self)
            dlg.setWindowTitle("AI Analysis")
            dlg.setAutoClose(True)
            dlg.setAutoReset(False)
            dlg.setMinimumDuration(0)
            self._ai_progress = dlg
            dlg.show()
            
    def _on_ai_progress(self, cur, total):
        if self._ai_progress:
            self._ai_progress.setRange(0, max(1, int(total)))
            self._ai_progress.setValue(max(0, int(cur)))
            self._ai_progress.setLabelText(f"3D triangulation… {cur}/{total}")

    def _on_ai_failed(self, msg: str):
        if self._ai_progress:
            try:
                self._ai_progress.close()
            except Exception:
                pass
            self._ai_progress = None
        QMessageBox.critical(self, "AI Analysis Failed", msg)

    def _on_ai_finished(self, *_):
        if self._ai_progress:
            try:
                self._ai_progress.setValue(self._ai_progress.maximum())
                self._ai_progress.close()
            except Exception:
                pass
            self._ai_progress = None
        QMessageBox.information(self, "AI Analysis", "The AI analysis has been completed successfully.")

    def _on_ai_cancelled(self, *_):
        if self._ai_progress:
            try:
                self._ai_progress.close()
            except Exception:
                pass
            self._ai_progress = None
        QMessageBox.information(self, "AI Analysis", "Analysis cancelled by user.")
        
    def _open_logs_clicked(self):
        """
        Open the LogInformation dialog (it redirects stdout/stderr while open).
        Keep a single instance so repeated clicks simply bring the window to front.
        """
        # If a dialog already exists and is visible, just focus it
        dlg = getattr(self, "_log_dialog", None)
        if dlg is not None and dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()
            return

        # Your LogInformation requires `script_path` and `working_dir`.
        # In the current implementation, it only handles stdout/stderr redirection
        # and does not launch any external worker;
        # so passing an empty string or the current project directory is enough.
        script_path = ""  # Placeholder; fill in a real path if you need to run external scripts
        working_dir = getattr(self.ctx, "project_path", "") or ""

        dlg = LogInformation(script_path=script_path, working_dir=working_dir, parent=self)
        self._log_dialog = dlg

        # When the dialog closes, clear the reference to avoid stale pointers
        try:
            dlg.finished.connect(lambda _=None: setattr(self, "_log_dialog", None))
        except Exception:
            pass
