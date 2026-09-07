from PyQt5.QtWidgets import QDialog, QFileDialog,QPushButton , QLabel, QLineEdit, QGridLayout, QApplication, QMessageBox, QSpacerItem, QSizePolicy
from PyQt5.QtCore import Qt
from config import Config_Manager, Project
import os
from widgets.ProjectContext import ProjectContext

class NewProject(QDialog):
    """This class is a dialog window that allows the user to create a new project"""
    def __init__(self, parent=None, ctx: ProjectContext=None):
        super(NewProject, self).__init__(parent)
        self.ctx = ctx
        #Window settings
        self.setWindowTitle("New Project")
        self.setFixedSize(300, 150)

        self.status_config = Config_Manager.ConfigManager() # Instance de ConfigManager, check config/recent_manager.py
        last_settings = self.status_config.get_last_project_settings()
        #Window layout
        self.main_layout = QGridLayout()
        self.setLayout(self.main_layout)

        #Project name
        self.project_name_label = QLabel("Project name")
        self.main_layout.addWidget(self.project_name_label, 0, 0, 1, 1)
        self.project_name = QLineEdit()
        self.main_layout.addWidget(self.project_name, 0, 1, 1, 2)

        #Project directory
        self.project_directory_label = QLabel("Project dir")
        self.main_layout.addWidget(self.project_directory_label, 1, 0, 1, 1)
        self.project_directory = QLineEdit()

        # default from context if available
        self.project_directory.setText(last_settings.get("path", ""))
        self.main_layout.addWidget(self.project_directory, 1, 1, 1, 1)
        self.project_directory_button = QPushButton("Browse")
        self.main_layout.addWidget(self.project_directory_button, 1, 2, 1, 1)

        #experimenter name
        self.experimenter_name_label = QLabel("Experimenter name")
        self.main_layout.addWidget(self.experimenter_name_label, 2, 0, 1, 1)
        self.experimenter_name = QLineEdit()
        self.experimenter_name.setText(last_settings.get("experimenter", ""))
        self.main_layout.addWidget(self.experimenter_name, 2, 1, 1, 2)

        #Spacer
        self.spacer_item = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.main_layout.addItem(self.spacer_item, 3, 0, 1, 3)  # Ajoute un espace dans la position (0, 1)


        #Validation buttons
        self.create_button = QPushButton("Create")
        self.main_layout.addWidget(self.create_button,4, 0, 1, 2)
        self.cancel_button = QPushButton("Cancel")
        self.main_layout.addWidget(self.cancel_button, 4, 2, 1, 1)
        self.create_button.setDefault(True)

        #Bindings
        self.project_directory_button.clicked.connect(self.browse)
        self.create_button.clicked.connect(self.create)
        self.cancel_button.clicked.connect(self.cancel)

        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    def browse(self):
        directory = QFileDialog.getExistingDirectory(self, "Select directory")
        self.project_directory.setText(directory)

    def create(self):
        project_name = self.project_name.text()
        project_directory = self.project_directory.text()
        experimenter_name = self.experimenter_name.text()
        project_path = os.path.join(project_directory, project_name)

        if project_name != "" and project_directory != "" and experimenter_name != "":
            try:
                Project.create_project(os.path.join(project_directory, project_name))
                if self.ctx:
                    self.ctx.set_project(project_path)
                parent = self.parent()
                if parent and hasattr(parent, "open_project"):
                    parent.open_project(project_path)
                self.close()
            except FileExistsError: #catch the exception if the project already exists
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Warning)
                msg.setText("Project already exists")
                msg.setInformativeText("Do you want to replace it ?")
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg.setDefaultButton(QMessageBox.No)
                reply = msg.exec_()
                if reply == QMessageBox.Yes:
                    Project.replace_project(os.path.join(project_directory, project_name), experimenter_name)
                    self.status_config.set_last_project_settings(project_directory, experimenter_name)
                    self.parent().open_project(os.path.join(project_directory, project_name))
                    self.close()
            except Exception as e: #catch all exceptions
                QMessageBox.critical(self, "Oups !", "An error occured while creating the project")

        else :
            QMessageBox.warning(self, "Warning", "Please fill all fields")

        
    def cancel(self):
        self.close()


if __name__ == "__main__":
    app = QApplication([])
    window = NewProject()
    window.show()
    app.exec_()