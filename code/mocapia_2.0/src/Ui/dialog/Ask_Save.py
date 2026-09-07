"""create a dialog to ask if the user wants to save the current file"""
import os
from PyQt5.QtWidgets import QDialog, QGridLayout, QPushButton, QLabel, QMessageBox, QFileDialog, QLineEdit
from config import Config_Manager

class AskSave(QDialog):
    """Dialog to ask if the user wants to save the current file before closing the application."""
    def __init__(self, parent=None):
        super(AskSave, self).__init__(parent)
        self.setWindowTitle("Save")
        self.setFixedSize(200, 100)
        self.project_manager = Config_Manager.ConfigManager()

        # Create the layout
        layout = QGridLayout()

        # Add a button to save the file
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_file)
        layout.addWidget(self.save_button, 1, 0, 1, 1)

        self.dont_save_button = QPushButton("Don't save")
        self.dont_save_button.clicked.connect(self.dont_save)
        layout.addWidget(self.dont_save_button, 1, 2, 1, 1)

        # Add a label to ask if the user wants to save the file
        self.label = QLabel("Save the current file ?")
        layout.addWidget(self.label, 0, 0, 1, 4)

        self.setLayout(layout)

    def save_file(self):

        self.project_manager.set_current_project_saved(True) # Set the project as saved
        self.close()

    def dont_save(self):
        # Close the dialog without saving the file
        self.close()



# Example of use
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    dialog = AskSave()
    dialog.exec_()