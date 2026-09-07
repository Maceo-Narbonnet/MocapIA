from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QGridLayout
from PyQt5.QtCore import pyqtSignal, QTimer
import os, time as t
from services.recording_service import RecordingService

class RecordingHeader(QWidget):
    # 兼容 CaptureManagerPage → CameraDisplayManager 的连接
    start_all_gopro_streams = pyqtSignal()
    stop_all_gopro_streams  = pyqtSignal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._rec_service = RecordingService(ctx, parent=self)

        self.layout = QGridLayout(self)
        proj_name = os.path.basename((getattr(ctx, "project_path", "") or "").rstrip("/\\")) or "-"
        exp_name  = getattr(ctx, "experiment_name", "") or "-"

        self.project_label   = QLabel(f"<b>Project : {proj_name}</b>")
        self.experiment_label= QLabel(f"<b>Experiment : {exp_name}</b>")
        self.btn = QPushButton("Start Filming")
        self.layout.addWidget(self.project_label,   0, 0)
        self.layout.addWidget(self.experiment_label,1, 0)
        self.layout.addWidget(self.btn,             0, 1, 2, 1)

        self._recording = False
        self.btn.clicked.connect(self._toggle_recording)

    # 兼容 MainWindow.open_project() 的刷新调用
    def refresh_labels(self):
        proj = (getattr(self.ctx, "project_path", "") or "").rstrip("/\\")
        pn = os.path.basename(proj) if proj else "-"
        en = getattr(self.ctx, "experiment_name", "") or "-"
        self.project_label.setText(f"<b>Project : {pn}</b>")
        self.experiment_label.setText(f"<b>Experiment : {en}</b>")
        self.update()

    def _toggle_recording(self):
        if not self._recording:
            # 关预览，留点时间
            self.stop_all_gopro_streams.emit()
            t.sleep(0.3)
            self._rec_service.start()
            self._recording = True
            self.btn.setText("Stop Filming")
        else:
            self._rec_service.stop()
            self._recording = False
            self.btn.setText("Start Filming")
            QTimer.singleShot(400, self.start_all_gopro_streams.emit)
