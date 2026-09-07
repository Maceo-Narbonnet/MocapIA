from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QComboBox, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QHBoxLayout, QVBoxLayout, QInputDialog, QSizePolicy, QSpacerItem
)
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import Qt, QUrl
import os, shutil, json

from Ui.widgets.Camera_List import CameraList
from Ui.widgets.Camera_status_list import StatusMonitorWidget, get_status_json_path
from Ui.widgets.Camera_Display import CameraDisplayManager
from Ui.widgets.RecordingHeader import RecordingHeader

class CaptureManagerPage(QWidget):
    """
    Capture and Video Management (tab)
    Top: Left = Start filming + CameraList + StatusMonitor
         Right = CameraDisplayManager preview
    Bottom: One-click generate folder structure from <project>/<experiment>/config.json
            and guide the user to import videos via dialogs
    """
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx

        # ========= Top: Camera modules (left + right) =========
        top_hbox = QHBoxLayout()

        # -- Left column
        left_vbox = QVBoxLayout()
        self.left_vbox = left_vbox

        # 1) Create widgets
        self.info = RecordingHeader(ctx=self.ctx, parent=self)
        self.cam_list = CameraList()
        status_path = get_status_json_path()
        self.status_box = StatusMonitorWidget(status_path)


        # 3) Set SizePolicy to avoid overlap/compression
        self.cam_list.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.status_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.status_box.setMinimumHeight(180)

        # 4) Add widgets to left column layout
        left_vbox.addWidget(self.info)
        left_vbox.addWidget(self.cam_list)
        left_vbox.addWidget(self.status_box)
        left_vbox.setContentsMargins(8, 6, 8, 8)
        left_vbox.setSpacing(6)
        top_hbox.addLayout(left_vbox, 1)
        
        left_vbox.setStretch(0, 0)  # self.info
        left_vbox.setStretch(1, 1)  # self.cam_list
        left_vbox.setStretch(2, 0)  # self.status_box

        # -- Right column: preview
        self.display = CameraDisplayManager()
        top_hbox.addWidget(self.display, 2)

        # -- Signal connections: start/stop all streams
        self.info.start_all_gopro_streams.connect(self.display.start_all_camera_streams)
        self.info.stop_all_gopro_streams.connect(self.display.stop_all_camera_streams)

        # Top margins
        top_hbox.setContentsMargins(8, 8, 8, 8)
        top_hbox.setSpacing(10)

        # ===== Bottom: Folder structure + Import =====
        bottom_hbox = QHBoxLayout()

        # --- Left side: folder structure ---
        left_box = QVBoxLayout()

        self.prepare_btn = QPushButton("Create/Update Folder Structure")
        self.refresh_btn = QPushButton("Refresh Folder List")
        left_btns = QHBoxLayout()
        left_btns.addWidget(self.prepare_btn)
        left_btns.addWidget(self.refresh_btn)
        left_box.addLayout(left_btns)

        self.folder_list = QListWidget()
        self.folder_list.setSelectionMode(QListWidget.SingleSelection)
        left_box.addWidget(self.folder_list)

        # --- Right side: Import panel (always visible) ---
        right_box = QVBoxLayout()
        right_box.addWidget(QLabel("Import Videos"))

        # Choose type: Calibration / Motion
        self.import_type = QComboBox()
        self.import_type.addItems(["Calibration", "Motion"])
        right_box.addWidget(self.import_type)

        # Choose target camera 
        self.camera_combo = QComboBox() 
        right_box.addWidget(QLabel("Target Camera:"))
        right_box.addWidget(self.camera_combo)

        # Choose files / clear list
        btn_row = QHBoxLayout()
        self.pick_btn = QPushButton("Add Files…")
        self.clear_btn = QPushButton("Clear")
        btn_row.addWidget(self.pick_btn)
        btn_row.addWidget(self.clear_btn)
        right_box.addLayout(btn_row)

        # List of files to import
        self.to_import_list = QListWidget()
        right_box.addWidget(self.to_import_list)

        # Import button
        self.import_btn = QPushButton("Import to Selected Folder")
        right_box.addWidget(self.import_btn)

        # —— Combine bottom two panels ——
        bottom_hbox.addLayout(left_box, 1)
        bottom_hbox.addLayout(right_box, 1)

        # —— Root layout ——
        root_vbox = QVBoxLayout(self)
        root_vbox.addLayout(top_hbox)
        root_vbox.addLayout(bottom_hbox)
        self.setLayout(root_vbox)

        # Event connections
        self.folder_list.itemDoubleClicked.connect(self._open_folder)
        self.prepare_btn.clicked.connect(self.prepare_folder_structure)
        self.refresh_btn.clicked.connect(self.refresh_folder_list)
        self.refresh_btn.setToolTip("Re-scan folders and cameras (use only if external changes were made)")
        self.pick_btn.clicked.connect(self._pick_files_for_import)
        self.clear_btn.clicked.connect(self._clear_import_files)
        self.import_btn.clicked.connect(self._do_import_now)

        # Initialize camera dropdown
        self._reload_camera_combo_from_config()

 

    def _experiment_paths(self):
        project = getattr(self.ctx, "project_path", None)
        exp     = getattr(self.ctx, "experiment_name", None)
        if not project or not exp:
            return None, None, None
        exp_root  = os.path.join(project, exp)
        raw_dir   = os.path.join(exp_root, "raw")
        calib_dir = os.path.join(raw_dir, "calibration")
        motion_dir= os.path.join(raw_dir, "motion")
        return exp_root, calib_dir, motion_dir

    def _get_experiment_config_path(self):
        exp_root, _, _ = self._experiment_paths()
        if not exp_root:
            return None
        return os.path.join(exp_root, "config.json")

    def _get_selected_cameras_from_config(self):
        cfg = self._get_experiment_config_path()
        cams = []
        if not cfg or not os.path.isfile(cfg):
            return cams
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
            for cam in data.get("camera_setup", []):
                name = (cam.get("name") or cam.get("camera_name") or "").strip()
                if name:
                    cams.append(name)
        except Exception as e:
            print("read config.json failed:", e)
        return cams

    def _reload_camera_combo_from_config(self):
        current = self.camera_combo.currentText()
        cams = self._get_selected_cameras_from_config()
        self.camera_combo.clear()
        if cams:
            self.camera_combo.addItems(cams)
            if current in cams:
                self.camera_combo.setCurrentText(current)


    def _fill_folder_list(self, paths):
        self.folder_list.clear()
        for p in paths:
            it = QListWidgetItem(p)
            it.setToolTip("Double-click to open this folder")
            self.folder_list.addItem(it)

    def _scan_existing_folders(self):
        """Return list of folder paths for display (calibration + motion + motion/*)"""
        _, calib_dir, motion_dir = self._experiment_paths()
        paths = []
        if calib_dir:
            if os.path.isdir(calib_dir): paths.append(calib_dir)
            if os.path.isdir(motion_dir):
                paths.append(motion_dir)
                # each camera folder
                try:
                    for name in sorted(os.listdir(motion_dir)):
                        p = os.path.join(motion_dir, name)
                        if os.path.isdir(p):
                            paths.append(p)
                except Exception:
                    pass
        return paths

    def refresh_folder_list(self):
        self._fill_folder_list(self._scan_existing_folders())
        self._reload_camera_combo_from_config()
        
    def refresh_status_box(self):
        """Reload 'current settings' from the latest status.json."""
        new_path = get_status_json_path()
        if hasattr(self.status_box, "set_json_path"):
            self.status_box.set_json_path(new_path)
        if hasattr(self.status_box, "reload"):
            self.status_box.reload()
            return
        # Otherwise: replace it in place within the left column layout
        old = self.status_box
        idx = self.left_vbox.indexOf(old)
        if idx < 0:
            # Fallback: in original layout, status_box is the third widget in the left column (index 2).
            idx = 2

        old.deleteLater()
        self.status_box = StatusMonitorWidget(new_path)

        # Reapply the same size policy as the initial setup to avoid height/compression changes.
        self.status_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.status_box.setMinimumHeight(180)

        self.left_vbox.insertWidget(idx, self.status_box)

    # ----------------- Folder generation & display -----------------

    def prepare_folder_structure(self):
        exp_root, calib_dir, motion_dir = self._experiment_paths()
        if not exp_root:
            QMessageBox.warning(self, "No experiment", "Project/Experiment is not set.")
            return

        os.makedirs(calib_dir, exist_ok=True)
        os.makedirs(motion_dir, exist_ok=True)

        cams = self._get_selected_cameras_from_config()
        created = [calib_dir, motion_dir]
        if cams:
            for cam in cams:
                p = os.path.join(motion_dir, cam)
                os.makedirs(p, exist_ok=True)
                created.append(p)
        else:
            QMessageBox.information(self, "No cameras", "No camera_setup found in config.json; only calibration/ and motion/ were created.")

        # Refresh left list & right dropdown
        self._fill_folder_list(self._scan_existing_folders())
        self._reload_camera_combo_from_config()

        QMessageBox.information(self, "Folders ready", "Folder structure has been created/updated.\nDouble-click on the left to open;\nUse the right panel to select and import videos multiple times.")


    def _pick_files_for_import(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select videos", "",
            "Videos (*.mp4 *.mov *.avi *.mkv);;All files (*)"
        )
        if not files:
            return
        for f in files:
            self.to_import_list.addItem(f)

    def _clear_import_files(self):
        self.to_import_list.clear()

    def _selected_import_target(self):
        """Return target directory path according to type and camera selection"""
        exp_root, calib_dir, motion_dir = self._experiment_paths()
        if not exp_root:
            return None
        if self.import_type.currentText() == "Calibration":
            os.makedirs(calib_dir, exist_ok=True)
            return calib_dir
        # Motion:
        cam = self.camera_combo.currentText().strip()
        if not cam:
            return None
        target = os.path.join(motion_dir, cam)
        os.makedirs(target, exist_ok=True)
        return target

    def _do_import_now(self):
        target = self._selected_import_target()
        if not target:
            QMessageBox.warning(self, "No target", "Please select a target type (for Motion, also select a camera).")
            return
        if self.to_import_list.count() == 0:
            QMessageBox.information(self, "No files", "No files selected for import.")
            return

        import_type = self.import_type.currentText().strip()
        cam = self.camera_combo.currentText().strip()

        # For both Calibration and Motion, a camera must be selected (as required by Option B)
        if not cam:
            QMessageBox.warning(self, "No camera", "Please choose a camera from the dropdown menu first.")
            return

        copied, errors = 0, []
        for i in range(self.to_import_list.count()):
            src = self.to_import_list.item(i).text()
            try:
                base = os.path.basename(src)

                if import_type == "Calibration":
                    # Key point: Add the camera name as a prefix to the file name,
                    # for example: 'Hero12_1__VID0001.mp4'
                    if not base.startswith(f"{cam}__"):
                        base = f"{cam}__{base}"
                    dst = os.path.join(target, base)
                else:
                    # Motion: the target directory is already motion/<cam>, so keep the original file name
                    dst = os.path.join(target, base)


                shutil.copy2(src, dst)
                copied += 1
            except Exception as e:
                errors.append(f"{os.path.basename(src)}: {e}")
        if errors:
            QMessageBox.warning(
                self, "Import partially failed",
                f"{copied} files copied to:\n{target}\n\nFailed:\n" + "\n".join(errors[:10])
            )
        else:
            QMessageBox.information(self, "Import done", f"{copied} files copied to:\n{target}")

        # Clear import list; refresh left folders (so user can continue to double-click open)
        self._clear_import_files()
        self.refresh_folder_list()
        
    def _open_folder(self, item):
        p = item.text()
        if os.path.isdir(p):
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))
            
    def on_enter(self):
        # If you want to auto-start preview streams when entering the page, enable here
        # self.display.start_all_camera_streams()
        if hasattr(self, "info") and self.info:
            self.info.refresh_labels()
        pass

    def on_leave(self):
        # Must stop streams when leaving the page (to save resources)
        try:
            self.display.stop_all_camera_streams()
        except Exception:
            pass
