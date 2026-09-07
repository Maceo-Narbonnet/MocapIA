from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QSlider, QSizePolicy, QHBoxLayout, QFileDialog, QMessageBox
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QPalette
import sys

#implemente des outils permetant de créer de fenetre de lecture video avec bouton play, pause et slider
#format pris en compte : mp4, mov,mp3 ...

class Video_Player(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PyQt5 Media Player")
        self.setGeometry(350, 100, 700, 500)
        
        p = self.palette()
        p.setColor(QPalette.Window, Qt.black)
        self.setPalette(p)
        
        self.init_ui()

    def init_ui(self):
        # Create media player object
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)

        # Create video widget object
        self.videowidget = QVideoWidget()

        # Create open button
        self.openBtn = QPushButton('Open Video')
        self.openBtn.clicked.connect(self.open_file)

        # Create button for playing
        self.playBtn = QPushButton('Play')
        self.playBtn.setEnabled(False)
        self.playBtn.clicked.connect(self.play_video)

        # Create slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)

        # Create label
        self.label = QLabel()
        self.label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        # Create hbox layout
        hboxLayout = QHBoxLayout()
        hboxLayout.setContentsMargins(0, 0, 0, 0)
        hboxLayout.addWidget(self.openBtn)
        hboxLayout.addWidget(self.playBtn)
        hboxLayout.addWidget(self.slider)

        # Create vbox layout
        vboxLayout = QVBoxLayout()
        vboxLayout.addWidget(self.videowidget)
        vboxLayout.addLayout(hboxLayout)
        vboxLayout.addWidget(self.label)
        self.setLayout(vboxLayout)

        # Set the video widget to the media player
        self.mediaPlayer.setVideoOutput(self.videowidget)

        # Connect signals
        self.mediaPlayer.durationChanged.connect(self.update_duration)
        self.mediaPlayer.positionChanged.connect(self.update_position)
        self.mediaPlayer.error.connect(self.handle_error)

    def open_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open Video")
        if filename:
            url = QUrl.fromLocalFile(filename)
            content = QMediaContent(url)
            self.mediaPlayer.setMedia(content)
            if not self.mediaPlayer.media().isNull():
                self.playBtn.setEnabled(True)
            else:
                self.show_error_message("Failed to load media.")

    def play_video(self):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
            self.playBtn.setText('Play')
        else:
            self.mediaPlayer.play()
            self.playBtn.setText('Pause')

    def update_duration(self, duration):
        self.slider.setRange(0, duration)

    def update_position(self, position):
        self.slider.setValue(position)

    def set_position(self, position):
        self.mediaPlayer.setPosition(position)

    def handle_error(self, error):
        self.show_error_message("An error occurred !")

    def show_error_message(self, message):
        QMessageBox.critical(self, "Error", message)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Video_Player()
    window.show()
    sys.exit(app.exec_())
