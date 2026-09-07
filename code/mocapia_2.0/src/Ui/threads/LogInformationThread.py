from PyQt5.QtCore import pyqtSignal, QObject

class OutputRedirector(QObject):
    """ Redirect stdout and stderr to PyQt UI """
    new_text = pyqtSignal(str)  # define the signal

    def __init__(self, original_stream):
        super().__init__()
        self.original_stream = original_stream  # stock original stdout / stderr

    def write(self, text):
        # Replace '#' with solid block for prettier progress bars
        if isinstance(text, str):
            text = text.replace('#', '█')

        # Send to UI
        if text.strip():
            self.new_text.emit(text.strip())

        # Still output to the original console (VSCode terminal)
        self.original_stream.write(text)
        self.original_stream.flush()

    def flush(self):
        self.original_stream.flush()  # make sure VSCode terminal refresh right away
