from PyQt5.QtCore import QObject, pyqtSignal, QThread
import json
import logging
import os
from Pose_Estimation.filtering import filter_csv_file 
from Pose_Estimation.filtering_utils import read_config_json, convert_to_c3d, extract_trc_data, create_c3d_file

## a JSON file have been created to configure the setting of the filtering process, take a look at filtering_utils.py and that JSON file for more information.
## This thread will load the JSON file and execute the filtering process in a separate thread.

class FilteringWorker(QObject):
    """
    Worker PyQt pour exécuter le filtrage dans un thread séparé.
    Hérite de QObject pour pouvoir utiliser les signaux/slots.
    """

    finished = pyqtSignal(str)
    
    error = pyqtSignal(str)
    
    progress = pyqtSignal(str) ## Possibilité de faire une barre de progression plus a tard

    def __init__(self, config_path: str, csv_path_in: str):
        super().__init__()
        self.config_path = config_path
        self.csv_path_in = csv_path_in
        self.is_running = True

    def run(self):
        """
        Méthode principale qui exécute la logique de filtrage.
        Cette méthode sera appelée par le QThread.
        """
        try:
            self.progress.emit("Chargement de la configuration de filtrage...")
            
            # 1. Load the JSON file
            with open(self.config_path, 'r') as f:
                config_dict = json.load(f)
            
            self.progress.emit(f"Début du filtrage pour {os.path.basename(self.csv_path_in)}...")
            
            # 2. Execute the filtering process
            output_path = filter_csv_file(config_dict, self.csv_path_in)
            
            if self.is_running and output_path:
                self.progress.emit("Filtrage terminé avec succès.")
                self.finished.emit(output_path)
            elif self.is_running:
                 self.error.emit("La fonction de filtrage n'a pas retourné de chemin de sortie.")

        except Exception as e:
            logging.error(f"Une erreur est survenue durant le filtrage : {e}", exc_info=True)
            if self.is_running:
                self.error.emit(str(e))

    def stop(self):
        """Méthode pour demander l'arrêt du worker."""
        self.is_running = False



class FilteringThread(QThread):
    """
    QThread dédié au lancement du processus de filtrage,
    suivant le modèle de votre application.
    """
    filtering_progress = pyqtSignal(str)
    filtering_finished = pyqtSignal(str)
    filtering_error = pyqtSignal(str)

    def __init__(self, config_path: str, csv_path_in: str):
        super().__init__()
        self.config_path = config_path
        self.csv_path_in = csv_path_in
        self.worker = None

    def run(self):
        """Crée le worker et exécute sa méthode run."""
        try:
            self.worker = FilteringWorker(self.config_path, self.csv_path_in)
            self.filtering_progress.emit(f"Starting filtering on {os.path.basename(self.csv_path_in)}")
            
            # Connect signals
            self.worker.progress.connect(self.filtering_progress)
            self.worker.finished.connect(self.filtering_finished)
            self.worker.error.connect(self.filtering_error)
            
            # Launch the filtering process
            self.worker.run()
        except Exception as e:
            self.filtering_error.emit(f"Error in filtering thread: {str(e)}")
            logging.error(f"Filtering thread error: {str(e)}", exc_info=True)

    def stop(self):
        """Demande l'arrêt du worker et attend la fin du thread."""
        if self.worker:
            self.worker.stop()
        self.quit()
        self.wait()


