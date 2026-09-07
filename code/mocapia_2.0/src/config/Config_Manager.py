import json
import os
from typing import List, Dict, Tuple

#This file contains the class ConfigManager, which is used to manage the configuration files of the application.
#The configuration files are JSON files that contain the settings of the application.
#There are three configuration files:
#- status.json: contains the status of the application (last project settings, current project, current used camera)
#- config.json: contains the general settings of the application and preferences 
#- camera_database.json: contains the list of cameras that can be used in the application


class ConfigManager:
    def __init__(self):
    
        config_dir = os.path.dirname(os.path.abspath(__file__))  
        settings_dir = os.path.join(config_dir, 'Settings')
        self.status_json = os.path.join(settings_dir, 'status.json') # path of configs files
        self.config_json = os.path.join(settings_dir, 'config.json')
        self.camera_json = os.path.join(settings_dir, "camera_database.json")
        self.status_data = self._load_config(self.status_json)
        self.camera_data = self._load_config(self.camera_json)
        self.config_data = self._load_config(self.config_json)

    def _load_config(self, file):
        # Charger les données depuis le fichier JSON
        if os.path.exists(file):
            with open(file, 'r') as file:
                try:
                    return json.load(file)
                except json.JSONDecodeError:
                    print(f"Erreur lors du chargement du fichier {file}")
                    return {}
        else:
            print(f"Le fichier {file} n'existe pas.")
            return {}

    def _save_config(self,data, file):
        # Sauvegarder les données dans le fichier JSON
        with open(file, 'w') as file:
            json.dump(data, file, indent=4)

    def get_last_project_settings(self):
        # Obtenir les paramètres du dernier projet
        return self.status_data.get('last_project_settings', {})
    
    def get_current_project_path(self):
        # Obtenir les paramètres du projet actuel
        return self.status_data["current_project"]["path"]

    def set_last_project_settings(self, path, experimenter):
        # Modifier les paramètres du dernier projet
        self.status_data['last_project_settings'] = {
            'path': path,
            'experimenter': experimenter
        }
        self._save_config(self.status_data, self.status_json)
    
    def set_current_project_path(self, path):
        # Modifier les paramètres du projet actuel
        self.status_data['current_project']['path'] = path
        self._save_config(self.status_data, self.status_json)

    def set_current_project_saved(self, saved):
        # Modifier l'état de sauvegarde du projet actuel
        assert isinstance(saved, bool), "saved doit être un booléen."
        self.status_data['current_project']['saved'] = saved
        self._save_config(self.status_data, self.status_json)
        
    def get_project_path_saved(self):
        # get the current script's absolute path
        current_path = os.path.dirname(os.path.abspath(__file__))
        # In case of the saved project path is in the current directory's "saved_projects" folder
        project_path = os.path.join(current_path, "saved_projects")
        if project_path:
            return project_path

    def get_current_project_saved(self):
        # Obtenir l'état de sauvegarde du projet actuel
        return self.status_data.get('current_project', {}).get('saved', False)
    
    def is_used_camera_config(self, ip:str, config_name:str) -> bool:
        """Return True if the camera configuration is used in the application, False otherwise"""
        assert isinstance(ip, str), "ip must be a string."
        assert isinstance(config_name, str), "config_name must be a string."

        for camera in self.status_data['current_used_camera']:
            if camera['ip'] == ip and camera['config_name'] == config_name:
                return True
        return False

    

    def set_camera_config_used(self, ip:str, config_name:str):
        """The camera is now used in the application, this function will add the camera to the current_used_camera in status.json
        Args : camera ip and config name of the camera, (all str)"""
        assert isinstance(ip, str), "ip must be a string."
        assert isinstance(config_name, str), "config_name must be a string."
        assert self.camera_exist(ip), "La caméra n'existe pas dans la base de données."
        assert self.configuration_exist_in_camera(ip, config_name), "La configuration n'existe pas pour la caméra."

        #add the camera to the current_used_camera
        if self.is_used_camera_config(ip, config_name):
            raise ValueError(f"The camera {ip} with the configuration {config_name} is already used in the application.")
        self.status_data['current_used_camera'].append( {
            'ip': ip,
            'config_name': config_name
        })
        self._save_config(self.status_data, self.status_json)
        return

    def remove_camera_config_used(self, ip:str, config_name:str):
        """The camera is now unused in the application, this function will remove the camera form the current_used_camera in status.json
        Args : camera ip and config name of the camera, (all str)"""

        assert isinstance(ip, str), "ip must be a string."
        assert isinstance(config_name, str), "config_name must be a string."
        assert self.camera_exist(ip), "La caméra n'existe pas dans la base de données."
        assert self.configuration_exist_in_camera(ip, config_name), "La configuration n'existe pas pour la caméra."

        #remove the camera from the current_used_camera
        for camera in self.status_data['current_used_camera']:
            if camera['ip'] == ip and camera['config_name'] == config_name:
                self.status_data['current_used_camera'].remove(camera)
                self._save_config(self.status_data, self.status_json)
                return
        print(f"La caméra {ip} avec la configuration {config_name} n'est pas utilisée dans l'application.")

    def get_used_config(self)->List[Tuple[str, str]]:
        """Return the list of used configurations
        Result example : [("CameraIp1", "CameraConfig1"), ("CameraIp2", "CameraConfig2")] for 2 camera added to the experiment"""
        return [(camera['ip'], camera['config_name']) for camera in self.status_data['current_used_config']]




    def add_camera(self, name : str, ip : str) -> None:
        """Args :
        name : str : Name of the camera to add
        ip : str : IP of the camera to add
        create_default_config : bool : If True, create a default configuration for the camera
        """
        for camera in self.camera_data:
            if camera['name'] == name and camera['ip'] == ip:
                print(f"La caméra {name} ({ip}) existe déjà.")
                return
        self.camera_data.append({
            'name': name,
            'ip': ip
        })
        self._save_config(self.camera_data, self.camera_json)
    
    def set_used_camera(self, name : str, ip : str) -> None:
        """Add the camera current_used_camera in status.json, if the camera is not already in the current_used_camera"""
        for camera in self.status_data['current_used_camera']:
            if camera['name'] == name and camera['ip'] == ip:
                print(f"La caméra {name} ({ip}) est déjà utilisée.")
                return
        #else we add the camera to the current_used_camera
        self.status_data['current_used_camera'].append( {
            'name': name,
            'ip': ip
        })
        self._save_config(self.status_data, self.status_json)

    def remove_used_camera(self, name : str, ip : str) -> None:
        """Remove the camera current_used_camera in status.json, if the camera is in the current_used_camera"""
        for camera in self.status_data['current_used_camera']:
            if camera['name'] == name and camera['ip'] == ip:
                self.status_data['current_used_camera'].remove(camera)
                self._save_config(self.status_data, self.status_json)
                return
        print(f"La caméra {name} ({ip}) n'est pas utilisée.")
    
    def delete_camera(self, name : str, ip : str) -> None:
        """Args :
        name : str : Name of the camera to delete
        ip : str : IP of the camera to delete
        """
        for camera in self.camera_data:
            if camera['name'] == name and camera['ip'] == ip: #remove the camera from the camera_database
                self.camera_data.remove(camera)
                self._save_config(self.camera_data, self.camera_json)
        for camera in self.status_data['current_used_camera']: #remove the camera from the current_used_camera
            if camera['name'] == name and camera['ip'] == ip:
                self.status_data['current_used_camera'].remove(camera)
                self._save_config(self.status_data, self.status_json)


class CameraManager:
    """Use this class to manage camera database of the app"""

    def __init__(self):
        self.json_path = "config\Settings\camera_database.json"
        self.camera_data = self._load_config(self.json_path)

    def _load_config(self, file):
        # Charger les données depuis le fichier JSON
        if os.path.exists(file):
            with open(file, 'r') as file:
                try:
                    return json.load(file)
                except json.JSONDecodeError:
                    print(f"Erreur lors du chargement du fichier {file}")
                    return {}
        else:
            print(f"Le fichier {file} n'existe pas.")
            return {}
        
    def _save_config(self,data, file):
        print("called _save_config")
        # Sauvegarder les données dans le fichier JSON
        with open(file, 'w') as file:
            json.dump(data, file, indent=4)

    def camera_exist(self, ip : str) -> bool:
        """Return True if the camera exists in the camera database, False otherwise,
        Args :
        ip : str : IP of the camera to check
        Remember IP is unique for each camera
        """
        for camera in self.camera_data:
            if camera['ip'] == ip:
                return True
        return False

    
    def add_camera(self, name : str, ip : str, default:bool = False) -> bool:
        """Add a camera to the camera database, if the camera is not already in the camera database
        Args :
            name : str : Name of the camera to add
            ip : str : IP of the camera to add
            default : bool : If True, create a default configuration for the camera
        Return True if the camera is added, False otherwise
        """
        if self.camera_exist(ip):
            print(f"La caméra {name} ({ip}) existe déjà.")
            return False
        if default:
            self.camera_data.append({
                'name': name,
                'ip': ip,
                'configurations': [
                    {
                        "name": "Default",
                        "parameters": {
                            "resolution": "1080p",
                            "fps": "30",
                            "fov": "Linear",
                            "favorite": True,
                            "other": {}
                        },
                        "intrinsic_calib": {
                            "matrix": [],
                            "dist": [],
                            "objpoints": [],
                            "imgpoints": []
                        }
                    }
                ]
            })
            self._save_config(self.camera_data, self.json_path)
            return True
        else:
            self.camera_data.append({
                'name': name,
                'ip': ip,
                'configurations': []
            })
            self._save_config(self.camera_data, self.json_path)
            return True
    
    def get_camera_name(self, ip : str) -> str:
        """Return the name of the camera
        Args :
            ip : str : IP of the camera
        Return the name of the camera, None if the camera does not exist"""
        assert self.camera_exist(ip), "La caméra n'existe pas dans la base de données."
        for camera in self.camera_data:
            if camera['ip'] == ip:
                return camera['name']
        return None
    
    def delete_camera(self, ip : str) -> bool:
        """Delete a camera from the camera database, if the camera is in the camera database
        Args :
            name : str : Name of the camera to delete
            ip : str : IP of the camera to delete
        Return True if the camera is deleted, False otherwise
        """
        for camera in self.camera_data:
            if camera['ip'] == ip:
                self.camera_data.remove(camera)
                self._save_config(self.camera_data, self.json_path)
                return True
        return False
    
    def configuration_exist_in_camera(self, ip:str, config_name:str) -> bool:
        """Return True if the configuration exists in the camera database, False otherwise,
        Args :
        ip : str : IP of the camera to check
        config_name : str : Name of the configuration to check
        """
        assert self.camera_exist(ip), "La caméra n'existe pas dans la base de données."
        print("called configuration_exist_in_camera :", ip, config_name)
        for camera in self.camera_data:
            if camera['ip'] == ip:
                # print("Camera found", camera['ip'], "configurations", camera['configurations'])
                for config in camera['configurations']:
                    print("config", config_name, config['name'])
                    print(type(config_name), type(config['name']))
                    if config['name'] == config_name:
                        return True
        return False
      
    
    def add_configuration(self, ip:str, config_name:str, config_resolution:str, config_fps:str, config_fov:str,mtx=[], dist=[], objpoints=[], imgpoints=[], config_other={})-> bool:
        """add a camera configuration to the camera database, if the camera is not already in the camera database
        Args :
            name : str : Name of the camera to add
            ip : str : IP of the camera to add
        Return True if the configuration is added, False otherwise
        """
        assert self.camera_exist(ip), "La caméra n'existe pas dans la base de données."
        if not(self.configuration_exist_in_camera(ip, config_name)):
            new_config = {
                "name": config_name,
                "parameters": {
                    "resolution": config_resolution,
                    "fps": config_fps,
                    "fov": config_fov,
                    "favorite": False,
                    "other": config_other
                },
                "intrinsic_calib": {
                            "mtx": mtx,
                            "dist": dist,
                            "objpoints": objpoints,
                            "imgpoints": imgpoints
                        }
            }
            try:
                for camera in self.camera_data:
                    if camera['ip'] == ip:
                        camera['configurations'].append(new_config)
                        self._save_config(self.camera_data, self.json_path)
                        return True
            except Exception as e:
                print(f"Erreur lors de l'ajout de la configuration : {e}")
                return False
        else:
            print(f"La configuration {config_name} existe déjà pour la caméra {ip}.")
            return False

    def delete_configuration_from_one_camera(self, ip:str, config_name:str) -> bool:
        """Delete a configuration from one camera, if the camera is in the camera database
        Args :
            ip : str : IP of the camera to delete
            config_name : str : Name of the configuration to delete
        Return True if the configuration is deleted, False otherwise
        """
        assert self.camera_exist(ip), "La caméra n'existe pas dans la base de données."
        print("called delete_configuration_from_one_camera :", ip, config_name)
        for camera in self.camera_data:
            if camera['ip'] == ip:
                for config in camera['configurations']:
                    if config['name'] == config_name:
                        camera['configurations'].remove(config)
                        self._save_config(self.camera_data, self.json_path)
                        return True
        return False
    
    def delete_configuration_from_all_cameras(self, config_name:str) -> bool:
        """Delete a configuration from all cameras
        Args :
            config_name : str : Name of the configuration to delete
        Return True if the configuration is deleted, False otherwise
        """
        for camera in self.camera_data:
            for config in camera['configurations']:
                if config['name'] == config_name:
                    camera['configurations'].remove(config)
                    self._save_config(self.camera_data, self.json_path)
                    return True
        return False

    def add_intrinsic_calib_to_camera_configuration(self, ip:str, config_name:str, mtx, dist, objpoints, imgpoints)->bool:
        """Add intrinsic calibration to a camera configuration
        Args :
            ip : str : IP of the camera
            config_name : str : Name of the configuration
            mtx, dist, objpoints, imgpoints : intrinsic calibration parameters
        Return True if the intrinsic calibration is added, False otherwise"""

        assert self.camera_exist(ip), "La caméra n'existe pas dans la base de données."
        assert self.configuration_exist_in_camera(ip, config_name), "La configuration n'existe pas pour la caméra."
        for camera in self.camera_data:
            if camera['ip'] == ip:
                for config in camera['configurations']:
                    if config['name'] == config_name:
                        config['intrinsic_calib'] ={
                            "mtx": mtx,
                            "dist": dist,
                            "objpoints": objpoints,
                            "imgpoints": imgpoints
                        }
                        self._save_config(self.camera_data, self.json_path)
                        return True
        return False
    
    def get_calibration_data(self, ip:str, config_name:str)->Tuple:
        """Return the calibration data of the camera configuration
        Args :
            ip : str : IP of the camera
            config_name : str : Name of the configuration
        Return the calibration data of the camera configuration, None if the configuration does not exist"""
        print("Config Name", config_name)
        assert self.camera_exist(ip), "La caméra n'existe pas dans la base de données."
        assert self.configuration_exist_in_camera(ip, config_name), "La configuration n'existe pas pour la caméra."
        for camera in self.camera_data:
            print("Camera", camera)
            if camera['ip'] == ip:
                for config in camera['configurations']:
                    if config['name'] == config_name:
                        print("Config", config)
                        return config['intrinsic_calib']['mtx'], config['intrinsic_calib']['dist'], config['intrinsic_calib']['objpoints'], config['intrinsic_calib']['imgpoints']
        return None
    
    def get_parameters_of_configuration(self, ip:str, config_name:str)->dict:
        """Return the parameters of the configuration
        Args :
            ip : str : IP of the camera
            config_name : str : Name of the configuration
        Return the parameters of the configuration, None if the configuration does not exist"""
        assert self.camera_exist(ip), "La caméra n'existe pas dans la base de données."
        assert self.configuration_exist_in_camera(ip, config_name), "La configuration n'existe pas pour la caméra."
        for camera in self.camera_data:
            if camera['ip'] == ip:
                for config in camera['configurations']:
                    if config['name'] == config_name:
                        return config['parameters']
        return None
    
    def get_configuration(self, ip:str, config_name:str):
        """Return the configuration
        Args :
            ip : str : IP of the camera
            config_name : str : Name of the configuration
        Return the configuration, None if the configuration does not exist"""
        assert self.camera_exist(ip), "La caméra n'existe pas dans la base de données."
        assert self.configuration_exist_in_camera(ip, config_name), "La configuration n'existe pas pour la caméra."
        for camera in self.camera_data:
            if camera['ip'] == ip:
                for config in camera['configurations']:
                    if config['name'] == config_name:
                        return config
        return None

    
    def set_favorite(self, ip:str, config_name:str, choice:bool)->bool:
        """Set the favorite status of a configuration to True/False depending on the choice
        Each camera can have only one favorite configuration : if we set the favorite status to True for a configuration, the favorite status of the other configurations will be set to False
        A camera can have no favorite configuration
        Args :
            ip : str : IP of the camera
            config_name : str : Name of the configuration
        Return True if the favorite status is set, False otherwise"""
        assert self.camera_exist(ip), "La caméra n'existe pas dans la base de données."
        assert self.configuration_exist_in_camera(ip, config_name), "La configuration n'existe pas pour la caméra."

        if choice == True: #if choice == True we set the favorite status to True for the given configuration and to False for the other configurations
            config_trouve = False
            for camera in self.camera_data:
                if camera['ip'] == ip:
                    for config in camera['configurations']:
                        if config['name'] == config_name:
                            config['parameters']['favorite'] = True
                            config_trouve = True
                        else:
                            config['parameters']['favorite'] = False #set the favorite status of the other configurations to False (only one configuration can be favorite)
            self._save_config(self.camera_data, self.json_path)
            return config_trouve
        
        else: #if choice == False we set the favorite status to False for the given configuration
            for camera in self.camera_data:
                if camera['ip'] == ip:
                    for config in camera['configurations']:
                        if config['name'] == config_name:
                            config['parameters']['favorite'] = False
                            self._save_config(self.camera_data, self.json_path)
                            return True
            return False
        
    def get_configurations(self, ip:str)->List[Dict]:
        """Return the configurations of the camera
        Args :
            ip : str : IP of the camera
        Return the configurations of the camera, None if the camera does not exist"""
        assert self.camera_exist(ip), "La caméra n'existe pas dans la base de données."
        for camera in self.camera_data:
            if camera['ip'] == ip:
                return camera['configurations']
        return None


class StatusManager:
    """Use this class to manage the status of the app"""

    def __init__(self):
        self.json_path = "config\Settings\status.json"
        self.status_data = self._load_config(self.json_path)

    def _load_config(self, file):
        # Charger les données depuis le fichier JSON
        if os.path.exists(file):
            with open(file, 'r') as file:
                try:
                    return json.load(file)
                except json.JSONDecodeError:
                    print(f"Erreur lors du chargement du fichier {file}")
                    return {}
        else:
            print(f"Le fichier {file} n'existe pas.")
            return {}
        
    def _save_config(self,data, file):
        print("called _save_config")
        # Sauvegarder les données dans le fichier JSON
        with open(file, 'w') as file:
            json.dump(data, file, indent=4)

    
    def add_used_config(self, ip:str, config_name:str)->bool:
        """Add the camera current_used_camera in status.json, if the camera is not already in the current_used_camera"""
        for camera in self.status_data['current_used_config']:
            if camera['ip'] == ip and camera['config_name'] == config_name:
                print(f"La caméra {ip} est déjà utilisée.")
                return False
        #else we add the camera to the current_used_camera
        self.status_data['current_used_config'].append( {
            'ip': ip,
            'config_name': config_name,
        })
        self._save_config(self.status_data, self.json_path)
        return True
    
    def remove_used_config(self, ip:str, config_name:str)->bool:
        """Remove the camera current_used_camera in status.json, if the camera is in the current_used_camera"""
        for camera in self.status_data['current_used_config']:
            if camera['ip'] == ip and camera['config_name'] == config_name:
                self.status_data['current_used_config'].remove(camera)
                self._save_config(self.status_data, self.json_path)
                return True
        print(f"La caméra {ip} n'est pas utilisée.")
        return False
    
    def remove_all_used_config(self)->bool:
        """Remove all the cameras from the current_used_camera in status.json"""
        self.status_data['current_used_config'] = []
        self._save_config(self.status_data, self.json_path)
        return True
    def save_status(self):
        """Persist current status_data to status.json"""
        self._save_config(self.status_data, self.json_path)

    def update_current(self, project_path: str, experiment_name: str, config_json_path: str):
        """Update and save status.json based on current project/experiment/config.json."""
        # 基于现有内容做 update，避免把其它字段（如 last_project_settings）抹掉
        data = dict(self.status_data) if isinstance(self.status_data, dict) else {}

        data["current_project"] = {"path": project_path.replace("\\", "/"), "saved": True}
        data["current_experiment_name"] = experiment_name
        data["current_experiment"] = {"name": experiment_name}

        # 从 <project>/<experiment>/config.json 读取 camera_setup → 写入 current_used_config
        used = []
        try:
            with open(config_json_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for cam in cfg.get("camera_setup", []):
                used.append({
                    "ip": cam.get("ip", "") or cam.get("serial", ""),
                    "config_name": cam.get("config_name", "Default"),
                })
        except Exception as e:
            print("StatusManager.update_current: failed to read config.json:", e)

        # 确保 key 一定存在，避免别处读取时报 KeyError
        data["current_used_config"] = used or []

        # 覆盖内存并落盘
        self.status_data = data
        self.save_status()
    
    
    

   



# Exemple d'utilisation
if __name__ == "__main__":
    camera_manager = CameraManager()
    camera_manager.add_camera("Camera1", "10.1.1")
    camera_manager.add_camera("Camera2", "10.1.2")
    camera_manager.add_configuration("10.1.1", "Config1", "1920x1080", "30", "90", [[1,2,3],[4,5,6],[7,8,9]])
    camera_manager.add_configuration("10.1.1", "Config2", "1280x720", "60", "120", [[1,2,3],[4,5,6],[7,8,9]], {"key1": "value1", "key2": "value2"})
    # camera_manager.set_favorite("10.1.1", "Config1")


