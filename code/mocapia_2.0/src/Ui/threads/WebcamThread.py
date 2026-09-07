import cv2
from PyQt5.QtCore import QThread, pyqtSignal


class WebcamThread(QThread):
    """Thread pour afficher le flux webcam en parallèle"""
    frame_ready = pyqtSignal(object)  # Signal pour transmettre une nouvelle image

    def __init__(self, serial_number):
        super().__init__()
        self.ip_camera = f"172.2{serial_number[-3]}.1{serial_number[-2]}{serial_number[-1]}.51"
        self.is_running = False

    def run(self):
        rtsp_url = f"rtsp://{self.ip_camera}:554/live"
        cap = cv2.VideoCapture(rtsp_url)

        if not cap.isOpened():
            print(f"Erreur : impossible de se connecter au flux RTSP à {rtsp_url}")
            return
        
        print("Flux RTSP démarré avec succès...")
        self.is_running = True

        while self.is_running:
            ret, frame = cap.read()
            if ret:
                self.frame_ready.emit(frame)  # Émettre l'image à l'interface utilisateur
            else:
                print("Erreur lors de la lecture du flux.")
                break

        cap.release()

    def stop(self):
        """Arrête le thread de webcam"""
        self.is_running = False
        self.quit()
        self.wait()