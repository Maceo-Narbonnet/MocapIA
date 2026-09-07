import os
from PyQt5.QtWidgets import QDialog, QGridLayout, QPushButton, QLabel, QMessageBox, QFileDialog, QLineEdit, QCheckBox
from config import Config_Manager

class NewCamera(QDialog):
    """Dialog window to create new camera"""
    def __init__(self, parent=None):
        super(NewCamera, self).__init__(parent)
        self.setWindowTitle("New Camera")
        self.setFixedSize(200, 150)

        self.main_layout = QGridLayout()
        self.setLayout(self.main_layout)

        #Camera name
        self.camera_name_label = QLabel("Camera name")
        self.main_layout.addWidget(self.camera_name_label, 0, 0, 1, 1)
        self.camera_name = QLineEdit()
        self.main_layout.addWidget(self.camera_name, 0, 1, 1, 2)

        #Camera IP
        self.camera_ip_label = QLabel("Camera IP")
        self.main_layout.addWidget(self.camera_ip_label, 1, 0, 1, 1)
        self.camera_ip = QLineEdit()
        self.main_layout.addWidget(self.camera_ip, 1, 1, 1, 2)

        #Default configuration
        self.default_config_label = QLabel("Create default configuration")
        self.main_layout.addWidget(self.default_config_label, 2, 0, 1, 2)
        self.default_config_toggle = QCheckBox()
        self.main_layout.addWidget(self.default_config_toggle, 2, 2, 1, 1)
        self.default_config_toggle.setChecked(True)

        #Validation buttons
        self.create_button = QPushButton("Create")
        self.main_layout.addWidget(self.create_button, 3, 0, 1, 1)
        self.cancel_button = QPushButton("Cancel")
        self.main_layout.addWidget(self.cancel_button, 3, 1, 1, 2)

        #Bindings
        self.create_button.clicked.connect(self.create_camera)
        self.cancel_button.clicked.connect(self.close)


    def create_camera(self):
        """Binding of the create button, connected to CongigManager.add_camera, add the camera in camera_database.json"""
        name = self.camera_name.text()
        ip = self.camera_ip.text()

        if name == "" or ip == "":
            QMessageBox.warning(self, "Warning", "Please fill all the fields.")
            return
        else :
            camera_manager = Config_Manager.CameraManager()
            camera_created : bool = False
            if self.default_config_toggle.isChecked():
                camera_created = camera_manager.add_camera(name, ip, True)
            else:
                camera_created = camera_manager.add_camera(name, ip, False)

            if camera_created:
                self.close()
            else:
                QMessageBox.warning(self, "Warning", "Camera already exists.")
                return
            self.close()

# Example of use
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    dialog = NewCamera()
    dialog.exec_()



