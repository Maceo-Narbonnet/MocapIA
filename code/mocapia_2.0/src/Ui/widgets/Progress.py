from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QDialog

class ProgressWidget(QDialog):
    """Display a progress bar and a message. Used it long operations.
    Args  : 
    message : str : message to display

    Methods :
    update_progress : update the progress bar
    set_message : update the message displayed
    """
    def __init__(self, message: str="In progress...", parent=None):
        super().__init__(parent)
        assert isinstance(message, str), "message must be a string"

        self.setFixedSize(300, 100)

        # Widgets de la barre de progression
        self.layout = QVBoxLayout(self)
        self.label = QLabel(message, self)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)  # Départ à 0%

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.progress_bar)

    def update_progress(self, value:int):
        """Update the progress bar value, must be between 0 and 100."""
        assert isinstance(value, int), "value must be an integer"
        assert 0 <= value <= 100, "value must be between 0 and 100"
        self.progress_bar.setValue(value)

    def set_message(self, message:str):
        """Upade progressbar message"""
        assert isinstance(message, str), "message must be a string"
        self.label.setText(message)