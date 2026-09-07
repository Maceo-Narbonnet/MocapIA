# threads/kinematicsThread.py

from PyQt5.QtCore import QObject, pyqtSignal, QThread
from config.Logger import Logger
import os
import subprocess
import shutil
import tempfile

class KinematicsWorker(QObject):
    """
    Worker PyQt pour executer la cinematique Pose2Sim (via subprocess)
    dans un thread separe.
    """
    # Signaux pour l'UI
    finished = pyqtSignal(str) # emettra le chemin du dossier de sortie OpenSim
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, trc_file_path: str, output_dir: str, conda_env: str):
        super().__init__()
        self.trc_file_path = trc_file_path
        self.output_dir = output_dir  # Dossier où creer les resultats
        self.conda_env = conda_env
        self.logger = Logger.get_logger()

    def _create_minimal_config(self, config_path: str):
        """Cree un fichier Config.toml minimal pour Pose2Sim"""
        minimal_config = """###############################################################################
## PROJECT PARAMETERS - MINIMAL CONFIG FOR KINEMATICS                        ##
###############################################################################

[project]
multi_person = false
participant_height = 1.88  # meters
participant_mass = 80      # kg
frame_rate = 'auto'
frame_range = 'auto'

[pose]
pose_model = 'LSTM'

[triangulation]
reproj_error_threshold_triangulation = 50
likelihood_threshold_triangulation = 0.05
min_cameras_for_triangulation = 2
interpolation = 'linear'
interp_if_gap_smaller_than = 10
fill_large_gaps_with = 'last_value'
show_interp_indices = true
handle_LR_swap = false
undistort_points = false
make_c3d = true

[filtering]
reject_outliers = true
filter = true
type = 'butterworth'
display_figures = false
make_c3d = true

   [filtering.butterworth]
   cut_off_frequency = 6
   order = 4

[markerAugmentation]
feet_on_floor = false
make_c3d = true

[kinematics]
use_augmentation = true
use_simple_model = false
right_left_symmetry = true
default_height = 1.8
remove_individual_scaling_setup = false
remove_individual_ik_setup = false
fastest_frames_to_remove_percent = 0.0
close_to_zero_speed_m = 0.0
large_hip_knee_angles = 90
trimmed_extrema_percent = 0.5

[logging]
use_custom_logging = true
save_logs = true
"""
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(minimal_config)
            self.logger.info(f"Config.toml minimal cree : {config_path}")
            return True
        except Exception as e:
            self.logger.error(f"Impossible de creer Config.toml minimal : {e}")
            return False

    def run(self):
        """
        Main function that executes the external kinematics logic.
        """
        temp_script_path = None  # Pour le nettoyage
        try:
            self.progress.emit("Begin of OpenSim kinematics analysis...")
            self.logger.info("Start of kinematics worker")
            print(f"[KINEMATICS] ----- Start of kinematics worker on {self.trc_file_path} -----")

            self.output_dir = os.path.normpath(self.output_dir)
            self.trc_file_path = os.path.normpath(self.trc_file_path)

            # --- 1. Verifier que le fichier TRC existe ---
            if not os.path.exists(self.trc_file_path):
                msg = f"Fichier TRC introuvable : {self.trc_file_path}"
                self.logger.error(msg)
                self.error.emit(msg)
                return

            # --- 2. Creer le dossier de sortie pour les resultats kinematics ---
            kinematics_dir = os.path.join(self.output_dir, "kinematics")
            os.makedirs(kinematics_dir, exist_ok=True)
            self.logger.info(f"Dossier kinematics cree : {kinematics_dir}")

            # --- 3. Creer un fichier Config.toml minimal dans output_dir ---
            config_toml_path = os.path.join(self.output_dir, "Config.toml")
            
            self.logger.info("Creation/reecriture du fichier Config.toml pour Pose2Sim")
            self.progress.emit("Creation de la configuration Pose2Sim...")
            
            if not self._create_minimal_config(config_toml_path):
                msg = "Impossible de creer le fichier Config.toml"
                self.logger.error(msg)
                self.error.emit(msg)
                return

            # --- 4. Creer le sous-dossier pose-3d et copier le TRC ---
            pose_3d_dir = os.path.join(self.output_dir, "pose-3d")
            os.makedirs(pose_3d_dir, exist_ok=True)
            
            trc_in_pose3d = os.path.join(pose_3d_dir, os.path.basename(self.trc_file_path))
            if os.path.abspath(self.trc_file_path) != os.path.abspath(trc_in_pose3d):
                shutil.copy2(self.trc_file_path, trc_in_pose3d)
                self.logger.info(f"Fichier TRC copie vers : {trc_in_pose3d}")
                self.progress.emit("Fichier TRC prepare pour Pose2Sim")
            
            # --- 5. Creer un script Python temporaire ---
            output_dir_unix = self.output_dir.replace('\\', '/')
            pose2sim_parent = r"D:\Users\Etudiant\Documents"
            
            python_script_content = f'''# -*- coding: utf-8 -*-
import sys
import os

# Forcer le flush immediat
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Desactiver les affichages graphiques
import matplotlib
matplotlib.use('Agg')
os.environ['MPLBACKEND'] = 'Agg'

print("[DEBUG] Debut du script Python", flush=True)

pose2sim_parent = r'{pose2sim_parent}'
sys.path.insert(0, pose2sim_parent)

print(f"[DEBUG] sys.path[0] = {{sys.path[0]}}", flush=True)
print(f"[DEBUG] Verification du dossier Pose2Sim...", flush=True)

pose2sim_path = os.path.join(pose2sim_parent, 'Pose2Sim')
if os.path.exists(pose2sim_path):
    print(f"[DEBUG] Pose2Sim trouve: {{pose2sim_path}}", flush=True)
    init_file = os.path.join(pose2sim_path, '__init__.py')
    print(f"[DEBUG] __init__.py existe: {{os.path.exists(init_file)}}", flush=True)
else:
    print(f"[ERROR] Pose2Sim NON trouve dans {{pose2sim_parent}}", flush=True)
    sys.exit(1)

print("[DEBUG] Tentative d'import Pose2Sim...", flush=True)

try:
    from Pose2Sim import Pose2Sim
    print("[DEBUG] Import Pose2Sim reussi!", flush=True)
except ImportError as e:
    print(f"[ERROR] ImportError: {{e}}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("[DEBUG] Lancement de kinematics...", flush=True)
try:
    Pose2Sim.kinematics(config='{output_dir_unix}')
    print("[DEBUG] Kinematics termine avec succes!", flush=True)
except Exception as e:
    print(f"[ERROR] Exception pendant kinematics: {{e}}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''
            
            # Ecrire le script dans un fichier temporaire
            temp_script_path = os.path.join(self.output_dir, "_temp_pose2sim_script.py")
            with open(temp_script_path, 'w', encoding='utf-8') as f:
                f.write(python_script_content)
            self.logger.info(f"Script temporaire cree: {temp_script_path}")

            # --- 6. Construire la commande ---
            command = [
                "conda", "run",
                "--no-capture-output",
                "-n", self.conda_env,
                "python", "-u", temp_script_path
            ]

            self.progress.emit(f"Lancement de Pose2Sim dans l'env '{self.conda_env}'...")
            self.logger.info(f"Pose2Sim sera importe depuis: {pose2sim_parent}")
            self.logger.info(f"Repertoire de travail: {self.output_dir}")
            self.logger.info(f"Commande: {' '.join(command)}")

            # --- 7. Executer la commande ---
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            env['MPLBACKEND'] = 'Agg'
            
            self.logger.info("Demarrage du subprocess...")
            
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='cp1252',
                errors='replace',
                cwd=self.output_dir,
                env=env,
                bufsize=1
            )
            
            # Lire la sortie en temps reel
            output_lines = []
            try:
                for line in iter(process.stdout.readline, ''):
                    if line:
                        line = line.rstrip()
                        output_lines.append(line)
                        self.logger.info(f"[POSE2SIM] {line}")
                        print(f"[POSE2SIM] {line}")
                        
                        if "[DEBUG]" in line or "[ERROR]" in line:
                            self.progress.emit(line)
                
                return_code = process.wait(timeout=600)
                
            except subprocess.TimeoutExpired:
                process.kill()
                msg = "Timeout: Pose2Sim a pris plus de 10 minutes"
                self.logger.error(msg)
                self.error.emit(msg)
                return

            if return_code != 0:
                error_msg = f"Pose2Sim a echoue avec le code {return_code}"
                self.logger.error(error_msg)
                if output_lines:
                    error_msg += f"\nDerniere ligne: {output_lines[-1]}"
                self.error.emit(error_msg)
                return

            self.logger.info("Execution de Pose2Sim terminee avec succes.")

            # --- 8. Verifier que les fichiers de sortie existent ---
            if not os.path.exists(kinematics_dir):
                msg = f"Le dossier kinematics n'a pas ete cree : {kinematics_dir}"
                self.logger.error(msg)
                self.error.emit(msg)
                return

            # --- 9. Succes ---
            self.progress.emit(f"Succes. Fichiers OpenSim generes dans {kinematics_dir}")
            self.finished.emit(kinematics_dir)
            print(f"[KINEMATICS] ----- Worker Kinematics termine -----")

        except subprocess.CalledProcessError as e:
            error_message = f"Erreur lors de l'execution de Pose2Sim. Le processus a echoue."
            self.logger.error(error_message)

            self.logger.error("--- Debut de la sortie d'erreur (stderr) du processus Pose2Sim echoue ---")
            error_output = e.stderr if e.stderr else e.stdout
            if error_output:
                for line in error_output.splitlines():
                    self.logger.error(f"[POSE2SIM-FAIL] {line}")
            else:
                self.logger.error("[POSE2SIM-FAIL] Aucune sortie d'erreur capturee.")
            self.logger.error("--- Fin de la sortie d'erreur (stderr) ---")

            simple_error = "Le processus Pose2Sim a echoue. Details:\n"
            if error_output:
                try:
                    last_line = [line for line in error_output.strip().splitlines() if line.strip()][-1]
                    simple_error += f"{last_line}"
                except IndexError:
                    simple_error += "Erreur inconnue (pas de sortie)."
            else:
                simple_error += "Erreur inconnue (pas de sortie)."

            self.error.emit(simple_error)

        except FileNotFoundError:
            error_message = "Erreur: Commande 'conda' non trouvee. Assurez-vous que Conda est dans le PATH système."
            self.logger.error(error_message)
            self.error.emit(error_message)

        except Exception as e:
            error_message = f"Une erreur inattendue est survenue dans le worker Kinematics : {str(e)}"
            self.logger.error(error_message)
            self.error.emit(error_message)

        finally:
            # Nettoyer le script temporaire
            if temp_script_path and os.path.exists(temp_script_path):
                try:
                    os.remove(temp_script_path)
                    self.logger.info("Script temporaire supprime")
                except:
                    pass

class KinematicsThread(QThread):
    """
    Wrapper QThread pour le KinematicsWorker.
    """
    # Signaux pour l'UI (relais)
    kinematics_progress = pyqtSignal(str)
    kinematics_finished = pyqtSignal(str)
    kinematics_error = pyqtSignal(str)

    def __init__(self, trc_file_path: str, output_dir: str, conda_env: str):
        super().__init__()
        self.trc_file_path = trc_file_path
        self.output_dir = output_dir
        self.conda_env = conda_env
        self.worker = None
        self.logger = Logger.get_logger()

    def run(self):
        """
        Cree le worker et execute sa methode run.
        """
        try:
            self.logger.info("Creation du thread Kinematics")
            self.worker = KinematicsWorker(
                self.trc_file_path,
                self.output_dir,
                self.conda_env
            )

            # Connecter les signaux du worker aux signaux du thread (relais)
            self.worker.progress.connect(self.kinematics_progress)
            self.worker.finished.connect(self.kinematics_finished)
            self.worker.error.connect(self.kinematics_error)

            self.logger.info("Execution du worker Kinematics")
            self.worker.run()

        except Exception as e:
            self.kinematics_error.emit(f"Erreur lors de la creation du thread Kinematics : {str(e)}")
            self.logger.error(f"Erreur init thread Kinematics: {str(e)}")