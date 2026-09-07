from PyQt5.QtWidgets import QPushButton, QLabel, QGridLayout, QWidget, QApplication, QMainWindow, QVBoxLayout, QFrame, QScrollArea, QMessageBox, QHBoxLayout
from PyQt5.QtGui import QIcon, QDrag
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData
from config import Config_Manager
from Ui.dialog.New_Camera import NewCamera
from Ui.dialog.Camera_Parameters import CameraParameters
import sys
from PyQt5.QtWidgets import QSizePolicy

class CameraConfigDisplay(QWidget):

    update_signal = pyqtSignal()
    # add_selected_config_signal = pyqtSignal(str)
    # remove_selected_config_signal = pyqtSignal(str)

    def __init__(self, ip, config_name:str):
        super(CameraConfigDisplay, self).__init__()

        #class attribut setup
        self.ip = ip
        self.config_name = config_name

        self.camera_manager = Config_Manager.CameraManager()
        self.config = self.camera_manager.get_configuration(self.ip, config_name)
        self.params = self.camera_manager.get_parameters_of_configuration(self.ip, config_name)

        #add QFrame
        self.frame = QFrame()
        self.frame.setFrameStyle(QFrame.Panel | QFrame.Raised)

        self.main_layout = QVBoxLayout()

        #Labels
        self.name_label = QLabel(f"<b>{config_name}<b>")
        self.params_label = QLabel(f"{self.params['resolution']} | {self.params['fps']} | {self.params['fov']}")
        self.other_params_label = QLabel(f"Other params : {self.params['other']}")

        # self.calibration_warning_label.setToolTip("Calibration needed")

        #button
        self.delete_button = QPushButton(QIcon(r"Ui\assets\trash_black.svg"), "")
        self.delete_button.setFixedSize(25, 25)
        self.delete_button.setStyleSheet("QPushButton{border: none;} QPushButton:checked{background-color: #f0f0f0;}")
        self.delete_button.setToolTip("Delete configuration")

        self.calibration_warning_label = QPushButton(QIcon(r"Ui\assets\alert-circle.svg"), "")
        self.calibration_warning_label.setFixedSize(25, 25)
        self.calibration_warning_label.setStyleSheet("QPushButton{border: none;} QPushButton:checked{background-color: #f0f0f0;}")
        self.calibration_warning_label.setToolTip("Calibration needed")


        if self.params['favorite'] == True:
            self.favorite_button = QPushButton(QIcon(r"Ui\assets\star_yellow.svg"), "")
            self.favorite_button.setCheckable(True)
            self.favorite_button.setChecked(True)
        else:
            self.favorite_button = QPushButton(QIcon(r"Ui\assets\star.svg"), "")
            self.favorite_button.setCheckable(True)
            self.favorite_button.setChecked(False)
        self.favorite_button.setFixedSize(25, 25)
        self.favorite_button.setStyleSheet("QPushButton{border: none;} QPushButton:checked{background-color: #f0f0f0;}")
        self.favorite_button.setToolTip("Favorite configuration")

        #create and add to layout
        self.frame_layout = QGridLayout()
        self.frame_layout.addWidget(self.name_label, 0, 0)
        self.frame_layout.addWidget(self.params_label, 1, 0)
        self.frame_layout.addWidget(self.other_params_label, 2, 0)
        self.frame_layout.addWidget(self.favorite_button, 1, 1)
        self.frame_layout.addWidget(self.delete_button, 2, 1)

        if len(self.config["intrinsic_calib"]) == 0:
            self.frame_layout.addWidget(self.calibration_warning_label, 0, 1)

        #bindings
        self.delete_button.clicked.connect(self.on_delete_clicked)
        self.favorite_button.clicked.connect(self.on_favorite_clicked)

        #set_layout of the frame
        self.frame.setLayout(self.frame_layout)
        self.main_layout.addWidget(self.frame)
        self.setLayout(self.main_layout)


    def on_delete_clicked(self):
        """Delete the configuration from the config file and delete the widget"""
        self.camera_manager.delete_configuration_from_one_camera(self.ip, self.config_name) #delete the configuration from the config file
        self.update_signal.emit() #update the display of all configs of the camera in the CameraWidget
        self.deleteLater() #delete the widget


    def on_favorite_clicked(self):
        if self.favorite_button.isChecked():
            self.favorite_button.setIcon(QIcon(r"Ui\assets\star_yellow.svg"))
            self.camera_manager.set_favorite(self.ip, self.config_name, True) #change the favorite status in the config file
            self.update_signal.emit() #update the display of all configs of the camera in the CameraWidget
        else:
            self.favorite_button.setIcon(QIcon(r"Ui\assets\star.svg"))
            self.camera_manager.set_favorite(self.ip, self.config_name, False) #change the favorite status in the config file
            self.update_signal.emit() #update the display of all configs of the camera in the CameraWidget


class CameraWidget(QWidget):
    update_camera_list_signal = pyqtSignal()

    def __init__(self, ip):
        super(CameraWidget, self).__init__()


        self.camera_ip = ip
        self.camera_manager = Config_Manager.CameraManager()
        self.camera_name = self.camera_manager.get_camera_name(self.camera_ip)
        self.configs = self.camera_manager.get_configurations(self.camera_ip)
        self.setFixedWidth(300)

        #layouts
        self.main_layout = QVBoxLayout()
        self.cam_info_layout = QHBoxLayout() #contains the camera name and ip labels and different buttons and finaly the configs layout
        self.configs_layout = QVBoxLayout()#contains the configs widgets

        #QLabels
        self.camera_name_label = QLabel(f"<b>{self.camera_name}<b>")
        self.camera_ip_label = QLabel(f"IP : {self.camera_ip}")

        #buttons
        self.show_configs_button = QPushButton(QIcon(r"Ui\assets\chevron-right.svg"), "")
        self.show_configs_button.setCheckable(True)
        self.show_configs_button.setStyleSheet("QPushButton{border: none;}")
        self.delete_camera_button = QPushButton(QIcon(r"Ui\assets\trash_black.svg"), "")
        self.delete_camera_button.setStyleSheet("QPushButton{border: none;}")
        self.add_configuration_button = QPushButton(QIcon(r"Ui\assets\plus.svg"), "")
        self.add_configuration_button.setStyleSheet("QPushButton{border: none;}")
        self.add_configuration_button.setToolTip("Add a configuration")

        #add to main layout
        # self.main_layout.addLayout(self.configs_layout, 1,2, 1, 49)
        # self.main_layout.addWidget(self.show_configs_button, 0, 0, 1, 1)
        # self.main_layout.addWidget(self.camera_name_label, 0, 1, 1, 1)
        # self.main_layout.addWidget(self.camera_ip_label, 0, 2, 1, 1)

        # self.main_layout.addWidget(self.delete_camera_button, 0, 48, 1, 1)
        # self.main_layout.addWidget(self.add_configuration_button, 0, 49, 1, 1)

        self.cam_info_layout.addWidget(self.show_configs_button)
        self.cam_info_layout.addWidget(self.camera_name_label)
        self.cam_info_layout.addWidget(self.camera_ip_label)
        self.cam_info_layout.addStretch()
        self.cam_info_layout.addWidget(self.delete_camera_button)
        self.cam_info_layout.addWidget(self.add_configuration_button)

        self.main_layout.addLayout(self.cam_info_layout)
        self.main_layout.addLayout(self.configs_layout)

        #bindings
        self.show_configs_button.clicked.connect(self.on_show_configs_clicked)
        self.delete_camera_button.clicked.connect(self.on_delete_camera_clicked)
        self.add_configuration_button.clicked.connect(self.on_add_configuration_clicked)

        #set the layout
        self.setLayout(self.main_layout)


    def on_add_configuration_clicked(self) -> None:
        """Open the CameraParameters dialog"""
        CameraParameters(self.camera_ip).exec_()
        self.update_camera_list_signal.emit()


    def on_show_configs_clicked(self) -> None:
        if self.show_configs_button.isChecked(): #show the configs and change the icon to chevron-down
            self.show_configs_button.setIcon(QIcon(r"Ui\assets\chevron-down.svg"))
            self.add_configs_widgets()


        else : #hide the configs and change the icon to chevron-right
            self.show_configs_button.setIcon(QIcon(r"Ui\assets\chevron-right.svg"))
            self.suppress_all_configs_widgets()

    def on_delete_camera_clicked(self) -> None:
        """Delete the camera from the config file and delete the widget
        Ask for confirmation before deleting"""
        confirmation = QMessageBox.question(self, "Delete camera", f"Do you really want to delete the camera : <b>{self.camera_name}</b> ?<br>This action will also delete all configurations of the camera.", QMessageBox.Yes | QMessageBox.No)
        if confirmation == QMessageBox.Yes:
            self.camera_manager.delete_camera(self.camera_ip)
            self.update_camera_list_signal.emit()
            self.deleteLater()

    def suppress_all_configs_widgets(self) -> None:
        """Suppress all the configs widgets from the configs_layout"""
        self.camera_manager = Config_Manager.CameraManager() #update the camera manager in case of changes
        self.configs = self.camera_manager.get_configurations(self.camera_ip) #update the configs list in case of changes
        while self.configs_layout.count():
            child = self.configs_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def add_configs_widgets(self) -> None:
        """Add the configs widgets to the configs_layout"""

        self.camera_manager = Config_Manager.CameraManager() #update the camera manager in case of changes
        self.configs = self.camera_manager.get_configurations(self.camera_ip) #update the configs list in case of changes
        for config in self.configs:
            config_widget = CameraConfigDisplay(self.camera_ip, config["name"])
            self.configs_layout.addWidget(config_widget)
            config_widget.update_signal.connect(self.update_configs_display) #connect the update signal of the config widget to the update display function

    def update_configs_display(self):
        """Update the configs display"""
        self.suppress_all_configs_widgets()
        self.add_configs_widgets()

    def get_favorite_config_name(self):
        """Return the name of the favorite config"""
        for config in self.configs:
            print(config)
            if config["parameters"]["favorite"]:
                return config["name"]
        return None

# Permet d'initialiser l'opération de drag
    def mouseMoveEvent(self, event):
        """Start the drag operation"""
        if event.buttons() == Qt.LeftButton:
            mime_data = QMimeData()
            mime_data.setText(f"{self.camera_ip},{self.get_favorite_config_name()}") #add informations to communicate with the drop event

            drag = QDrag(self)
            drag.setMimeData(mime_data)
            # mime_data.setText(self.config_name)
            drag.setHotSpot(event.pos())
            drag.exec_(Qt.MoveAction)



class CameraList(QWidget):
    def __init__(self) -> None:
        super(CameraList, self).__init__()

        #class attribut setup
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        #widget structure
        self.main_layout = QVBoxLayout()

        #scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)

        #buttons
        self.add_camera_button = QPushButton(QIcon(r"Ui\assets\plus.svg"), "")
        self.add_camera_button.setFixedSize(25, 25)
        self.add_camera_button.setStyleSheet("QPushButton{border: none;} QPushButton:checked{background-color: #f0f0f0;}")
        self.add_camera_button.setToolTip("Add a camera")

        #Add all cameras to the layout
        self.add_cameras_to_display()

        self.content_widget.setLayout(self.content_layout)
        self.scroll_area.setWidget(self.content_widget)

        #add to main layout
        self.main_layout.addWidget(self.add_camera_button)
        self.main_layout.addWidget(self.scroll_area)
        self.setLayout(self.main_layout)

        #bindings
        self.add_camera_button.clicked.connect(self.on_add_camera_clicked)


    def on_add_camera_clicked(self) -> None:
        """Open the NewCamera dialog"""
        NewCamera().exec_()
        self.camera_manager = Config_Manager.CameraManager()
        self.update_cameras_list()

    def add_cameras_to_display(self):
        """Add a camera widget to the layout"""
        self.camera_manager = Config_Manager.CameraManager()
        for camera in self.camera_manager.camera_data:
            camera_widget = CameraWidget(camera["ip"])
            camera_widget.update_camera_list_signal.connect(self.update_cameras_list)
            self.content_layout.layout().addWidget(camera_widget)
        self.content_layout.addStretch()


    def delete_all_cameras_widgets(self):
        """Delete all the camera widgets from the layout content_layout"""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()


    def update_cameras_list(self):
        """Update the cameras display"""
        self.delete_all_cameras_widgets()
        self.add_cameras_to_display()



if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Créer une fenêtre principale
    main_window = QMainWindow()
    camera_list = CameraList()
    # Définir le widget central dans la fenêtre principale
    main_window.setCentralWidget(camera_list)

    # Afficher la fenêtre principale
    main_window.show()

    # Exécuter la boucle de l'application
    sys.exit(app.exec_())
    app.exec_()