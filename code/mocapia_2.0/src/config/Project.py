#!Structure of projects class are defined in documentation/structure_projects.txt
import os
import json
import shutil
import pickle
import datetime
from config.Config_Manager import ConfigManager, CameraManager
from typing import List, Tuple, Dict


def create_project(project_path:str, experimenter_name:str=""):
    """Create a new project at the specified path"""
    assert isinstance(project_path, str), "project_path must be a string"
    assert project_path != "", "project_path cannot be empty"
    assert isinstance(experimenter_name, str), "experimenter_name must be a string"

    if not os.path.exists(project_path):
        os.makedirs(project_path)
        with open(os.path.join(project_path, 'logs.txt'), 'w') as f:
            f.write(f"Project created at {datetime.datetime.now()}\n")
        with open(os.path.join(project_path, 'info.json'), 'w') as f:
            json.dump({"experimenter": experimenter_name}, f, indent=4)
    else:
        raise FileExistsError(f"Directory {project_path} already exists")

def replace_project(project_path:str, experimenter_name:str=""): #call this function if the project already exists, 
    """Replace an existing project at the specified path"""
    assert isinstance(project_path, str), "project_path must be a string"
    assert project_path != "", "project_path cannot be empty"
    assert isinstance(experimenter_name, str), "experimenter_name must be a string"

    if os.path.exists(project_path):
        shutil.rmtree(project_path)
        create_project(project_path, experimenter_name)
    else:
        raise FileNotFoundError(f"Directory {project_path} does not exist")


class MocapProject:
    def __init__(self, project_path:str):
        self.project_path = project_path #path of the opened project
        self._check_directory_exist(project_path) #thows error if project path does not exist
        self.log_path = os.path.join(project_path, 'logs.txt') #path to the logs file of the project
        self._check_create_directory(self.log_path) #folder for experiments

    def _check_directory_exist(self, path:str) -> None:
        """throw error if directory does not exist"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Directory {path} does not exist")

    def _check_create_directory(self, path:str) -> None:
        """Create directory if it does not exist"""
        if not os.path.exists(path):
            os.makedirs(path)

    def _write_log(self, message:str):
        """ Add a message to the logs.txt file of an experiment """
        assert isinstance(message, str), "message must be a string"

        with open(self.log_path, 'a') as log_file:
            log_file.write(f"[{datetime.datetime.now()}] {message}\n")

    #! ---------- Experiments managing ---------- !#

    def add_experiment(self, experiment_name:str) -> None:
        """ Add a new experiment to the current opened project. 
        Args : experiment_name (str) : name of the experiment"""
        assert isinstance(experiment_name, str), "experiment_name must be a string"
        assert experiment_name != "", "experiment_name cannot be empty"

        config_manager = ConfigManager()
        camera_manager = CameraManager()
        camera_setup = []

        #add all info about used camera for the created experiment
        for camera in config_manager.get_used_config(): 
            cam_ip, config_name = camera
            camera_name = camera_manager.get_camera_name(cam_ip)
            camera_params = camera_manager.get_parameters_of_configuration(cam_ip, config_name)
            camera_setup.append({"name": camera_name, "ip": cam_ip, "config_params": camera_params})

        # get camera config parameters in one list and camera calibration in anonther list
        experiment_path = os.path.join(self.project_path, experiment_name)
        self._check_create_directory(experiment_path)

        # Create subfolders
        self._check_create_directory(os.path.join(experiment_path, 'calibration')) #folder for calibration data
        self._check_create_directory(os.path.join(experiment_path, 'captures')) #folder for raw capture data
        self._check_create_directory(os.path.join(experiment_path, 'analysis')) #folder for analysis data (output of analysis made by user)

        # Create config.json file
        config_path = os.path.join(experiment_path, 'config.json')
        config_data = {
            "experiment_name": experiment_name,
            "camera_setup": camera_setup,
            "date_created": str(datetime.datetime.now())
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)

        self.generate_calib_pickle(experiment_name, config_manager.get_used_config())

        self._write_log(f"Experiment {experiment_name} created")


    def generate_calib_pickle(self, experiment_name:str, camera_configs:List[Tuple[str, str]]) -> None:
        """for each camera in the experiment, generate a pickle file saved in the calibration folder of the experiment
        files has name : {camera_ip}_intrinsics.pickle"""
        assert isinstance(experiment_name, str), "experiment_name must be a string"

        for camera_ip, config_name in camera_configs:
            camera_manager = CameraManager()
            mtx, dist, objpoints, imgpoints = camera_manager.get_calibration_data(camera_ip, config_name)

            dico_pickle= {
                camera_ip : {
                    "mtx": mtx,
                    "dist": dist,
                    "objpoints": objpoints,
                    "imgpoints": imgpoints
                }
            }
                
            #open or create the pickle file in the calibration folder of the experiment, and write the calibration data
            pickle_path = os.path.join(self.project_path, experiment_name, 'calibration', f"{camera_ip}_intrinsics.pickle")
            with open(pickle_path, 'wb') as f:
                pickle.dump(dico_pickle, f)


    def get_experiment_list(self) -> List[str]:
        """Return a list of all the experiments in the project"""
        experiments = [name for name in os.listdir(self.project_path) if os.path.isdir(os.path.join(self.project_path, name))]
        return experiments
    
    # def get_experiment_config(self, experiment_name:str) -> List[Tuple[str, str]]:
    #     """For a given experiment_name, if the experiement exist in the project, return a list of tuple of camera ip and config for each cam added to the experiment
    #     Args : experiment_name (str) : name of the experiment
    #     Return exemple : [("CameraIp1", "CameraConfig1"), ("CameraIp2", "CameraConfig2")] for 2 camera added to the experiment"""
    #     assert isinstance(experiment_name, str), "experiment_name must be a string"
        
    #     if experiment_name in self.get_experiment_list(): #check if experiment exists
    #         experiement_config_path = os.path.join(self.project_path, experiment_name, 'config.json')
    #         with open(experiement_config_path, 'r') as f:
    #             config_data = json.load(f)
    #             res = []
    #             for config_data in config_data["camera_setup"]:
    #                 res.append((config_data["camera_ip"], config_data["config_name"])) #return a list of tuple of camera ip and config for each cam added to the experiment
    #             return res

    #     else:
    #         raise FileNotFoundError(f"Experiment {experiment_name} does not exist in the project")

    def get_experiment_camera_ips(self, experiment_name:str) -> List[str]:
        """Return a list of camera ips used in the experiment"""
        assert isinstance(experiment_name, str), "experiment_name must be a string"
        
        if experiment_name in self.get_experiment_list(): #check if experiment exists
            experiement_config_path = os.path.join(self.project_path, experiment_name, 'config.json')
            with open(experiement_config_path, 'r') as f:
                config_data = json.load(f)
                return [cam["ip"] for cam in config_data["camera_setup"]]
            
    def get_experiment_camera_dict(self, experiment_name:str)-> Dict[str, str]:
        """return a dictionnary of {camera_name : camera_ip} for the cameras used in the experiment"""
        assert isinstance(experiment_name, str), "experiment_name must be a string"
        
        if experiment_name in self.get_experiment_list():
            experiement_config_path = os.path.join(self.project_path, experiment_name, 'config.json')
            with open(experiement_config_path, 'r') as f:
                config_data = json.load(f)
                return {cam["name"]: cam["ip"] for cam in config_data["camera_setup"]}
        
    def get_experiment_config_parameters(self, experiment_name) -> List[dict]:
        """For a given experiment_name, if the experiement exist in the project, return a list of dictionary of camera parameters for each cam added to the experiment
        Args : experiment_name (str) : name of the experiment
        Return exemple : [{"name": "CameraName1", "ip": "CameraIp1", "config_params": {"param1": "value1", "param2": "value2"}}, {"name": "CameraName2", "ip": "CameraIp2", "config_params": {"param1": "value1", "param2": "value2"}}] for 2 camera added to the experiment"""
        
        if experiment_name in self.get_experiment_list():
            experiement_config_path = os.path.join(self.project_path, experiment_name, 'config.json')
            with open(experiement_config_path, 'r') as f:
                config_data = json.load(f)
                return config_data["camera_setup"]
        else:
            raise FileNotFoundError(f"Experiment {experiment_name} does not exist in the project")

    def get_img_size(self, experiment_name:str) -> Tuple[int, int]:
        """Return the image size of the cameras used in the experiment"""
        assert isinstance(experiment_name, str), "experiment_name must be a string"
        
        corresponding_resolution :Dict[str, Tuple[int, int]] = {"1080p": (1920, 1080), "1440p": (2560, 1440), "2.7k":(2560, 1440), "4k": (3840, 2160), "5.3k": (5280, 2972)}
        experiment_resolution = self.get_experiment_config_parameters(experiment_name)[0]["config_params"]["resolution"]
        img_size = corresponding_resolution[experiment_resolution] if experiment_resolution in corresponding_resolution else None
        return img_size




    #*captures for an experiement are stored in the captures folder of the experiment
    def add_capture(self, experiment_name, capture_name, videos:List[str]=[]):
        """Add a new capture to an experiment, the capture can contain multiple videos or be empty
        Args :
        experiment_name (str) : name of the experiment
        capture_name (str) : name of the capture
        videos (List[str]) : list of paths to the videos of the capture"""
        experiment_path = os.path.join(self.project_path, experiment_name)
        capture_path = os.path.join(experiment_path, 'captures', capture_name)
        self._check_create_directory(capture_path)

        for cam_id, video_file in enumerate(videos, start=1):
            video_name = f"{capture_name}_cam{cam_id}_video.mp4"
            destination = os.path.join(capture_path, video_name)
            # Ici on simule le déplacement de la vidéo
            os.rename(video_file, destination)

        self._write_log(f"In experiement {experiment_name} : Capture {capture_name} added with videos: {', '.join(videos)}")

        
    def add_video_to_capture(self, experiment_name, capture_name, video_path):
        """Add a video to an existing capture in an experiment"""
        experiment_path = os.path.join(self.project_path, experiment_name)
        capture_path = os.path.join(experiment_path, 'captures', capture_name)  # Path to the capture folder
        assert os.path.exists(capture_path), f"Capture {capture_name} does not exist in experiment {experiment_name}" 
        
        # Copy the video file to the capture folder
        video_name = os.path.basename(video_path)
        destination = os.path.join(capture_path, video_name)
        
        # Utiliser shutil.copy pour copier le fichier
        shutil.copy(video_path, destination)

        self._write_log(f"In experiment {experiment_name}: Video {video_name} added to capture {capture_name}")

    



if __name__ == "__main__":
    project = MocapProject(r"D:\Users\Etudiant\Documents\MoCapIA3\MocapIA_3\TestProject")
    print(project.get_experiment_list())
    print(project.get_experiment_config("Test1"))
    
    
    





        
