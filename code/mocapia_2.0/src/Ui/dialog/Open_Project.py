import os
from PyQt5.QtWidgets import QDialog, QGridLayout, QPushButton, QLabel, QFileDialog, QLineEdit
from config import Config_Manager
from PyQt5.QtCore import pyqtSignal

class ProjectOpenDialog(QDialog):
    """Dialogue pour ouvrir un projet existant."""
    projectSelected = pyqtSignal(str)

    def __init__(self, parent=None):
        super(ProjectOpenDialog, self).__init__(parent)
        self.setWindowTitle("Ouvrir un projet")
        self.setFixedSize(300, 100)
        self.project_manager = Config_Manager.ConfigManager()
        self.parent = parent


        # Créer le layout
        layout = QGridLayout()

        # Ajouter un bouton pour ouvrir le dossier
        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(self.open_project_folder)
        layout.addWidget(self.open_button, 1, 0, 1, 2)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button, 1, 2, 1, 1)

        # Ajouter un label pour afficher le chemin du dossier sélectionné
        self.label = QLabel("Project directory")
        layout.addWidget(self.label, 0, 0, 1, 1)

        #QLineEdit
        self.line_edit_project_dir = QLineEdit()
        layout.addWidget(self.line_edit_project_dir, 0, 1, 1, 2)

        self.setLayout(layout)



    def open_project_folder(self):
        # Ouvrir un dialogue pour sélectionner un dossier
        last_settings = self.project_manager.get_last_project_settings()
        last_path = last_settings.get("path","")
        start_dir = last_path if os.path.isdir(last_path) else os.path.expanduser("~")
        
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier projet", start_dir)
        if folder:
            self.line_edit_project_dir.setText(folder)
            self.projectSelected.emit(folder)
            self.accept()


# Exemple d'utilisation
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    dialog = ProjectOpenDialog()
    dialog.exec_()