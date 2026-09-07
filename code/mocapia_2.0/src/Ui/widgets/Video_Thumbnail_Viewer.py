import sys
import os
import cv2
from PyQt5.QtWidgets import QApplication, QWidget, QGridLayout, QLabel, QScrollArea, QSizePolicy
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QSize, pyqtSignal

class ClickableLabel(QLabel):
    # Signal to be emitted when the label is clicked
    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_StyledBackground, True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class VideoThumbnailViewer(QWidget):
    def __init__(self, video_folder, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Thumbnail Viewer")  # Optional if it's embedded in another window
        self.setGeometry(100, 100, 1000, 800)  # Optional if it's embedded in another window

        self.video_folder = video_folder

        # Layout
        self.layout = QGridLayout()
        self.setLayout(self.layout)

        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.layout.addWidget(self.scroll_area)

        # Content widget in the scroll area
        self.content_widget = QWidget()
        self.scroll_area.setWidget(self.content_widget)
        self.content_layout = QGridLayout()
        self.content_widget.setLayout(self.content_layout)

        # Load video thumbnails
        self.load_video_thumbnails()

    def load_video_thumbnails(self):
        files = [f for f in os.listdir(self.video_folder) if f.endswith(('.mp4', '.avi', '.MOV', '.mov', '.mp3'))]
        thumbnail_size = (150, 100)  # Taille des miniatures (largeur, hauteur)
        thumbnail_widget_size = QSize(150, 150)  # Taille totale des widgets de miniatures (avec l'espace pour le nom)
        row = 0
        col = 0

        # Clear previous content
        for i in reversed(range(self.content_layout.count())):
            widget = self.content_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        for file in files:
            video_path = os.path.join(self.video_folder, file)
            thumbnail = self.get_video_thumbnail(video_path, thumbnail_size)
            pixmap = QPixmap.fromImage(thumbnail)
            
            # Create and add thumbnail label
            thumbnail_label = ClickableLabel()
            thumbnail_label.setPixmap(pixmap)
            thumbnail_label.setFixedSize(thumbnail_size[0], thumbnail_size[1])
            thumbnail_label.setScaledContents(True)
            
            # Create and add name label
            name_label = QLabel(file)
            # name_label.setAlignment(Qt.AlignCenter)
            name_label.setFixedSize(thumbnail_size[0], 50)  # Fixed height for name labels
            
            # Connect the click event of the thumbnail to a method
            thumbnail_label.clicked.connect(lambda f=file: self.on_thumbnail_clicked(f))
            
            # Create a widget to hold both thumbnail and name labels
            widget = QWidget()
            widget_layout = QGridLayout()
            widget_layout.addWidget(thumbnail_label, 0, 0)
            widget_layout.addWidget(name_label, 1, 0)
            widget.setLayout(widget_layout)
            widget.setFixedSize(thumbnail_widget_size)

            # Add the combined widget to the content layout
            self.content_layout.addWidget(widget, row, col)
            
            col += 1
            if col > 4:  # Changez ce nombre pour définir combien d'éléments par ligne
                col = 0
                row += 1

    def get_video_thumbnail(self, video_path, size):
        cap = cv2.VideoCapture(video_path)
        success, frame = cap.read()
        cap.release()
        if success:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Redimensionner l'image
            frame = cv2.resize(frame, size)
            qimg = QImage(frame.data, size[0], size[1], 3 * size[0], QImage.Format_RGB888)
            return qimg
        else:
            return QImage()

    def on_thumbnail_clicked(self, file_name):
        print(f"Clicked on: {file_name}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    video_folder = 'C:\\Users\\Etudiant\\Documents\\Stages-TX\\TN09-Mocapia-Alexandru\\Interface_Graphique_conception\\graphic_items\\video'
    window = VideoThumbnailViewer(video_folder)
    window.show()
    sys.exit(app.exec_())
