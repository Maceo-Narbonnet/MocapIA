import json
import sys
import os
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QApplication, QWidget, QScrollArea, QMainWindow, QPushButton, QSizePolicy
from PyQt5.QtCore import QTimer , pyqtSlot, Qt

def get_status_json_path():
    if getattr(sys, 'frozen', False):
        # if it's the program already wrapped(like PyInstaller), obtain the catelogue of executable file
        current_path = os.path.dirname(sys.executable)
        base_path = os.path.dirname(os.path.dirname(current_path))
    else:
        # if it's source code running
        current_path = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.dirname(os.path.dirname(current_path))

    # creat the indirect path
    status_path = os.path.join(base_path, "config", "Settings", "status.json")
    return status_path

class StatusMonitorWidget(QWidget):
    def __init__(self, status_file_path, min_height=220):
        super().__init__()

        #class attribut setup
        self.setMinimumHeight(min_height)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        #widget structure
        self.main_layout = QVBoxLayout()

        #scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)

        self.content_widget.setLayout(self.content_layout)
        self.scroll_area.setWidget(self.content_widget)

        #add to main layout
        self.main_layout.addWidget(self.scroll_area)
        self.setLayout(self.main_layout)


        self.status_file_path = status_file_path
        self.last_config = None

        #button for refreshing the camera settings
        self.refresh_camera_setting_button = QPushButton("Refresh the camera settings")
        self.refresh_camera_setting_button.clicked.connect(self.on_click_refresh_camera_settings)
        self.main_layout.addWidget(self.refresh_camera_setting_button)

        # 1. show the current setting's label
        self.config_label = QLabel("current setting: (unknown)")
        self.config_label.setStyleSheet("font-size: 12px;")

        # 2. place it in the vertical layout
        self.content_layout.addWidget(self.config_label)

        # 3. Timer, check it every 3 seconds
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_config_change)
        self.timer.start(3000)  # 3 seconds

        self.check_config_change()  # read one time when initiall this


    @pyqtSlot()
    def reload_from_file(self):
        self.last_config = object()   # regard as changed
        self.check_config_change()

    def check_config_change(self):
        try:
            with open(self.status_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            current_config = data.get('current_used_config')

            if current_config != self.last_config:
                if isinstance(current_config, list):
                    if not current_config:
                        display_text = "current setting:\n(empty)"
                    else:
                        lines = ["current setting:"]
                        for item in current_config:
                            lines.append(f"- IP: {item.get('ip','unknown')} | Config: {item.get('config_name','unknown')}")
                        display_text = "\n".join(lines)
                else:
                    display_text = f"current setting:\n{current_config}"

                self.config_label.setText(display_text)
                self.last_config = current_config
        except Exception as e:
            print(f"Error reading {self.status_file_path}: {e}")
            self.config_label.setText("reading error")

    def on_click_refresh_camera_settings(self):
        try:
            with open(self.status_file_path, 'r', encoding='utf-8') as f:
                status_data = json.load(f)

            status_data["current_used_config"] = []

            with open(self.status_file_path, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, indent=4)

            print("Clear the current_used_config successfully")

            # refresh UI
            self.reload_from_file()
        except Exception as e:
            print(f"Fail to refresh the camera settings: {e}")
            self.config_label.setText("reading error")



if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Créer une fenêtre principale
    main_window = QMainWindow()
    status_path = get_status_json_path()
    camera_status_list = StatusMonitorWidget(status_path)
    # Définir le widget central dans la fenêtre principale
    main_window.setCentralWidget(camera_status_list)

    # Afficher la fenêtre principale
    main_window.show()

    # Exécuter la boucle de l'application
    sys.exit(app.exec_())
    app.exec_()