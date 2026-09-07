import sys
from PyQt5.QtWidgets import QDialog, QTextEdit, QPushButton, QVBoxLayout
from Ui.threads.LogInformationThread import OutputRedirector

class LogInformation(QDialog):
    def __init__(self, script_path, working_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log Information")
        self.setGeometry(200, 200, 600, 400)

        # creat the log window
        self.log_output = QTextEdit(self)
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("The log infomation will be shown here...")

        # creat close button
        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self.close)

        # creat the layout
        layout = QVBoxLayout()
        layout.addWidget(self.log_output)
        layout.addWidget(self.close_button)
        # self.setLayout(layout)
        self.setLayout(layout)

        # redirect stdout and stderr
        self.stdout_redirector = OutputRedirector(sys.stdout)
        self.stderr_redirector = OutputRedirector(sys.stderr)
        self.stdout_redirector.new_text.connect(self.log_output.append)
        self.stderr_redirector.new_text.connect(self.log_output.append)
        # self.stdout_redirector.new_text.connect(self.append_log)
        # self.stderr_redirector.new_text.connect(self.append_log)

        sys.stdout = self.stdout_redirector    # redirect stdout 
        sys.stderr = self.stderr_redirector    # redirect stderr

        self.worker = None    # process object



    def closeEvent(self, event):
        """ make sure the thread stops correctly when the window is closed """
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

        if self.worker:
            self.worker.stop()
            self.worker.wait()
            self.worker = None

        event.accept()
