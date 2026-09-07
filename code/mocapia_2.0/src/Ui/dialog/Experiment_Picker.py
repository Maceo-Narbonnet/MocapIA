# Ui/dialog/Experiment_Picker.py
import os, re, datetime, json
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QListWidget, QLineEdit,
    QLabel, QDialogButtonBox, QMessageBox, QHBoxLayout
)
from config.Project import MocapProject
from Ui.widgets.CameraSetUpPanel import CameraSetupPanel
from config.Config_Manager import StatusManager
import io, contextlib

SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-]+$")  # Allowed characters

class ExperimentPickerDialog(QDialog):
    """
    A dialog that provides both:
      - Open Experiment (list)
      - New Experiment (input name)
    Clicking OK executes the corresponding logic of the current Tab,
    and the result is stored in self.experiment_name.
    """
    def __init__(self, project_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select or Create Experiment")
        self.setMinimumSize(600, 500)
        self.project_path = project_path
        self.project = MocapProject(project_path)
        self.experiment_name = None  # Caller reads this after exec_()

        # ---------- Tabs ----------
        self.tabs = QTabWidget()
        self.tab_open = QWidget()
        self.tab_new  = QWidget()
        self.tabs.addTab(self.tab_open, "Open")
        self.tabs.addTab(self.tab_new,  "New")

        # ---------- Open tab ----------
        self.listw = QListWidget()
        self._load_experiment_list()
        self.listw.itemDoubleClicked.connect(self._accept_open)  # Double-click to open

        lay_open = QVBoxLayout(self.tab_open)
        lay_open.addWidget(QLabel("Existing experiments:"))
        lay_open.addWidget(self.listw)

        # ---------- New tab ----------
        self.name_edit = QLineEdit()
        self.name_edit.setText(datetime.datetime.now().strftime("%Y%m%d_%H%M"))

        help_line = QLabel("Allowed: letters, numbers, '_' and '-'")
        help_line.setStyleSheet("color: gray;")

        lay_new = QVBoxLayout(self.tab_new)
        row = QHBoxLayout()
        row.addWidget(QLabel("New experiment name:"))
        row.addWidget(self.name_edit)
        lay_new.addLayout(row)
        lay_new.addWidget(help_line)
        self.cam_panel = CameraSetupPanel(parent=self.tab_new)
        lay_new.addWidget(self.cam_panel)
        lay_new.addStretch(1)

        # ---------- Buttons ----------
        self.btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btns.accepted.connect(self._on_ok)
        self.btns.rejected.connect(self.reject)

        # ---------- Root Layout ----------
        root = QVBoxLayout(self)
        root.addWidget(self.tabs)
        root.addWidget(self.btns)

    def _load_experiment_list(self):
        """Prefer using MocapProject.get_experiment_list(); fallback to directory scan."""
        self.listw.clear()
        try:
            names = self.project.get_experiment_list() or []
        except Exception:
            root = self.project_path
            names = []
            if root:
                for name in sorted(os.listdir(root)):
                    full = os.path.join(root, name)
                    if os.path.isdir(full) and not name.startswith("."):
                        names.append(name)
        for n in names:
            self.listw.addItem(n)

    def _accept_open(self):
        item = self.listw.currentItem()
        if not item:
            QMessageBox.warning(self, "Select", "Please select an experiment.")
            return
        self.experiment_name = item.text()
        self.accept()

    def _accept_new(self):
        name = (self.name_edit.text() or "").strip()
        if not name:
            QMessageBox.warning(self, "Invalid name", "Name cannot be empty.")
            return
        if not SAFE_NAME.match(name):
            QMessageBox.warning(self, "Invalid name",
                                "Only letters, numbers, '_' and '-' are allowed.")
            return

        existing = set(self.project.get_experiment_list() or [])
        if name in existing:
            QMessageBox.warning(self, "Already exists",
                                f"Experiment '{name}' already exists.")
            return

        # 1) Collect camera setup 
        camera_setup = self.cam_panel.get_camera_setup()
        if not camera_setup or len(camera_setup) < 2:
            QMessageBox.warning(
                self,
                "Not enough cameras",
                "Please select at least two cameras to perform 3D modeling."
            )
            return
        
        
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink):

            # -- Write status.json first, then create directory --
            sm = StatusManager()
            # Backup old status for rollback on failure
            old_status = json.loads(json.dumps(sm.status_data))  # Deep copy

            try:
                # 2) Update status.json
                sm.remove_all_used_config()  # Already saved internally
                for cam in camera_setup:
                    ip = cam.get("ip", "")
                    cfg_name = cam.get("config_name") or "Default"
                    sm.add_used_config(ip, cfg_name)  

                sm.status_data.setdefault('current_project', {})['path'] = self.project.project_path
                sm.status_data.setdefault('current_experiment', {})['name'] = name
                sm.status_data['current_experiment_name'] = name  
                sm._save_config(sm.status_data, sm.json_path)   

                # 3) Create experiment directory structure (failure goes to except -> rollback)
                self.project.add_experiment(name)

            except Exception as e:
                # Roll back status.json
                try:
                    sm._save_config(old_status, sm.json_path)
                except Exception:
                    pass
                QMessageBox.critical(
                    self, "Create experiment failed",
                    f"Failed to create experiment folder or files.\n"
                    f"The status.json has been restored.\n\nError: {e}"
                )
                return

        # Success: return new experiment name
        self.experiment_name = name
        self.accept()



    def _on_ok(self):
        if self.tabs.currentWidget() is self.tab_open:
            self._accept_open()
        else:
            self._accept_new()
