import json
import sys
import os
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QApplication, QWidget, QScrollArea, QMainWindow
from PyQt5.QtCore import QTimer


class CameraFramerateMonitorWidget(QWidget):
    def __init__(self, status_file_path):
        super().__init__()

        #class attribut setup
        self.setFixedSize(700, 120)

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

        # 1. show the current setting's label
        self.config_label = QLabel("current setting: (unknown)")
        self.config_label.setStyleSheet("font-size: 14px;")

        # 2. place it in the vertical layout
        self.content_layout.addWidget(self.config_label)

        # 3. Timer, check it every 3 seconds
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_config_change)
        self.timer.start(3000)  # 3 seconds

        self.check_config_change()  # read one time when initiall this


    def check_config_change(self):
        try:
            with open(self.status_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                experiment_name = data.get('experiment_name')
                current_config = data.get('camera_setup')

                if current_config != self.last_config:
                    if isinstance(current_config, list):
                        config_lines = [f"experiment name: {experiment_name}\ncurrent setting:"]
                        for item in current_config:
                            ip = item.get("ip", "unknown")
                            config = item.get("config_params", {})
                            resolution = config.get("resolution", "unknown")
                            fps = config.get("fps", "unknown")
                            fov = config.get("fov", "unknown")
                            config_lines.append(f"IP: {ip}, resolution: {resolution}, fps: {fps}, fov: {fov}")
                        display_text = "\n".join(config_lines)
                    else:
                        display_text = f"current setting:\n{current_config}"

                    self.config_label.setText(display_text)
                    self.last_config = current_config
        except Exception as e:
            print(f"Error reading {self.status_file_path}: {e}")
            self.config_label.setText("reading error")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Créer une fenêtre principale
    main_window = QMainWindow()
    status_path = r"D:\Users\Etudiant\Documents\MoCapIA4\mocapia_3\TestProject5\MoCap_Demo2\config.json"
    camera_status_list = CameraFramerateMonitorWidget(status_path)
    # Définir le widget central dans la fenêtre principale
    main_window.setCentralWidget(camera_status_list)

    # Afficher la fenêtre principale
    main_window.show()

    # Exécuter la boucle de l'application
    sys.exit(app.exec_())
    app.exec_()