from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import QTimer
from PyQt5.QtSvg import QSvgWidget
import os

class RecordingIndicator(QWidget):
    """Just a simple widget to show a recording indicator (little red point) with a blinking effect."""
    def __init__(self, blink_interval=500, parent=None):
        """Initializes the widget with a blinking interval and a parent widget."""
        super().__init__(parent)
        svg_path = r"Ui\assets\recording_circle.svg"
        if not os.path.exists(svg_path):
            raise FileNotFoundError(f"Le fichier {svg_path} est introuvable.")
        
        self.svg_path = svg_path
        self.blink_interval = blink_interval  # Blinking interval in milliseconds
        self.is_visible = True  # Current visibility state of the indicator

        # Create a layout and add the SVG widget to it
        layout = QVBoxLayout(self)
        self.svg_widget = QSvgWidget(self.svg_path)
        self.svg_widget.setFixedSize(10, 10)  # Indicator size
        layout.addWidget(self.svg_widget)
        
        # create a timer to handle the blinking effect
        self.blink_timer = QTimer(self)
        self.blink_timer.setInterval(self.blink_interval)
        self.blink_timer.timeout.connect(self.toggle_visibility)

        self.svg_widget.hide()  # Hide the SVG by default

    def toggle_visibility(self):
        """Inverts the visibility state of the indicator."""
        if self.is_visible:
            self.svg_widget.hide()
        else:
            self.svg_widget.show()
        self.is_visible = not self.is_visible

    def start_blinking(self):
        """Start the blinking effect and show the indicator."""
        self.blink_timer.start()

    def stop_blinking(self):
        """Stop the blinking effect and hide the indicator."""
        self.blink_timer.stop()
        self.svg_widget.hide()
        self.is_visible = False
