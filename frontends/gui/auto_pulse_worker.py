from PyQt6.QtCore import QObject, pyqtSignal


class AutoPulseWorker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller

    def run(self):
        try:
            result = self.controller.capture_once()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
