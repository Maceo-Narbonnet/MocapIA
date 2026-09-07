from PyQt5.QtWidgets import QWidget, QStackedWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QGridLayout, QFrame, QWidget, QMessageBox
from PyQt5.QtGui import QIcon, QPixmap, QImage, QMovie
from PyQt5.QtCore import Qt, QEvent, pyqtSignal, QThread, QSize
from config.Config_Manager import CameraManager
from config.Config_Manager import StatusManager
from typing import final
from enum import auto, Enum
import sys
import os
from typing import Tuple, List
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Ui.threads.WebcamThread import WebcamThread
from Camera.GoProCam import GoProCam
from Ui.widgets.Progress import ProgressWidget
from Ui.threads.CalibrationThread import IntrinsicCalibrationWorker
import time as t

class CameraErrorWidget(QWidget): 
    """This widget is added to the QStackedWidget when the camera has an error."""
    def __init__(self, error:str = "Error"):
        super().__init__()
        self.main_layout = QHBoxLayout()
        self.label_layout = QVBoxLayout()
        self.icon_label = QLabel()
        self.icon_label.setPixmap(QIcon(r"Ui\assets\alert-triangle.svg").pixmap(50, 50))
        self.label_oups = QLabel("<b>Oups !</b>")
        self.main_label = QLabel("The camera encountered an error.")
        self.error_label = QLabel(f"Error : {error}")

        self.main_layout.addWidget(self.icon_label)
        self.label_layout.addWidget(self.label_oups)
        self.label_layout.addWidget(self.main_label)
        self.label_layout.addWidget(self.error_label)

        self.main_layout.addLayout(self.label_layout)
        self.setLayout(self.main_layout)

    def set_error(self, error:str):
        self.error_label.setText(f"Error : {error}")


class CameraProgessWidget(QWidget):
    """This widget is added to the QStackedWidget when the camera is making a big task like calibration, capture or other."""
    def __init__(self, default_message:str = "Working..."):
        super().__init__()
        self.main_layout = QVBoxLayout()
        self.progress_widget = ProgressWidget(default_message)
        self.main_layout.addWidget(self.progress_widget)
        self.setLayout(self.main_layout)


class CameraLoadingWidget(QWidget):
    """Display a loading gif when the camera is connecting. Use during the change of differents states."""
    def __init__(self):
        super().__init__()
        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignCenter)
        self.movie = QMovie(r"Ui\assets\load_spinner.gif")
        self.movie.setScaledSize(QSize(70, 70))
        self.label = QLabel()
        self.label.setMovie(self.movie)
        # self.label.setFixedSize(100, 100)

        self.movie.start()
        self.main_layout.addWidget(self.label)
        self.setLayout(self.main_layout)

class CameraStream(QWidget):
    """Display the camera stream if the camera is connected, else displays a camera icon."""

    def __init__(self, size: Tuple[int, int], parent=None):
        super().__init__(parent)
        self.setFixedSize(size[0], size[1])
        self.setStyleSheet("background-color: #000000; padding: 0px; border-radius: 0px;")

        # Label for displaying the camera stream
        self.stream_label = QLabel(self)
        self.stream_label.setFixedSize(size[0], size[1])
        self.stream_label.setAlignment(Qt.AlignCenter)
        
        # Label to display a camera icon when there's no stream
        self.no_cam_label = QLabel(self)
        self.no_cam_label.setFixedSize(size[0], size[1])
        self.no_cam_label.setAlignment(Qt.AlignCenter)
        self.no_cam_label.setPixmap(QPixmap("path/to/camera_icon.png").scaled(
            size[0], size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation))  # Replace with actual path to camera icon
        
        # Layout to contain labels
        layout = QVBoxLayout()
        layout.addWidget(self.stream_label)
        layout.addWidget(self.no_cam_label)
        self.setLayout(layout)

        # Initially hide the stream label until the stream starts
        self.stream_label.hide()
        self.webcam_thread = None  # Thread to display the webcam stream

    def start_stream(self, camera_ip: str):
        """Start the stream of a GoPro camera and display it in the widget."""
        self.gopro = GoProCam(camera_ip)  # Remplacez par le numéro de série de la GoPro
        if self.gopro.connect():
            self.gopro.enable_wired_control()
            self.gopro.webcam_mode()
            print("GoPro connected and ready to use.")

            if self.gopro.start_webcam():
                print("Webcam started...")
                # Hide the camera icon and show the stream label
                self.no_cam_label.hide()
                self.stream_label.show()

                self.webcam_thread = WebcamThread(camera_ip)
                self.webcam_thread.frame_ready.connect(self.display_frame)
                self.webcam_thread.start()

    def display_frame(self, frame):
        """Display the frame on the widget."""
        # Convert the OpenCV frame (BGR) to QImage (RGB)
        height, width, _ = frame.shape
        bytes_per_line = 3 * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()

        # Update QLabel to display the frame
        self.stream_label.setPixmap(QPixmap.fromImage(q_img).scaled(
            self.stream_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def stop_stream(self):
        """Stop the stream of the camera."""
        if self.webcam_thread is not None:
            self.webcam_thread.stop()
            self.webcam_thread = None
        
        # Switch back to the "no camera" icon and hide the stream label
        self.stream_label.hide()
        self.no_cam_label.show()

        # Stop and reset GoPro settings
        self.gopro.stop_webcam()  # Stop the webcam mode
        self.gopro.enable_wired_control()  # Enable wired control to use the camera normally
        self.gopro.webcam_mode_exit()  # Exit the webcam mode


class CameraStackedWidget(QStackedWidget):
    """Stacked widget to display different widgets for the camera display (one class for each state).
    The states are :
    - CameraStream : Display the camera stream
    - CameraErrorWidget : Display an error message
    - CameraProgessWidget : Display a progress bar (used during calibrations and other exigent tasks)
    - CameraLoadingWidget : Display a loading gif
    """

    def __init__(self, size: Tuple[int, int], parent=None):
        super().__init__(parent)
        self.setFixedSize(size[0], size[1])
        print("Size of the stacked widget : ", size)

        # Widgets for different states
        self.no_cam_label = QLabel()
        self.no_cam_label.setPixmap(QIcon(r"Ui\assets\camera-off.svg").pixmap(50, 50))
        self.no_cam_label.setAlignment(Qt.AlignCenter)
        self.no_cam_label.setStyleSheet("background-color: #000000; padding: 0px; border-radius: 0px;")

        self.stream_widget = CameraStream(size)
        self.error_widget = CameraErrorWidget()
        self.progress_widget = CameraProgessWidget()
        self.loading_widget = CameraLoadingWidget()

        # Add widgets to stacked widget
        self.addWidget(self.no_cam_label)
        self.addWidget(self.stream_widget)
        self.addWidget(self.error_widget)
        self.addWidget(self.progress_widget)
        self.addWidget(self.loading_widget)

        self.setCurrentWidget(self.loading_widget)
        self.loading_widget.show()


    def set_error(self, error: str = "Error"):
        """Set the error message to display"""
        self.error_widget.set_error(error)
        self.setCurrentWidget(self.error_widget)
        self.update()

    def set_progress(self, message: str = "Working..."):
        """Set the progress message to display"""
        self.update()
        print("Setting progress message")
        self.progress_widget.progress_widget.set_message(message)
        self.setCurrentWidget(self.progress_widget)
        self.update()
        self.progress_widget.show()

    def start_stream(self, camera_ip: str):
        print("Starting stream")
        """Start the stream of a GoPro camera and display it in the widget"""
        self.set_progress("Connecting...")
        self.stream_widget.start_stream(camera_ip)
        self.setCurrentWidget(self.stream_widget)
        self.stream_widget.show()

    def stop_stream(self):
        print("Stopping stream")
        """Stop the stream of the camera"""
        self.stream_widget.stop_stream()
        self.setCurrentWidget(self.no_cam_label)
        self.no_cam_label.show()

    # def set_loading(self):
    #     """Set the loading gif"""
    #     self.setCurrentWidget(self.loading_widget)
    #     self.loading_widget.show()



class CameraDisplay(QWidget):
    """Display the camera preview and status if camera is connected else, displays a camera icon"""

    maximize_true_signal = pyqtSignal(str, str) #signal to maximize the camera display, the signal must contain the camera ip and the config name
    maximize_false_signal = pyqtSignal(str, str) #signal to minimize the camera display, the signal must contain the camera ip and the config name
    delete_signal = pyqtSignal(str, str) #signal to delete the camera display, the signal must contain the camera ip and the config name
    def __init__(self, cam_ip:str, config_name:str):
        super().__init__()

        #! ----------------- Camera Configuration ----------------- !#
        self.camera_manager = CameraManager()
        self.config_parameters = self.camera_manager.get_configuration(cam_ip, config_name)["parameters"]
        self.intrinsic_calib_data = self.camera_manager.get_configuration(cam_ip, config_name)["intrinsic_calib"]
        
        self.camera_ip: str = cam_ip
        self.config_name: str = config_name
        self.camera_name = self.camera_manager.get_camera_name(cam_ip)
        self.camera_fps = self.config_parameters["fps"]
        self.camera_resolution = self.config_parameters["resolution"]
        self.camera_fov = self.config_parameters["fov"]

        #! ----------------- Camera Status ----------------- !#

        class STATUS(Enum):
            CONNECTED = auto()
            # LOADING = auto()
            DISCONNECTED = auto()
            CONNECTION_ERROR = auto()
            CALIBRATED = auto()
            # CALIBRATING = auto()
            NOT_CALIBRATED = auto()
            CALIBRATION_ERROR = auto()

        self.STATUS = STATUS

        self.calibration_status_icons = {
            STATUS.CALIBRATED: r"Ui\assets\check.svg",
            STATUS.NOT_CALIBRATED: r"Ui\assets\alert-circle.svg",
            STATUS.CALIBRATION_ERROR: r"Ui\assets\alert_triangle.svg"
        }
        self.connection_status_icons = {
            STATUS.CONNECTED: r"Ui\assets\wifi_check.svg",
            STATUS.CONNECTION_ERROR: r"Ui\assets\wifi_error.svg",
            STATUS.DISCONNECTED: r"Ui\assets\wifi_disconnected.svg"
        }

        self.widget_connection_status : STATUS = STATUS.CONNECTED
        self.widget_calibration_status : STATUS = STATUS.NOT_CALIBRATED if self.intrinsic_calib_data["mtx"] == [] else STATUS.CALIBRATED

        #*battery status
        self.battery: bool = False
        self.camera_battery: int = 0
        self.battery_charging: bool = False

        #*Size of the widget
        self.maximized :bool = False
        self.mimimized :bool = False
        
        self.SIZE :final = (650, 366)
        self.SIZE_MAXI :final = (self.SIZE[0]*2, self.SIZE[1]*2)
        self.SIZE_MINI :final = ()
        self.BAR_SIZE :final = 40
        self.current_size = self.SIZE
        # self.setMinimumSize(self.current_size[0], self.current_size[1]+self.BAR_SIZE*2)
        # self.setMaximumSize(self.current_size[0], self.current_size[1]+self.BAR_SIZE*2)


        #! ----------------- Widgets ----------------- !#

        #labels 
        self.camera_name_and_config_label = QLabel(f"{self.camera_name} - {self.config_name}")
        self.battery_label = QLabel() #battery icon
        self.calibration_status_label = QLabel() #calibration status icon
        self.calibration_status_label.setToolTip("Calibration Status")
        self.connection_status_label = QLabel()
        self.connection_status_label.setToolTip("Connection Status")
        self.camera_name_and_config_label.setStyleSheet("background-color: #aaaaaa; padding: 5px; border-radius: 5px;")
        self.camera_name_and_config_label.setAlignment(Qt.AlignCenter)

        #buttons
        self.maximize_button = QPushButton(QIcon(r"Ui\assets\maximize.svg"), "")
        self.delete_button = QPushButton(QIcon(r"Ui\assets\x.svg"), "") 
        self.minimize_button = QPushButton(QIcon(r"Ui\assets\minimize.svg"), "") 
        self.calibration_button = QPushButton(QIcon(r"Ui\assets\chessboard.svg"), "") #calibration button
        self.camera_config_button = QPushButton(f"{self.camera_resolution} | {self.camera_fps} | {self.camera_fov}") #camera config button
        self.camera_config_button.setStyleSheet("background-color: #aaaaaa; padding: 5px; border-radius: 5px;")
        self.camera_config_button.setToolTip("Camera Configuration")
        self.calibration_button.setToolTip("Calibrate Camera")
        
        #add layout 
        self.layout = QVBoxLayout()
        self.main_frame = QFrame()
        self.main_frame.setStyleSheet("padding-top : 0px; padding-bottom:0px; padding-right:15px; padding-left:0px; border-radius: 5px; background-color: #000000;")
        self.main_frame.setFixedSize(self.SIZE[0], self.SIZE[1])

        #Top band
        self.top_band_container = QWidget()
        self.top_band_layout = QHBoxLayout()
        self.top_band_layout.addWidget(self.battery_label)
        self.top_band_layout.addStretch()
        self.top_band_layout.addWidget(self.camera_name_and_config_label)
        self.top_band_layout.addStretch()
        self.top_band_layout.addWidget(self.minimize_button)
        self.top_band_layout.addWidget(self.maximize_button)
        self.top_band_layout.addWidget(self.delete_button)
        self.top_band_container.setLayout(self.top_band_layout)
        self.top_band_container.setStyleSheet("background-color: rgba(0,0,0,0);")
        self.top_band_container.setFixedSize(self.SIZE[0], self.BAR_SIZE)

        #Middle Video Stream
        self.camera_stacked = CameraStackedWidget(self.SIZE)
        
        # self.camera_stacked.start_stream(self.camera_ip)

        #Bottom band
        self.bottom_band_container = QWidget()
        self.bottom_band_layout = QHBoxLayout()
        self.bottom_band_layout.addWidget(self.connection_status_label)
        self.bottom_band_layout.addWidget(self.calibration_status_label)
        self.bottom_band_layout.addStretch()
        self.bottom_band_layout.addWidget(self.camera_config_button)
        self.bottom_band_layout.addStretch()
        self.bottom_band_layout.addWidget(self.calibration_button)
        self.bottom_band_container.setLayout(self.bottom_band_layout)
        self.bottom_band_container.setStyleSheet("background-color: rgba(0,0,0,0);")
        self.bottom_band_container.setFixedSize(self.SIZE[0],self.BAR_SIZE)

        #add to a main layout
        # self.layout.addWidget(self.camera_stacked)
        self.frame_layout = QVBoxLayout()
        self.frame_layout.addWidget(self.top_band_container)
        self.frame_layout.addWidget(self.camera_stacked)
        self.frame_layout.addWidget(self.bottom_band_container)
        self.main_frame.setLayout(self.frame_layout)
        self.layout.addWidget(self.main_frame)
        self.setLayout(self.layout)

        self.update_camera_status()

        #! ----------------- Buttons bindings ----------------- !#
        self.delete_button.clicked.connect(self.on_delete_button_clicked)
        self.maximize_button.clicked.connect(self.on_maximize_button_clicked)
        self.calibration_button.clicked.connect(self.on_calibration_button_clicked)

        #! ----------------- Signal event ----------------- !#
        # self.update_all_camera_status.connect(self.update_camera_status)



    #! ----------------- Buttons Handler ----------------- !#

    def on_delete_button_clicked(self):
        #! add the function to delete from current used configs (to delete them)
        #* dont delete it from the camera database
        self.delete_signal.emit(self.camera_ip, self.config_name)
        self.camera_stacked.stop_stream()
        

    def on_maximize_button_clicked(self):
        if self.maximized == False :
            self.maximize_true_signal.emit(self.camera_ip, self.config_name)
            self.maximized = True
            self.current_size = self.SIZE_MAXI
            self.update_camera_status()
        else:
            self.maximize_false_signal.emit(self.camera_ip, self.config_name)
            self.current_size = self.SIZE
            self.maximized = False
            self.update_camera_status()
            

    # def on_minimize_button_clicked(self):
    #     pass

    def on_calibration_button_clicked(self):
        self.camera_stacked.set_progress("Calibrating...")
        self.thread = QThread()
        self.worker = IntrinsicCalibrationWorker(self.camera_ip,self.config_name, self.camera_resolution, self.camera_fps, self.camera_fov, self.camera_stacked)
        self.worker.moveToThread(self.thread)
        
        #execute the calibration
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.worker.finished.connect(self.on_calibration_finished)

        #update the camera status when the calibration is finished
        self.thread.start()

    def on_calibration_finished(self) -> None:
        QMessageBox.information(self, "Calibration finished", "The instrinsic calibration is finished with success")
        self.widget_calibration_status = self.STATUS.CALIBRATED
        self.update_camera_status()




    def update_camera_status(self):
        """Update the camera status displayed on the widget"""

        #* Update the battery status
        if self.battery:
            if self.battery_charging:
                self.battery_label.setPixmap(QIcon(r"Ui\assets\Battery-Charging.svg").pixmap(20, 20))  
            elif self.camera_battery <= 30:
                self.battery_label.setPixmap(QIcon(r"Ui\assets\Battery-Dead.svg").pixmap(20, 20))
            elif self.camera_battery <= 60:
                self.battery_label.setPixmap(QIcon(r"Ui\assets\Battery-Half.svg").pixmap(20, 20))
            else :
                self.battery_label.setPixmap(QIcon(r"Ui\assets\Battery-Full.svg").pixmap(20, 20))
        else:
            self.battery_label.setPixmap(QIcon(r"Ui\assets\Battery-Slash.svg").pixmap(20, 20))
        #* Update the calibration and connection status
        self.calibration_status_label.setPixmap(QIcon(self.calibration_status_icons[self.widget_calibration_status]).pixmap(20, 20))
        self.connection_status_label.setPixmap(QIcon(self.connection_status_icons[self.widget_connection_status]).pixmap(20, 20))

        #* Update widgets size
        self.main_frame.setFixedSize(self.current_size[0], self.current_size[1])
        self.camera_stacked.setFixedSize(self.current_size[0], self.current_size[1] - self.BAR_SIZE*2) 
        self.top_band_container.setFixedSize(self.current_size[0], self.BAR_SIZE)
        self.bottom_band_container.setFixedSize(self.current_size[0], self.BAR_SIZE)



class CameraDisplayManager(QWidget):
    """Manage the camera display with drag and drop functionality"""

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Créer un layout principal pour la classe
        self.layout = QVBoxLayout()

        # Créer une QScrollArea pour contenir le contenu défilable
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        # Créer un widget conteneur pour contenir le layout de la grille
        self.container_widget = QWidget()

        # Créer un layout de type QGridLayout pour disposer les widgets caméra
        self.scroll_layout = QGridLayout()
        self.container_widget.setLayout(self.scroll_layout)

        # Ajouter le widget conteneur à la zone de défilement
        self.scroll_area.setWidget(self.container_widget)

        # Ajouter la zone de défilement au layout principal
        self.layout.addWidget(self.scroll_area)
        self.setLayout(self.layout)

        self.camera_list : List[CameraDisplay] = []

        # Permettre le drag and drop
        self.setAcceptDrops(True)

        #connect the signal to update the widget
        # self.update_displaymanager.connect(self.update_widget)

    #! ----------------- Gestion du drag and drop ----------------- !#
    
    def dragEnterEvent(self, event):
        """Accepter le drag lorsqu'un élément compatible entre dans la zone"""
        event.accept()

    def dropEvent(self, event):
        """Gérer le drop de caméra et ajouter l'affichage correspondant"""
        if event.mimeData().hasText():
            # Extraire les informations de l'événement (cam_ip et config_name)
            cam_ip, config_name = event.mimeData().text().split(",")
            # Ajouter le widget de caméra
            self.add_camera_display(cam_ip, config_name)

            # Accepter l'événement de drop
            event.accept()

    #! ----------------- Gestion des widgets caméra ----------------- !#

    def add_camera_display(self, cam_ip: str, config_name: str):
        """Ajouter un affichage de caméra dans la grille"""
        if not any(camera.camera_ip == cam_ip and camera.config_name == config_name for camera in self.camera_list): #check if the camera is already added
            camera_display = CameraDisplay(cam_ip, config_name)
            line = len(self.camera_list) // 2
            row = len(self.camera_list) % 2
            self.camera_list.append(camera_display)
            
            # Ajouter le widget caméra dans la grille
            self.scroll_layout.addWidget(camera_display, line, row)

            # Connecter le signal de suppression du widget
            camera_display.delete_signal.connect(self.delete_camera_display)
            camera_display.maximize_true_signal.connect(self.on_maximize_camera_display_true)
            camera_display.maximize_false_signal.connect(self.on_maximize_camera_display_false)
            
            # Start the stream from camera for the camera display
            camera_display.camera_stacked.start_stream(cam_ip)

            status_manager = StatusManager()
            status_manager.add_used_config(cam_ip, config_name) #add to status database that the config is used
        else:
            QMessageBox.warning(self, "Camera already added", "The camera is already added to the display")

    def remove_all_camera_display(self):
        """Supprimer tous les affichages de caméra sans affecter la liste"""
        for camera_display in self.camera_list:
            self.scroll_layout.removeWidget(camera_display)

    def stop_all_camera_streams(self) -> None:
        """Stop all camera stream"""
        print("Stopping all camera streams...")
        for camera_display in self.camera_list:
            camera_display.camera_stacked.stop_stream()

    def start_all_camera_streams(self) -> None:
        """Start all camera stream"""
        print("Starting all camera streams...")
        for camera_display in self.camera_list:
            camera_display.camera_stacked.start_stream(camera_display.camera_ip)

    def update_camera_display_placement(self):
        """Réorganiser les affichages de caméra pour éviter les espaces vides"""
        self.remove_all_camera_display()

        # Ajouter les caméras dans le layout de la grille
        for i, camera_display in enumerate(self.camera_list):
            line = i // 2
            row = i % 2
            self.scroll_layout.addWidget(camera_display, line, row)
            print(f"Camera {i} added at line {line} and row {row}")

        # Forcer une mise à jour du layout
        self.scroll_layout.update()
    
    #! ----------------- Gestion des signaux ----------------- !#

    def on_maximize_camera_display_true(self, cam_ip: str, config_name: str):
        """Maximiser un affichage de caméra spécifique"""
        for camera_display in self.camera_list:
            if camera_display.camera_ip != cam_ip and camera_display.config_name != config_name:
                camera_display.hide()

    def on_maximize_camera_display_false(self, cam_ip: str, config_name: str):
        """Minimiser un affichage de caméra spécifique"""
        for camera_display in self.camera_list:
            if camera_display.camera_ip != cam_ip and camera_display.config_name != config_name:
                camera_display.show()

    def delete_camera_display(self, cam_ip: str, config_name: str):
        """Supprimer un affichage de caméra spécifique"""
        for camera_display in self.camera_list:
            if camera_display.camera_ip == cam_ip and camera_display.config_name == config_name:
                camera_find = camera_display #store the camera display to delete after the entire loop is done (check else statement)
            else:
                camera_display.show() #remember to show the hidden camera display if the supressed camera is maximized

        camera_find.deleteLater()
        self.camera_list.remove(camera_find)
        self.update_camera_display_placement()

        status_manager = StatusManager()
        status_manager.remove_used_config(cam_ip, config_name) #add to status database that the config is not used anymore

    def closeEvent(self, event:QEvent) -> None:
        status_manager = StatusManager()
        status_manager.remove_all_used_config()
        event.accept()

    def update_widget(self):
        self.update()



if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication([])
    window = CameraErrorWidget("Error")
    window.show()
    app.exec_()