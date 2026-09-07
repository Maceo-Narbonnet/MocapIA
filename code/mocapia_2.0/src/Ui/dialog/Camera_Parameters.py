import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QDialog, QPushButton, QHBoxLayout, QLineEdit, QMessageBox
from PyQt5.QtCore import Qt
from config.Config_Manager import CameraManager
from Camera.Camera_settings.Hero12 import COMPATIBLE_SETTINGS, AVAILABLE_RESOLUTIONS, AVAILABLE_FPS, AVAILABLE_FOV


# class SliderApp(QWidget):
#     """Display a slider with a list of items to select from.
#     The selected item is displayed in bold.
#     Args :
#         items (List[str]): List of items to select from.
#     """
#     def __init__(self, items: List[str]):
#         super().__init__()

#         self.items = items #List of items to select from

#         self.setWindowTitle('Sélection d\'éléments avec un slider')
#         self.setGeometry(100, 100, 400, 150)

#         layout = QGridLayout()

#         # Creation of labels
#         self.labels = []
#         for i, item in enumerate(self.items):
#             label = QLabel(item, self)
#             label.setStyleSheet("font-size: 12px;")
#             label.setAlignment(Qt.AlignCenter)  # Centrer les labels
#             layout.addWidget(label, 1, i+1)  # Placer dans la première ligne
#             self.labels.append(label)

#         # create the slider
#         self.slider = QSlider(Qt.Horizontal, self)
#         self.slider.setMinimum(0)  # Valeur minimale
#         self.slider.setMaximum(len(self.items) - 1)  # Valeur maximale
#         self.slider.setTickInterval(1)  # Incrément du slider
#         self.slider.setTickPosition(QSlider.TicksBelow)  # Position des ticks
#         self.slider.setSingleStep(1)  # Pas de mouvement

#         # Connexion du changement de valeur à une fonction
#         self.slider.valueChanged.connect(self.update_labels)

#         # Ajouter le slider au layout (deuxième ligne)
#         layout.addWidget(self.slider, 0, 1, 1, len(self.items))  # Placer dans la deuxième ligne, s'étendant sur toutes les colonnes

#         # Appliquer le layout à la fenêtre
#         self.setLayout(layout)

#         # Afficher les ticks initiaux
#         self.update_labels(0)

#     def update_labels(self, value):
#         # Mise à jour des labels pour afficher l'élément correspondant en gras
#         for i, label in enumerate(self.labels):
#             if i == value:
#                 label.setStyleSheet("font-size: 14px; font-weight: bold;")  # Gras pour le sélectionné
#             else:
#                 label.setStyleSheet("font-size: 12px;")  # Normal pour les autres

#     def get_selected_item(self):
#         """Return the currently selected item based on the slider position."""
#         return self.items[self.slider.value()]


# class CameraParameters(QDialog):
#     def __init__(self,cam_ip:str, parent: QWidget=None) -> None:
#         super().__init__(parent)
#         self.setWindowTitle("Camera Parameters")
#         self.camera_ip = cam_ip
#         self.main_layout = QGridLayout()

#         #Statics items
#         self.configuration_name_label = QLabel("Configuration name: ")
#         self.static_FPS_label = QLabel("FPS: ")
#         self.static_resolution_label = QLabel("Resolution: ")
#         self.static_FOV_label = QLabel("FOV: ")
#         self.more_button = QPushButton("More")
#         self.apply_button = QPushButton("Apply")
#         self.cancel_button = QPushButton("Cancel")

#         #Camera name
#         self.config_name_line_edit = QLineEdit()
#         self.config_name_line_edit.setText("New Config")

#         #Sliders items 
#         self.FPS_slider = SliderApp(["24","30", "60", "120", "240"])
#         self.resolution_slider = SliderApp(["720p", "1080p", "2.7K", "4K", "5.3K"])
#         self.FOV_slider = SliderApp(["Narrow", "Linear", "Wide", "SuperView", "Hyperview"])


#         #Add to layout
#         self.main_layout.addWidget(self.configuration_name_label, 0, 0)
#         self.main_layout.addWidget(self.config_name_line_edit, 0, 1)
#         self.main_layout.addWidget(self.static_FPS_label, 1, 0)
#         self.main_layout.addWidget(self.static_resolution_label, 2, 0)
#         self.main_layout.addWidget(self.static_FOV_label, 3, 0)
#         self.main_layout.addWidget(self.more_button, 4, 0)
#         self.main_layout.addWidget(self.apply_button, 5, 0)
#         self.main_layout.addWidget(self.cancel_button, 5, 1)

#         self.main_layout.addWidget(self.FPS_slider, 1, 1)
#         self.main_layout.addWidget(self.resolution_slider, 2, 1)
#         self.main_layout.addWidget(self.FOV_slider, 3, 1)

#         self.setLayout(self.main_layout)


#         #Bindings
#         self.cancel_button.clicked.connect(self.close)
#         self.more_button.clicked.connect(self.more_clicked)
#         self.apply_button.clicked.connect(self.apply_clicked)

#     def more_clicked(self):
#         print("More clicked")

#     def apply_clicked(self):
#         config_name = self.config_name_line_edit.text()
#         resolution = self.resolution_slider.get_selected_item()
#         fps = self.FPS_slider.get_selected_item()
#         fov = self.FOV_slider.get_selected_item()
#         if config_name == "":
#             QMessageBox.warning(self, "Warning", "Please fill all the fields.")
#             return
#         camera_manager = CameraManager()
#         camera_manager.add_configuration(self.camera_ip, config_name, resolution, fps, fov)
#         self.close()


class CameraParameters(QDialog):
    def __init__(self, cam_ip: str, default_config : dict = {'resolution': '1080p', 'fps': '30', 'fov': 'Linear'}, parent: QWidget = None) -> None:
        """Create a dialog to select camera parameters.
        Args:
            cam_ip (str): IP address of the camera.
            default_config (dict): Default configuration to display. Example {'resolution': '1080p', 'fps': '30', 'fov': 'Wide'}
            /!\ the default configuration must be compatible with the camera.
        """
        super().__init__(parent)
        self.setWindowTitle("New configuration")
        self.camera_ip = cam_ip
        self.default_config = default_config

        self.dico_resolution = {}
        self.dico_fps = {}
        self.dico_fov = {}

        self.main_layout = QVBoxLayout()
        self.config_name_layout = QHBoxLayout()
        self.resolution_layout = QHBoxLayout()
        self.FPS_layout = QHBoxLayout()
        self.FOV_layout = QHBoxLayout()


        #general items
        self.config_name_label = QLabel("Configuration name:")
        self.config_name_line_edit = QLineEdit()
        self.config_name_line_edit.setText("New Config")
        self.config_name_layout.addWidget(self.config_name_label)
        self.config_name_layout.addWidget(self.config_name_line_edit)

        self.resolution_label = QLabel("Resolution:")
        self.FPS_label = QLabel("Frame per second:")
        self.FOV_label = QLabel("Field of view:")
        self.apply_button = QPushButton("Apply")

        #resolutions buttons
        for resolution in AVAILABLE_RESOLUTIONS:
            self.dico_resolution[resolution] = QPushButton(resolution)
            self.dico_resolution[resolution].clicked.connect(self.resolution_clicked)
            self.resolution_layout.addWidget(self.dico_resolution[resolution])
            self.dico_resolution[resolution].setCheckable(True)
            if resolution == self.default_config['resolution']:
                self.dico_resolution[resolution].setChecked(True)
        print( self.default_config['resolution'])

        #fps buttons
        for fps in AVAILABLE_FPS:
            self.dico_fps[fps] = QPushButton(fps)
            self.dico_fps[fps].clicked.connect(self.fps_clicked)
            self.FPS_layout.addWidget(self.dico_fps[fps])
            self.dico_fps[fps].setCheckable(True)
            if fps == self.default_config['fps']:
                self.dico_fps[fps].setChecked(True)


        #fov buttons
        for fov in AVAILABLE_FOV:
            self.dico_fov[fov] = QPushButton(fov)
            self.dico_fov[fov].clicked.connect(self.fov_clicked)
            self.FOV_layout.addWidget(self.dico_fov[fov])
            self.dico_fov[fov].setCheckable(True)
            if fov == self.default_config['fov']:
                self.dico_fov[fov].setChecked(True)

        
        self.main_layout.addLayout(self.config_name_layout)
        self.main_layout.addWidget(self.resolution_label)
        self.main_layout.addLayout(self.resolution_layout)
        self.main_layout.addWidget(self.FPS_label)
        self.main_layout.addLayout(self.FPS_layout)
        self.main_layout.addWidget(self.FOV_label)
        self.main_layout.addLayout(self.FOV_layout)
        self.main_layout.addWidget(self.apply_button)

        self.setLayout(self.main_layout)

        self.check_fps_compatibility(self.default_config['resolution'])
        self.check_fov_compatibility(self.default_config['resolution'], self.default_config['fps'])

        self.apply_button.clicked.connect(self.on_apply_clicked)



    def on_apply_clicked(self):
        """Executed when the apply button is clicked"""
        config_name = self.config_name_line_edit.text()
        config = self.get_selected_config()
        if config_name == "":
            QMessageBox.warning(self, "Warning", "Please fill all the fields.")
            return
        camera_manager = CameraManager()
        camera_manager.add_configuration(self.camera_ip, config_name, config["resolution"], config["fps"], config["fov"])
        self.close()

    
    def resolution_clicked(self):
        """Exectuted when a resolution button is clicked, so resolution changed, 
        we need to update the fps and fov buttons"""
        button = self.sender()

        if not button.isChecked():
            button.setChecked(True)
            return
        else:
            for resolution in self.dico_resolution:
                if resolution == button.text(): #uncheck all the other buttons
                    button.setChecked(True)
                else:
                    self.dico_resolution[resolution].setChecked(False)
        
        self.check_fps_compatibility(button.text())
        self.check_fov_compatibility(button.text(), self.get_selected_config()["fps"])


    def fps_clicked(self):
        button = self.sender()
        if not button.isChecked():
            button.setChecked(True)
            return #do nothing if the button is already checked
        else :
            for fps in self.dico_fps: #uncheck all the other buttons
                if fps == button.text():
                    button.setChecked(True)
                else:
                    self.dico_fps[fps].setChecked(False)

        self.check_fov_compatibility(self.get_selected_config()["resolution"], button.text())
    
    def fov_clicked(self):
        button = self.sender()
        if not button.isChecked():
            button.setChecked(True)
            return
        else:
            for fov in self.dico_fov:
                if fov == button.text(): #uncheck all the other buttons
                    button.setChecked(True)
                else:
                    self.dico_fov[fov].setChecked(False)
    
    def check_fps_compatibility(self, resolution:str):
        """Check the compatibility of the selected resolution with the selected fps"""
        compatible_fps = COMPATIBLE_SETTINGS[resolution]
        first_compatible_button = None
        check_first_compatible_button = False
        for fps in self.dico_fps:
            if fps in compatible_fps:
                self.dico_fps[fps].setEnabled(True)
                first_compatible_button = self.dico_fps[fps]  # button to check if the current checked button have to be unchecked
            else:
                if self.dico_fps[fps].isChecked():
                    check_first_compatible_button = True
                self.dico_fps[fps].setEnabled(False)
                self.dico_fps[fps].setChecked(False)

        if first_compatible_button is not None and check_first_compatible_button:
            first_compatible_button.setChecked(True)

    def check_fov_compatibility(self, resolution:str, fps:str):
        """Check the compatibility of the selected resolution and fps with the selected fov"""
        compatible_fov = COMPATIBLE_SETTINGS[resolution][fps]
        first_compatible_button = None
        check_first_compatible_button = False
        for fov in self.dico_fov:
            if fov in compatible_fov:
                self.dico_fov[fov].setEnabled(True)
                first_compatible_button = self.dico_fov[fov]
            else:
                if self.dico_fov[fov].isChecked():
                    check_first_compatible_button = True
                self.dico_fov[fov].setEnabled(False)
                self.dico_fov[fov].setChecked(False)
        if first_compatible_button is not None and check_first_compatible_button:
            first_compatible_button.setChecked(True)
        

    def get_selected_config(self):
        """Return the selected configuration"""
        resolution, fps, fov = None, None, None
        for res in self.dico_resolution:
            if self.dico_resolution[res].isChecked():
                resolution = res; break
        for f in self.dico_fps:
            if self.dico_fps[f].isChecked():
                fps = f; break
        for f in self.dico_fov:
            if self.dico_fov[f].isChecked():
                fov = f; break
        return {"resolution": resolution, "fps": fps, "fov": fov}
    

    # def apply_clicked(self):
    # config_name = self.config_name_line_edit.text()
    # resolution = self.resolution_slider.get_selected_item()
    # fps = self.FPS_slider.get_selected_item()
    # fov = self.FOV_slider.get_selected_item()
    # if config_name == "":
    #     QMessageBox.warning(self, "Warning", "Please fill all the fields.")
    #     return
    # camera_manager = CameraManager()
    # camera_manager.add_configuration(self.camera_ip, config_name, resolution, fps, fov)
    # self.close()

    

        

 


if __name__ == "__main__":
    app = QApplication(sys.argv)  # Création de l'application Qt

    # Exécution de CameraParameters avec un exemple d'adresse IP de caméra
    cam_ip = "192.168.1.100"
    window = CameraParameters(cam_ip, {"resolution": "1080p", "fps": "30", "fov": "Wide"})
    window.show()

    sys.exit(app.exec_())  # Lancer la boucle d'événements Qt




