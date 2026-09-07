from PyQt5.QtCore import QObject, pyqtSignal, QThread
import json
from config.Logger import Logger
import os
import numpy as np
from Pose_Estimation.markerAugmentation import augment_markers_all, hybrid_augmentation  # ← MODIFIER cet import
from Pose_Estimation.filtering_utils import read_config_json

class AugmentationWorker(QObject):
    """
    Worker PyQt pour exécuter l'augmentation des marqueurs dans un thread séparé.
    """
    finished = pyqtSignal(str) # Émet le chemin du fichier de sortie AUGMENTÉ
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, config_path: str, filtered_csv_path_in: str):
        super().__init__()
        self.config_path = config_path
        self.csv_path_in = filtered_csv_path_in # Fichier .csv FILTRÉ
        self.is_running = True
        self.logger = Logger.get_logger()

    def run(self):
        """
        Méthode principale qui exécute la logique d'augmentation HYBRIDE.
        """
        try:
            self.progress.emit("Loading configuration for augmentation...")
            self.logger.info("Starting hybrid marker augmentation")
            print(f"[AUGMENTATION HYBRID] Starting on {self.csv_path_in}\n")

            _, config_dict = read_config_json(self.config_path)
            
            if not config_dict:
                self.error.emit("Impossible de charger le fichier de configuration.")
                return

            use_hybrid = config_dict.get('markerAugmentation', {}).get('use_hybrid', False)
            augmenterModelName = config_dict.get('markerAugmentation', {}).get('augmenterModelName', 'LSTM')
            base, ext = os.path.splitext(self.csv_path_in)
            
            # ÉTAPE 1 : Générer le CSV LSTM complet
            self.progress.emit("Generating full LSTM...")
            
            result_min_y = augment_markers_all(config_dict, self.csv_path_in)
            
            if np.isnan(result_min_y):
                self.error.emit("[AUGMENTATION] Échec de l'augmentation LSTM.")
                return
            
            csv_lstm_full = f"{base}_{augmenterModelName}.csv"
            
            if not os.path.exists(csv_lstm_full):
                self.error.emit(f"[AUGMENTATION] Fichier LSTM non trouvé : {csv_lstm_full}")
                return
            
            if not use_hybrid:
                self.progress.emit("OK - LSTM augmentation completed!")
                print(f"[AUGMENTATION LSTM] Final file: {csv_lstm_full}\n")
                self.logger.info(f"LSTM CSV created: {csv_lstm_full}")
                self.finished.emit(csv_lstm_full)  # ← Émettre le fichier LSTM
                return

            # ÉTAPE 2 : Fusion avec les données réelles
            self.progress.emit("Merging with real data...")
            csv_hybrid_output = f"{base}_LSTM.csv"  # Au lieu de "_hybrid.csv"
            
            try:
                hybrid_augmentation(
                    csv_halpe26=self.csv_path_in,
                    csv_lstm=csv_lstm_full,
                    output_path=csv_hybrid_output
                )
                
                if self.is_running:
                    self.progress.emit("OK - Hybrid augmentation completed!")
                    print(f"[AUGMENTATION HYBRID] Hybrid file: {csv_hybrid_output}\n")
                    self.logger.info(f"Hybrid CSV created: {csv_hybrid_output}")
                    self.finished.emit(csv_hybrid_output)
                    
            except Exception as e:
                self.logger.error(f"[AUGMENTATION] Erreur hybridation : {e}", exc_info=True)
                self.error.emit(f"[AUGMENTATION] Erreur hybridation : {str(e)}")

        except Exception as e:
            self.logger.error(f"[AUGMENTATION] Erreur worker augmentation : {e}", exc_info=True)
            if self.is_running:
                self.error.emit(str(e))

    def stop(self):
        """Permet d'arrêter le worker prématurément."""
        self.is_running = False
        self.logger.info("[AUGMENTATION] Arrêt du worker d'augmentation demandé")

class MarkerAugmentationThread(QThread):
    """
    Thread PyQt5 pour gérer le AugmentationWorker.
    Il suit le même design que FilteringThread.py.
    """
    # Signaux pour l'UI
    augmentation_progress = pyqtSignal(str)
    augmentation_finished = pyqtSignal(str) # Émettra le chemin du .csv AUGMENTÉ
    augmentation_error = pyqtSignal(str)

    def __init__(self, config_path: str, filtered_csv_path_in: str):
        super().__init__()
        self.config_path = config_path
        self.csv_path_in = filtered_csv_path_in
        self.worker = None
        self.logger = Logger.get_logger()

    def run(self):
        """
        Crée le worker et exécute sa méthode run.
        """
        try:
            self.logger.info("Création du thread d'augmentation")
            self.worker = AugmentationWorker(self.config_path, self.csv_path_in)
            
            # Connecter les signaux du worker aux signaux du thread (relais)
            self.worker.progress.connect(self.augmentation_progress)
            self.worker.finished.connect(self.augmentation_finished)
            self.worker.error.connect(self.augmentation_error)
            
            self.logger.info("Exécution du worker")
            self.worker.run()

        except Exception as e:
            self.augmentation_error.emit(f"Erreur lors de la création du thread d'augmentation : {str(e)}")
            self.logger.error(f"Erreur création thread augmentation : {str(e)}", exc_info=True)

    def stop(self):
        if self.worker:
            self.worker.stop()
        self.quit()
        self.wait(5000)

