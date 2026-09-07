from PyQt5.QtCore import QObject, pyqtSignal

class ProjectContext(QObject):
    """Global context: emits a `changed` signal whenever the project or experiment is modified."""
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.project_path = ""
        self.experiment_name = ""

    def set_project(self, path: str):
        self.project_path = path or ""
        self.changed.emit()

    def set_experiment(self, name: str):
        self.experiment_name = name or ""
        self.changed.emit()
