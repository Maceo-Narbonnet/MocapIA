# Ui/dialog/Change_Reference.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QSpinBox)
from PyQt5.QtCore import Qt
import os, json
from Pose_Estimation.change_ref_pipeline import run_change_reference
from typing import List

class ChangeRefDialog(QDialog):
    def __init__(self, parent=None, preselected_video_paths=None, capture_name=None):
        super().__init__(parent)
        self.setWindowTitle("Change Reference")
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        self.capture_name = capture_name

        # project / experiment
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Project:")); self.le_project = QLineEdit(); b1 = QPushButton("Browse…")
        b1.clicked.connect(self.pick_project); r1.addWidget(self.le_project,1); r1.addWidget(b1); lay.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Experiment:")); self.le_exp = QLineEdit(); r2.addWidget(self.le_exp,1); lay.addLayout(r2)

        # ---- Output dir (read-only) ----
        r2b = QHBoxLayout()
        r2b.addWidget(QLabel("Output dir:"))
        self.le_out = QLineEdit()
        self.le_out.setReadOnly(True)
        r2b.addWidget(self.le_out, 1)
        lay.addLayout(r2b)

        def _refresh_out():
            proj = self.le_project.text().strip()
            exp  = self.le_exp.text().strip()
            self.le_out.setText(os.path.join(proj, exp, "change_ref") if proj and exp else "")


        self.le_project.textChanged.connect(lambda *_: _refresh_out())
        self.le_exp.textChanged.connect(lambda *_: _refresh_out())

        
        # videos
        r3 = QHBoxLayout()
        self.btn_pick = QPushButton("Select videos…"); self.btn_pick.clicked.connect(self.pick_videos)
        self.list_videos = QListWidget(); r3.addWidget(self.btn_pick); r3.addWidget(self.list_videos,1); lay.addLayout(r3)
        self._videos: List[str] = []
        
        # video list management buttons
        r3b = QHBoxLayout()
        self.btn_remove = QPushButton("Remove selected")
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear = QPushButton("Clear all")
        self.btn_clear.clicked.connect(self.clear_all_videos)
        r3b.addWidget(self.btn_remove)
        r3b.addWidget(self.btn_clear)
        r3b.addStretch(1)   
        lay.addLayout(r3b)



        # buttons
        r6 = QHBoxLayout()
        btn_run = QPushButton("Run"); btn_run.clicked.connect(self.run)
        btn_close = QPushButton("Close"); btn_close.clicked.connect(self.close)
        r6.addStretch(1); r6.addWidget(btn_run); r6.addWidget(btn_close); lay.addLayout(r6)

        # Pre-fill (if the main window already has values)
        mw = parent
        # If the main window has a ctx object, use ctx first; otherwise fall back to attributes
        if mw and hasattr(mw, "ctx"):
            if mw.ctx.project_path: self.le_project.setText(mw.ctx.project_path)
            if mw.ctx.experiment_name: self.le_exp.setText(mw.ctx.experiment_name)
        else:
            if mw and getattr(mw, "project_path", None): self.le_project.setText(mw.project_path)
            if mw and getattr(mw, "experiment_name", None): self.le_exp.setText(mw.experiment_name)

        _refresh_out()   # ← Use a helper function to update the output path consistently
        
        # Auto-fill video paths: use the provided paths if available;
        # otherwise try to use the capture paths (either passed in or the latest one)
        
        if preselected_video_paths:
            self._add_video_paths(preselected_video_paths)
        else:
            self._auto_prefill_videos(capture_name)            

    def pick_project(self):
        d = QFileDialog.getExistingDirectory(self, "Select project folder")
        if d:
            self.le_project.setText(d)

    def pick_videos(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select videos", "", "Videos (*.mp4 *.avi *.mov)"
        )
        if not files:
            return

        # Normalize paths and perform case-insensitive deduplication (Windows)
        norm = lambda p: os.path.normcase(os.path.normpath(p))

        # Existing set
        existing = {norm(p) for p in self._videos}

        # Only add new ones
        new_ones = [p for p in files if norm(p) not in existing]
        if not new_ones:
            return
        self._videos.extend(new_ones)

        # Only display the newly added ones (more efficient; could also clear and rebuild full list)
        for p in new_ones:
            self.list_videos.addItem(QListWidgetItem(p))
            
    def remove_selected(self):
        """Remove the currently selected videos from the list"""
        # First get the text of selected items
        selected = [i.text() for i in self.list_videos.selectedItems()]
        if not selected:
            return
        # Remove from the internal list
        to_remove = {os.path.normcase(os.path.normpath(p)) for p in selected}
        self._videos = [p for p in self._videos
                        if os.path.normcase(os.path.normpath(p)) not in to_remove]
        # Remove from the list widget
        for i in self.list_videos.selectedItems():
            row = self.list_videos.row(i)
            self.list_videos.takeItem(row)

    def clear_all_videos(self):
        """Clear all selected videos"""
        self._videos.clear()
        self.list_videos.clear()


    def run(self):
        project_path    = self.le_project.text().strip()
        experiment_name = self.le_exp.text().strip()

    
        if not (project_path and experiment_name and self._videos):
            QMessageBox.warning(self, "Missing",
                                "Please fill project/experiment and select videos.")
            return

         # output directory <project>/<experiment>/change_ref
        out_base_dir = self.le_out.text().strip() or os.path.join(project_path, experiment_name, "change_ref")
        os.makedirs(out_base_dir, exist_ok=True)

    
        prev_modality = self.windowModality()
        self.setWindowModality(Qt.NonModal)
        self.setEnabled(False)

        try:
            path = run_change_reference(
                video_paths   = self._videos,
                project_path  = project_path,
                experiment_name = experiment_name,
                out_base_dir  = out_base_dir,
                capture_name = self.capture_name,
                xlen          = 160.0,    
                ylen          = 120.0     
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        finally:
            # Restore dialog state
            self.setWindowModality(prev_modality)
            self.setEnabled(True)
            self.raise_()
            self.activateWindow()

        # After saving successfully, refresh the main window (if CSV is already open)
        mw = self.parent()
        if mw and getattr(mw, "csv_path", None):
            mw.new_plot_clicked(mw.csv_path)

        QMessageBox.information(self, "Success", f"Saved: {path}")
        self.accept()
        
        
    def _add_video_paths(self, paths: List[str]):
        """Add a batch of absolute paths into the video list 
        (remove duplicates, only add existing files)."""
        norm = lambda p: os.path.normcase(os.path.normpath(p))
        existing = {norm(p) for p in self._videos}
        added = 0
        for p in paths or []:
            if not p: 
                continue
            p = os.path.normpath(p)
            if not os.path.isfile(p):
                continue
            if norm(p) in existing:
                continue
            self._videos.append(p)
            self.list_videos.addItem(QListWidgetItem(p))
            existing.add(norm(p))
            added += 1
        return added

    def _videos_from_capture(
        self,
        project_path: str,
        experiment_name: str,
        capture_name: str
    ) -> List[str]:
        import os, json

        cap_dir = os.path.normpath(
            os.path.join(project_path, experiment_name, "captures", capture_name)
        )
        meta_path = os.path.join(cap_dir, "capture.json")

        if not os.path.isfile(meta_path):
            return []

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        camera_names = meta.get("camera_names", [])
        sources = meta.get("sources", [])

        # ip / filename -> path 映射（fallback 用）
        dir_videos = {
            fn: os.path.join(cap_dir, fn)
            for fn in os.listdir(cap_dir)
            if fn.lower().endswith((".mp4", ".avi", ".mov"))
        }

        videos = []

        for cam in camera_names:
            # 1️⃣ 先找 sources 里对应 camera
            entry = next((s for s in sources if s.get("camera") == cam), None)

            path = None
            if entry:
                p = os.path.normpath(entry.get("path", ""))
                if p and not os.path.isabs(p):
                    p = os.path.join(cap_dir, p)
                if p and os.path.isfile(p):
                    path = p
                else:
                    # 2️⃣ sources 失效 → 用文件名兜底
                    fn = os.path.basename(p)
                    alt = dir_videos.get(fn)
                    if alt and os.path.isfile(alt):
                        path = alt

            # 3️⃣ 如果还没找到 → 从剩余视频里拿一个
            if path is None and dir_videos:
                path = sorted(dir_videos.values())[0]

            if path:
                videos.append(os.path.normpath(path))
                # 防止被下一个 camera 误用
                dir_videos.pop(os.path.basename(path), None)

        # debug
        for i, v in enumerate(videos, 1):
            print(f"cam{i} ({camera_names[i-1]}): {v}")

        return videos



    def _auto_prefill_videos(self, capture_name: str = None):
        """Auto-prefill: use the specified capture if given; 
        otherwise select the most recently modified one under captures."""
        project_path = self.le_project.text().strip()
        experiment_name = self.le_exp.text().strip()
        if not (project_path and experiment_name):
            return

        caps_root = os.path.join(project_path, experiment_name, "captures")
        if not os.path.isdir(caps_root):
            return

        target_cap = capture_name
        if not target_cap:
            # Select the most recently modified subdirectory

            subdirs = [d for d in os.listdir(caps_root) if os.path.isdir(os.path.join(caps_root, d))]
            if not subdirs:
                return
            subdirs.sort(key=lambda d: os.path.getmtime(os.path.join(caps_root, d)), reverse=True)
            target_cap = subdirs[0]

        videos = self._videos_from_capture(project_path, experiment_name, target_cap)
        if not videos:
            return

        added = self._add_video_paths(videos)
        if added:
            print(f"[ChangeRef] Auto prefilled {added} video(s) from capture: {target_cap}")


