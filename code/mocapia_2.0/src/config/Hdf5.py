import h5py
import numpy as np
import os 
from typing import Tuple, List, Dict

# Type aliases for camera calibration data (intrinsics)
MtxMatrix = np.ndarray
DistMatrix = Tuple[float, float, float, float, float]

# Type aliases for camera calibration data (extrinsics)
ProjectionMatrix = np.ndarray
RotationMatrix = np.ndarray
TranslationMatrix = np.ndarray
RectifiedRotationMatrix = np.ndarray
EssentialMatrix = np.ndarray
FundamentalMatrix = np.ndarray
QMatrix = np.ndarray
Roi = Tuple[int, int, int, int]

# Type aliases for detections data (2D points)
Point2DMatrix = np.ndarray
def hdf5_structure(file_path:str) -> None:
    """
    Print the structure of an hdf5 file
    """
    with h5py.File(file_path, "r") as f:
        def print_structure(name, obj):
            print(name, "->", type(obj))
        f.visititems(print_structure)

class Hdf5_Calib:
    """This class implements a hdf5 file reader and writer for hdf5 files used to store calibration data
    the file structure is as follows:
    intrinsics (group)
        cam_id1 (group)
            mtx (dataset): camera matrix
            dist (dataset): distortion coefficients
        ...
    extrinsics (group)
        cam_id1-cam_id2 (group)
            P1 (dataset): projection matrix for camera 1
            P2 (dataset): projection matrix for camera 2
            R1 (dataset): rectified rotation matrix for camera 1
            R2 (dataset): rectified rotation matrix for camera 2
            and other optional data (T, R, E, F, Q, roi1, roi2)
        ...
    """

    def __init__(self, file_path:str, mode="a"):
        """file_path: path to the hdf5 file, the file will be created if it does not exist"""

        self.file_path = file_path
        self.mode = mode
        self.file = None
        self.open_file()


    #! ------------ file management ------------ !#
    def open_file(self):
        """open the hdf5 file"""
        try:
            self.file = h5py.File(self.file_path, self.mode)
        except Exception as e:
            raise ValueError(f"Error opening file {self.file_path}: {e}")
        
    def close_file(self):
        """close the hdf5 file (used in the destructor)"""
        if self.file is not None : self.file.close()

    def __del__(self):
        """destructor"""
        self.close_file()

    def create_dataset(self, group, name, data):
        """Create a dataset in the hdf5 file"""
        if name in group:
            del group[name]
        group.create_dataset(name, data=data)


    #! ------------ intrinsics calibrations data ------------ !#
    def write_intrinsics(self, camera_id:str, intrinsics:Tuple[MtxMatrix, DistMatrix]) -> None:
        """Write mtx and dist to the hdf5 file, in the corresponding camera_id group"""
        group = self.file.require_group(f"intrinsics/{camera_id}")
        self.create_dataset(group, "mtx", intrinsics[0])
        self.create_dataset(group, "dist", intrinsics[1])

    def read_intrinsics(self, camera_id:str) -> Tuple[MtxMatrix, DistMatrix]:
        """Read mtx and dist from the hdf5 file, in the corresponding camera_id group"""
        if camera_id not in self.file["intrinsics"]:
            raise ValueError(f"Camera {camera_id} not found in the file")
        group = self.file.require_group(f"intrinsics/{camera_id}")
        print(group["mtx"])
        mtx = np.array(group["mtx"])
        dist = np.array(group["dist"])
        return mtx, dist
    
    #! ------------ extrinsics calibrations data ------------ !#
    def write_extrinsics_matrix(self, cam_id, T:TranslationMatrix, R:RotationMatrix,
                                E:EssentialMatrix = None, F:FundamentalMatrix = None,
                                Q:QMatrix = None, roi1:Roi=None, roi2:Roi=None
                                ) -> None:
        """Args:
            cam1_id: camera 1 id
            cam2_id: camera 2 id
            T: translation matrix for the couple of cameras (Rij)
            R: rotation matrix for the couple of cameras (Tij)
            optional:
                E: essential matrix
                F: fundamental matrix
                Q: Q matrix
                roi: region of interest
        """
        group = self.file.require_group(f"extrinsics/{cam_id}")
        #add the data to the group
        self.create_dataset(group, "T", T)
        self.create_dataset(group, "R", R)

        if E is not None:
            self.create_dataset(group, "E", E)
        if F is not None:
            self.create_dataset(group, "F", F)
        if Q is not None:
            self.create_dataset(group, "Q", Q)
        if roi1 is not None and roi2 is not None:
            self.create_dataset(group, "roi1", roi1)
            self.create_dataset(group, "roi2", roi2)


    def write_extrinsics_projection(self,cam_id:str, P:ProjectionMatrix)-> None:
        """Write projection matrix to the hdf5 file, in the corresponding cam_id group"""
        group = self.file.require_group(f"extrinsics/{cam_id}")
        self.create_dataset(group, f"P", P)

    def write_ref(self, ref_cam_id:str) -> None:
        """Write the reference camera id to the hdf5 file, as a metadata"""
        self.file.attrs["ref_cam_id"] = ref_cam_id

    def read_ref(self) -> str:
        """Read the reference camera id from the hdf5 file"""
        return self.file.attrs["ref_cam_id"]


    def read_extrinsics(self, cam_id) -> Dict[str, np.ndarray]:
        
        extrinsics_data = {}
        cam_group = self.file.require_group(f"extrinsics/{cam_id}")

        

        # read obligatory matrices
        extrinsics_data["T"] = cam_group["T"][:]
        extrinsics_data["R"] = cam_group["R"][:]

        # read optional matrices
        if "E" in cam_group:
            extrinsics_data["E"] = cam_group["E"][:]
        if "F" in cam_group:
            extrinsics_data["F"] = cam_group["F"][:]
        if "Q" in cam_group:
            extrinsics_data["Q"] = cam_group["Q"][:]
        if "roi1" in cam_group and "roi2" in cam_group:
            extrinsics_data["roi1"] = cam_group["roi1"][:]
            extrinsics_data["roi2"] = cam_group["roi2"][:]
        if "P" in cam_group:
            extrinsics_data["P"] = cam_group["P"][:]

        return extrinsics_data



class Hdf5_Detections:
    """This class implements a hdf5 file reader and writer for hdf5 files used to store detections data for each folder and each images
    The detections data are stored in the following format:
    camera_ip : str (group)
        image_indice : str (dataset) : detections for image1 type ndarray with shape (N, 2)
        image_indice : str (dataset) : detections for image2
        ...
    """
    def __init__(self, file_path:str, mode="a"):
        """file_path: path to the hdf5 file, the file will be created if it does not exist"""

        self.file_path = file_path
        self.mode = mode
        self.file = None
        self.open_file()


    #! ------------ file management ------------ !#
    def open_file(self):
        """open the hdf5 file"""
        try:
            self.file = h5py.File(self.file_path, self.mode)
        except Exception as e:
            raise ValueError(f"Error opening file {self.file_path}: {e}")
        
    def close_file(self):
        """close the hdf5 file (used in the destructor)"""
        if self.file is not None : self.file.close()

    def __del__(self):
        """destructor"""
        self.close_file()

    def create_dataset(self, group, name, data):
        """Create a dataset in the hdf5 file"""
        if name in group:
            del group[name]
        group.create_dataset(name, data=data)

    #! ------------ detections data ------------ !#

    def write_detections(self, folder:str, image:str, detections:Point2DMatrix) -> None:
        """Write detections to the hdf5 file, in the corresponding folder group"""
        group = self.file.require_group(folder)
        self.create_dataset(group, image, detections)
    
    def ensure_camera_groups(self, camera_ids):
        """Ensure that HDF5 groups for each camera id exist, even if empty."""
        for cam_id in camera_ids:
            self.file.require_group(str(cam_id))

    
    def is_detected(self, folder:str, image:str) -> bool:
        """Check if the image is detected in the hdf5 file"""
        if folder not in self.file:
            return False
        group = self.file[folder]
        return image in group
    
    def read_detections(self, folder:str, image:str) -> Point2DMatrix:
        """Read detections from the hdf5 file, in the corresponding folder group"""
        if not self.is_detected(folder, image):
            raise ValueError(f"Image {image} not found in the file")
        
        group = self.file[folder]
        return np.array(group[image])
    
    def get_detection_dictionnaries(self, folder_1:str, folder_2:str) -> Dict[str, bool]:
        """Return one dictionary containing (image_name:str : detected:bool),
        the detected images are those that are present in both folders"""
        if folder_1 not in self.file or folder_2 not in self.file:
            raise ValueError(f"Folder {folder_1} or {folder_2} not found in the file")
        
        detections = {}
        group_1 = self.file[folder_1]
        group_2 = self.file[folder_2]
        for image in group_1:
            detections[image] = image in group_2
        return detections