from PyQt5.QtWidgets import QMessageBox, QApplication, QMainWindow, QHBoxLayout, QWidget, QVBoxLayout
from Ui.dialog import New_Project, Open_Project, Ask_Save

from config import Config_Manager
from config import Project
from config.Config_Manager import StatusManager

from Ui.widgets.Side_menu_bar import SideMenuBar
from Ui.widgets.FileExplorer import FileExplorer

import qdarkstyle
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from PyQt5.QtWidgets import QMainWindow, QStackedWidget
from Ui.widgets.ProjectContext import ProjectContext
from Ui.dialog.Experiment_Picker import ExperimentPickerDialog

from Ui.pages.CaptureManagerPage import CaptureManagerPage
from Ui.pages.ExperimentHomePage import ExperimentHomePage
from Ui.pages.AnalysisPage import AnalysisPage

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.ctx = ProjectContext()
        #States Manager
        self.project_path = None
        # self.project_class = None
        self.experiment_name = None
        self.file_explorer_visible = False

        # Window settings
        self.setWindowTitle("MoCapIA Main Window")
        self.setGeometry(QApplication.desktop().screenGeometry())
        self.status_manager = Config_Manager.ConfigManager()
 
        # Menu bar
        self.menu_bar = self.menuBar()
        self.menu_file = self.menu_bar.addMenu("File")
        self.menu_edit = self.menu_bar.addMenu("Edit")
        self.menu_settings = self.menu_bar.addMenu("Settings")
        self.menu_help = self.menu_bar.addMenu("Help")

        # Submenu file
        self.submenu_file_new = self.menu_file.addAction("New Project")
        self.submenu_file_open = self.menu_file.addAction("Open Project")
        self.submenu_file_save = self.menu_file.addAction("Save Project")
        self.submenu_file_exit = self.menu_file.addAction("Exit")

        # Submenu edit
        self.submenu_edit_undo = self.menu_edit.addAction("Undo")
        self.submenu_edit_redo = self.menu_edit.addAction("Redo")

        # Submenu settings
        self.submenu_settings_display = self.menu_settings.addAction("Display")
        self.submenu_settings_language = self.menu_settings.addAction("Language")
        self.submenu_settings_preferences = self.menu_settings.addAction("Preferences")

        # Submenu help
        self.submenu_help_documentation = self.menu_help.addMenu("Documentation")
        self.submenu_help_about = self.menu_help.addMenu("About")

        # Subsubmenu help
        self.subsubmenu_help_about_author = self.submenu_help_about.addAction("Author")
        self.subsubmenu_help_about_version = self.submenu_help_about.addAction("Version")
        self.subsubmenu_help_about_yolommpose = self.submenu_help_about.addAction("What is YoloMMPose ?")

        self.subsubmenu_help_documentation_calibration = self.submenu_help_documentation.addAction("Help for calibration")
        self.subsubmenu_help_documentation_data = self.submenu_help_documentation.addAction("Yolommpose documentation")
        self.subsubmenu_help_documentation_analysis = self.submenu_help_documentation.addAction("Analysis documentation")

        #Menu bar bindings
        self.submenu_file_exit.triggered.connect(lambda : self.close_window())
        self.submenu_file_new.triggered.connect(lambda: New_Project.NewProject(self).exec_())
        self.submenu_file_open.triggered.connect(self.on_open_project)
        self.submenu_file_save.triggered.connect(lambda: Ask_Save.AskSave(self).exec_())

        #window main layout
        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # Side_Menu_Bar 
        self.side_menu_bar = SideMenuBar(self)

        #Add to main layout
        self.main_layout.addWidget(self.side_menu_bar)
        self.side_menu_bar.show()
        self.main_layout.update()

        # Widget central
        self.central_widget = QWidget(self)
        self.central_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.central_widget)  # Définir le widget central

        #signal bindings
        self.side_menu_bar.camera_state_signal.connect(self.set_state_capture_manager)
        self.side_menu_bar.experiment_home_signal.connect(self.set_state_experiment_home)
        self.side_menu_bar.analysis_state_signal.connect(self.set_state_analysis)
        self.side_menu_bar.show_files.connect(self.handle_file_explorer)

        # self.side_menu_bar.window_parameters.connect(self.set_state_parameters)
        self.side_menu_bar.set_uniform_sizes()         
        self.side_menu_bar.set_project_loaded(False)   # Default state = No project opened
        #state widget
        self.state_widget = QWidget(self)
        self.state_widget.setLayout(QHBoxLayout())
        self.main_layout.addWidget(self.state_widget)
        
        # ---- Central container: left side shows the file list; right side shows the stack ----
        self.center_container = QWidget(self)
        self.center_hbox = QHBoxLayout(self.center_container)
        self.center_hbox.setContentsMargins(0,0,0,0)
        self.center_hbox.setSpacing(0)

        # Left column: container for the file panel (implemented as an empty QWidget embedding the FileExplorer)
        self.file_area = QWidget(self.center_container)
        self.file_area.setLayout(QVBoxLayout())
        self.file_area.layout().setContentsMargins(0,0,0,0)
        self.file_area.setVisible(False)              
        self.file_explorer_visible = False

        # Right column: page stack
        self.stack = QStackedWidget(self.center_container)

        self.center_hbox.addWidget(self.file_area, 0) 
        self.center_hbox.addWidget(self.stack, 1)

        # Insert the container into the existing main_layout
        self.main_layout.addWidget(self.center_container, 1)
      
    def on_open_project(self):
        dlg = Open_Project.ProjectOpenDialog(self)
        dlg.projectSelected.connect(self.open_project)
        if self.file_explorer_visible:
            self.hide_file_explorer()
        dlg.exec_()
        

    def open_project(self, project_path: str):
        self.project_path = project_path
        print(project_path)

        # Create new dialog
        dlg = ExperimentPickerDialog(self.project_path, parent=self)
        if not dlg.exec_():
            return  # User canceled
        self.experiment_name = dlg.experiment_name

        if hasattr(self, "ctx"):
            self.ctx.set_project(self.project_path)
            self.ctx.set_experiment(self.experiment_name)
        # Update status.json
        cfg_path = os.path.join(self.project_path, self.experiment_name, "config.json")
        StatusManager().update_current(self.project_path, self.experiment_name, cfg_path)
        # Refresh the camera page display
        if hasattr(self, "_pages") and "camera" in self._pages:
            page = self._pages["camera"]  # CaptureManagerPage
            if hasattr(page, "info") and page.info:
                page.info.refresh_labels()     # Project/Experiment labels
            if hasattr(page, "refresh_status_box"):
                page.refresh_status_box()      # refresh “Current settings”
        # At this point, ctx already has experiment, then continue to enable the UI
        self.show_file_explorer()
        self.set_state_capture_manager()
        self.side_menu_bar.set_project_loaded(True)


    def close_window(self):
        if self.status_manager.get_project_path_saved():
            self.close()
        else:
            Ask_Save.AskSave(self).exec_() # Ask the user if he wants to save the project before closing the window
            self.close()

        
        
    def _ensure_page(self, key: str):
        if not hasattr(self, "_pages"):
            self._pages = {}

        if key in self._pages:
            return self._pages[key]

        # —— Create and add to the stack —— #
        if key == "camera":
            w = CaptureManagerPage(ctx=self.ctx, parent=self.stack)   
        elif key == "home":
            w = ExperimentHomePage(ctx=self.ctx, parent=self.stack) 
        elif key == "analysis":
            w = AnalysisPage(ctx=self.ctx, parent=self.stack)
        else:
            return None

        self.stack.addWidget(w)
        self._pages[key] = w
        return w

        
    def _switch_to(self, key: str):
        if getattr(self, "project_path", None) is None:
            return
        neww = self._ensure_page(key)
        if not neww: return
        oldw = self.stack.currentWidget()
        if oldw and hasattr(oldw, "on_leave"):
            oldw.on_leave()
        self.stack.setCurrentWidget(neww)
        if hasattr(neww, "on_enter"):
            neww.on_enter()

        # Sidebar selection
        if hasattr(self.side_menu_bar, "_select"):
            self.side_menu_bar._select({"camera":"camera","home":"home","analysis":"analysis"}.get(key))

    def set_state_capture_manager(self):
        self._switch_to("camera")

    def set_state_experiment_home(self):
        self._switch_to("home")

    def set_state_analysis(self):
        self._switch_to("analysis")



    def show_file_explorer(self):
        if getattr(self, "project_path", None) is None:
            return
        # Avoid duplicate creation
        if getattr(self, "file_explorer_visible", False):
            self.file_area.setVisible(True)
            if hasattr(self.side_menu_bar, "set_file_open"):
                self.side_menu_bar.set_file_open(True)
            return

        self.file_explorer = FileExplorer(self.project_path)

        # Clear the left column and insert the FileExplorer
        lay = self.file_area.layout()
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w: w.deleteLater()
        lay.addWidget(self.file_explorer)

        self.file_area.setVisible(True)
        self.file_explorer_visible = True
        if hasattr(self.side_menu_bar, "set_file_open"):
            self.side_menu_bar.set_file_open(True)

    def hide_file_explorer(self):
        self.file_area.setVisible(False)
        self.file_explorer_visible = False
        if hasattr(self.side_menu_bar, "set_file_open"):
            self.side_menu_bar.set_file_open(False)

    def handle_file_explorer(self):
        if getattr(self, "project_path", None) is None:
            return
        if not getattr(self, "file_explorer_visible", False) or not self.file_area.isVisible():
            self.show_file_explorer()
        else:
            self.hide_file_explorer()



if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet())

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())