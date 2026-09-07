import os
from PyQt5.QtWidgets import (
    QWidget, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt
from Ui.widgets.Plot_Manager import (
    TimelineManager,
    PlotManager,
    Render3D_With_Buttons,
)
from Pose_Estimation import csv_reader as csv
# from Pose_Estimation.change_ref_store import load_T
from Ui.widgets.Camera_framerate import CameraFramerateMonitorWidget
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import logging

class AnalysisPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.logger = logging.getLogger("AnalysisPage")
        # --- Top-level layout ---
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.grid.setSpacing(8)

        # ========== Top toolbar ==========
        self.csv_edit = QLineEdit()
        self.csv_edit.setPlaceholderText("Path to CSV file (OpenPose/Your export)")
        self.csv_edit.setClearButtonEnabled(True)

        self.btn_browse = QPushButton("Browse…")
        self.btn_load   = QPushButton("Load CSV")

        top = QHBoxLayout()
        top.addWidget(QLabel("CSV:"))
        top.addWidget(self.csv_edit, 1)
        top.addWidget(self.btn_browse, 0)
        top.addWidget(self.btn_load,   0)

        # ========== Middle: two columns (left & right) ==========
        # Left: 2D Plot (placeholder)
        self.plot2d_placeholder = QLabel("2D Plot")
        self.plot2d_placeholder.setAlignment(Qt.AlignCenter)
        self.plot2d_placeholder.setStyleSheet("color:#999; border:1px dashed rgba(255,255,255,0.2);")
        self.plot2d_placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Right: 3D Render + Camera Used List (placeholder)
        self.plot3d_placeholder = QLabel("3D Render")
        self.plot3d_placeholder.setAlignment(Qt.AlignCenter)
        self.plot3d_placeholder.setStyleSheet("color:#999; border:1px dashed rgba(255,255,255,0.2);")
        self.plot3d_placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.camera_used_list = None  # created after loading

        # ========== Bottom：Timeline ==========
        self.timeline = TimelineManager()

        # Place in grid: row 0 = top toolbar; row 1 = left & right; row 2 = timeline
        self.grid.addLayout(top,                     0, 0, 1, 2) 
        self.grid.addWidget(self.plot2d_placeholder, 1, 0, 1, 1)
        self.grid.addWidget(self.plot3d_placeholder, 1, 1, 1, 1)
        self.grid.addWidget(self.timeline,           2, 0, 1, 2)

        self.plot2D_manager = None
        self.plot3D_manager = None
        self.csv_path = None
        self.base_dir = None
        self.experiment_name = None
        self.config_path = None

        # Signal bindings
        self.btn_browse.clicked.connect(self._browse_csv)
        self.btn_load.clicked.connect(self._load_csv_clicked)

    # ---------------- **Top toolbar actions** ----------------
    def _browse_csv(self):
        start_dir = self._exp_root() or os.getcwd()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose CSV",
            start_dir,
            "CSV files (*.csv);;All files (*)"
        )
        if path:
            self.csv_edit.setText(path)

    def _load_csv_clicked(self):
        path = self.csv_edit.text().strip()
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "CSV not found", "Please choose a valid CSV file.")
            return
        try:
            self._load_csv_file(path)
        except Exception as e:
            QMessageBox.critical(self, "Load failed", f"Failed to load CSV:\n{e}")

    # ---------------- Core: load CSV and build visualizations ----------------
    def _load_csv_file(self, file_path: str):
        # 0) Normalize the path to use consistent separators (fix mixed slashes)
        file_path = os.path.normpath(file_path)
        
        # 1) Use the exact file the user selected (respect their choice)
        actual_path = file_path
        self.logger.info(f"Using selected CSV: {actual_path}")
        print(f"[ANALYSIS PAGE] Using CSV: {actual_path}")

        # 1) Parse path structure (compatible with your legacy StateAnalysis approach)
        reader = csv.CSVReader(actual_path, skiprows=2, sep=",")
        self.csv_path = actual_path

        # Update the text field to show which file is actually loaded
        if hasattr(self, "csv_edit"):
            self.csv_edit.setText(actual_path)


        # According to your previous inference: …/<project>/<experiment>/…/xx.csv
        experiment_path = os.path.dirname(os.path.dirname(os.path.dirname(file_path)))
        self.base_dir = experiment_path
        self.experiment_name = os.path.basename(experiment_path)
        project_path = os.path.dirname(experiment_path)
        self.config_path = os.path.join(experiment_path, "config.json")

        # 2) Load reference-frame transform T (if the module is available)
        T = None
        # 3) Read 3D keypoints (via your csv_reader interface)
        labels = [
            "Nose","LEye","REye","LEar","REar","LShoulder","RShoulder","LElbow","RElbow",
            "LWrist","RWrist","LHip","RHip","LKnee","RKnee","LAnkle","RAnkle","Head",
            "Neck","Hip","LBigToe","RBigToe","LSmallToe","RSmallToe","LHeel","RHeel"
        ]
        points = reader.convert_csv_to_point3D(labels)

        # 4) Clean up previous visualization widgets
        self._delete_if_exists(self.plot2D_manager)
        self._delete_if_exists(self.plot3D_manager)
        self.plot2D_manager = None
        self.plot3D_manager = None
        if self.camera_used_list:
            self._delete_if_exists(self.camera_used_list)
            self.camera_used_list = None
        
        print("Deleting done; forcing event loop sync")
        QApplication.processEvents()
        QTimer.singleShot(50, lambda: self._create_visualizations(file_path,points))

        # # 5) Create new visualization widgets and place them in the layout
        # self.plot2D_manager = PlotManager(self.timeline, file_path, points)
        # self.plot3D_manager = Render3D_With_Buttons(self.timeline, file_path, points, framerate=30)

        # self.grid.addWidget(self.plot2D_manager, 1, 0, 1, 1)
        # self.grid.addWidget(self.plot3D_manager, 1, 1, 1, 1)

        # Right-bottom: camera usage list (if a config is present)
        if os.path.isfile(self.config_path):
            self.camera_used_list = CameraFramerateMonitorWidget(self.config_path)
            self.grid.addWidget(self.camera_used_list, 3, 1, 1, 1)

        # 6) Remove placeholders (if they are still present)
        self._delete_if_exists(self.plot2d_placeholder)
        self._delete_if_exists(self.plot3d_placeholder)
        self.plot2d_placeholder = None
        self.plot3d_placeholder = None
        
    def _create_visualizations(self, file_path, points):
        self.plot2D_manager = PlotManager(self.timeline, file_path, points)
        self.plot3D_manager = Render3D_With_Buttons(self.timeline, file_path, points, framerate=30)
        self.grid.addWidget(self.plot2D_manager, 1, 0, 1, 1)
        self.grid.addWidget(self.plot3D_manager, 1, 1, 1, 1)


    # ---------------- Lifecycle hooks ----------------
    def on_enter(self):
        """Triggered when switching to this page (optional)"""
        # If you want to auto-resume rendering/timers, check/start here
        pass

    def on_leave(self):
        for attr in ("plot2D_manager", "plot3D_manager", "camera_used_list"):
            w = getattr(self, attr, None)
            self._safe_stop_widget(w)
            setattr(self, attr, None)

    # ---------------- Utility functions ----------------
    def _exp_root(self):
        pj = getattr(self.ctx, "project_path", None)
        ex = getattr(self.ctx, "experiment_name", None)
        return os.path.join(pj, ex) if pj and ex else None

    def _delete_if_exists(self, w):
        if w is None:
            return
        try:
            w.setParent(None)
        except Exception:
            pass
        try:
            w.deleteLater()
        except Exception:
            pass

    def _safe_stop_widget(self, w):
        """Safely stop and release a Qt object that may already be destroyed"""
        if not w:
            return

        # Detect whether it has been destroyed: access a Qt method; if RuntimeError is raised, treat as deleted
        try:
            _ = w.objectName()
        except RuntimeError:
            return

        # Try stop/close methods one by one
        for meth in ("stop", "stop_all", "shutdown", "close"):
            try:
                fn = getattr(w, meth, None)
            except RuntimeError:
                return
            if callable(fn):
                try:
                    fn()
                except Exception as e:
                    print(f"_safe_stop_widget {meth} error:", e)

        # Request deferred deletion (if still alive)
        try:
            w.deleteLater()
        except RuntimeError:
            pass
