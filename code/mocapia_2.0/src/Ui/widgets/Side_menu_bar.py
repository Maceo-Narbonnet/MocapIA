from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal, QSize
import os
import sys
from typing import Optional

class SideMenuBar(QWidget):
    """Side menu bar with buttons to access file explorer, capture manager,
    experiment home and analysis pages."""

    # Signals
    camera_state_signal = pyqtSignal()         # Manage Capture
    analysis_state_signal = pyqtSignal()
    experiment_home_signal = pyqtSignal()
    window_parameters = pyqtSignal()
    show_files = pyqtSignal()

    def __init__(self, parent=None):
        super(SideMenuBar, self).__init__(parent)

        # ---- layout ----
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.layout.setSpacing(8)
        self.setFixedWidth(55)

        # ---- stylesheet (one source of truth) ----
        self.stylesheet_all = """
        QPushButton {
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            color: #cbd5e1;
            padding: 6px;
        }
        QPushButton:hover {
            background: rgba(255,255,255,0.09);
        }
        QPushButton:checked {
            /* Persistent highlight when selected */
            background: rgba(90,175,255,0.22);
            border: 1px solid rgba(90,175,255,0.55);
            color: #E6F2FF;
        }
        QPushButton:disabled {
            opacity: 0.45;
        }
        """

        # ---- assets dir ----
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        assets_dir = os.path.normpath(assets_dir)  # Normalize path to avoid ".." segments

        def icon(name):
            return QIcon(os.path.join(assets_dir, name))

        # ---- buttons ----
        self.button_file = QPushButton()
        self.button_camera = QPushButton()     # Manage Capture
        self.button_home = QPushButton()       # Experiment Home
        self.button_analysis = QPushButton()
        self.button_settings = QPushButton()   # Settings (not checkable)

        # checkable & styles
        for b in (self.button_file, self.button_camera, self.button_home, self.button_analysis):
            b.setCheckable(True)
            b.setStyleSheet(self.stylesheet_all)
            b.setFixedSize(42, 42)
            b.setIconSize(QSize(18, 18))

        # Settings button does not require a checked (selected) state
        self.button_settings.setCheckable(False)
        self.button_settings.setStyleSheet(self.stylesheet_all)
        self.button_settings.setFixedSize(42, 42)
        self.button_settings.setIconSize(QSize(18, 18))

        # icons & tooltips
        self.button_file.setIcon(icon("file.svg"))
        self.button_file.setToolTip("Files")

        self.button_camera.setIcon(icon("camera.svg"))
        self.button_camera.setToolTip("Manage Capture")

        self.button_home.setIcon(icon("workflow.svg"))  # Experiment home (workflow icon)
        self.button_home.setToolTip("Experiment Home")

        self.button_analysis.setIcon(icon("activity.svg"))
        self.button_analysis.setToolTip("Analysis")

        self.button_settings.setIcon(icon("settings.svg"))
        self.button_settings.setToolTip("Settings")

        # ---- layout order ----
        self.layout.addWidget(self.button_file)
        self.layout.addWidget(self.button_camera)
        self.layout.addWidget(self.button_home)
        self.layout.addWidget(self.button_analysis)
        self.layout.addStretch(1)
        self.layout.addWidget(self.button_settings)

        # ---- bindings ----
        self.button_file.clicked.connect(self.on_click_file)
        self.button_camera.clicked.connect(self.on_click_camera)
        self.button_home.clicked.connect(self.on_click_home)
        self.button_analysis.clicked.connect(self.on_click_analysis)
        self.button_settings.clicked.connect(self.on_click_settings)

        # Initial: none selected; enable/disable is controlled by MainWindow
        self._select(None)

    # ---------- Slots ----------
    def on_click_file(self):
        # Toggle highlight state; does not affect other buttons
        self.button_file.setChecked(not self.button_file.isChecked())
        self.show_files.emit()   # MainWindow will decide whether to show/hide the panel

    def set_file_open(self, opened: bool):
        """Allow MainWindow to update the highlight state after the file panel is opened/closed."""
        self.button_file.setChecked(bool(opened))

    def on_click_camera(self):
        self._select("camera")
        self.camera_state_signal.emit()

    def on_click_home(self):
        self._select("home")
        self.experiment_home_signal.emit()

    def on_click_analysis(self):
        self._select("analysis")
        self.analysis_state_signal.emit()

    def on_click_settings(self):
        self.window_parameters.emit()

    # ---------- Helpers ----------
    def _select(self, which: Optional[str] = None):
        """Use :checked state to highlight the selected button."""
        mapping = {
            "camera": self.button_camera,
            "home": self.button_home,
            "analysis": self.button_analysis,
        }
        # Clear all states
        for btn in mapping.values():
            btn.setChecked(False)
        # Set selected state
        if which in mapping:
            mapping[which].setChecked(True)

    def set_project_loaded(self, loaded: bool):
        """
        When no project is loaded: disable all buttons and clear highlight.
        When a project is loaded: enable all buttons and highlight the camera button by default.

        If you want “Files” to be clickable even without a project,
        change the first part to: self.button_file.setEnabled(True).
        """
        if not loaded:
            for b in (self.button_file, self.button_camera, self.button_home, self.button_analysis):
                b.setEnabled(False)
            self._select(None)
        else:
            for b in (self.button_file, self.button_camera, self.button_home, self.button_analysis):
                b.setEnabled(True)
            self._select("camera")

    def set_uniform_sizes(self):
        # Sizes already unified in __init__; kept for compatibility if MainWindow calls this
        pass


# --- Standalone preview ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = SideMenuBar()
    # preview: no project loaded → all disabled & unselected
    w.set_project_loaded(False)
    w.show()
    sys.exit(app.exec_())
