import sys
import cv2
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QComboBox
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QTimer, Qt

class VideoWidget(QWidget):
    def __init__(self, cam_id,fps_display=30, parent=None):
        super(VideoWidget, self).__init__(parent)
        self.setWindowTitle('Flux Vidéo en Direct')
        self.fps_display = fps_display
        self.cam_id = cam_id
        self.waiting_time = 1000 // self.fps_display

        # Layout principal pour organiser les widgets
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # QLabel pour afficher la vidéo
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label)


        # Démarrer avec une caméra spécifique
     
        self.cap = cv2.VideoCapture(self.cam_id)

        # Créer un timer pour mettre à jour le flux vidéo
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(self.waiting_time)  # 30 ms pour environ 33 images par seconde

    def get_camera_info(self):
        """Récupérer la résolution et les FPS de la caméra actuelle."""
        if self.cap.isOpened():
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            return width, height, fps
        return 0, 0, 0


    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            # Récupérer les informations de la caméra
            width, height, fps = self.get_camera_info()

            # Ajouter des informations sur le flux vidéo
            text = f"Camera {self.cam_id}: {width}x{height}, {fps:.2f} FPS"
            cv2.putText(frame, text, (10, height-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 80, 200), 2)

            # Redimensionner l'image pour qu'elle corresponde à la taille du QLabel
            frame = cv2.resize(frame, (self.label.width(), self.label.height()))

            # Convertir l'image en QImage
            height, width, _ = frame.shape
            bytes_per_line = 3 * width
            q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()

            # Mettre à jour le QLabel avec le QImage converti
            self.label.setPixmap(QPixmap.fromImage(q_image))

    def closeEvent(self, event):
        self.cap.release()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Créer le widget vidéo
    video_widget = VideoWidget(0)
    video_widget.resize(800, 600)
    video_widget.show()

    sys.exit(app.exec_())