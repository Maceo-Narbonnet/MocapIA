from PyQt5.QtCore import pyqtSignal, QObject
from Camera.GoProCam import GoProCam
from Pose_Estimation.toolbox_calibration import get_camera_parameters_chessboard
from Pose_Estimation.video_utils import extract_images_from_video, clear_folder
from config.Config_Manager import ConfigManager, CameraManager
import os
class IntrinsicCalibrationWorker(QObject):
    """Worker to connect for intrinsic calibrations"""
    
    finished = pyqtSignal()
    # progress_label = pyqtSignal(str)
    progress_bar = pyqtSignal(int)

    def __init__(self, camera_ip,config_name, camera_resolution, camera_fps, camera_fov, camera_stream):
        super().__init__()
        self.camera_ip = camera_ip
        self.camera_resolution = camera_resolution
        self.camera_fps = camera_fps
        self.camera_fov = camera_fov
        self.camera_stream = camera_stream
        self.config_name = config_name

        #calibrations statics parameters from the user preferences
        config_manager = ConfigManager()
        config_calib = config_manager.config_data["intrinsinc_calibration"]
        self.tmp_calib_folder = config_calib["tmp_calib_folder"]
        self.view_scale_percent = config_calib["view_scale_percent"]
        self.upscale_coeff = config_calib["upscale_coeff"]
        self.nCol = config_calib["nCol"]
        self.nRow = config_calib["nRow"]
        self.downscale_coeff = config_calib["downscale_coeff"]
        self.nb_images = config_calib["nb_images"]
        self.duration = config_calib["video_time"]

    def run(self):
        """Run the intrinsic calibration"""
        try:
            gopro = GoProCam(self.camera_ip)
            if gopro.connect():
                self.camera_stream.stop_stream()
                gopro.enable_wired_control()
                gopro.set_configuration_parameters(self.camera_resolution, self.camera_fps, self.camera_fov)
                gopro.take_and_download_video(self.duration, self.tmp_calib_folder)
                self.camera_stream.start_stream(self.camera_ip)

                video_path = os.path.join(self.tmp_calib_folder, os.listdir(self.tmp_calib_folder)[0])
                # Extract images from the video
                extract_images_from_video(video_path, self.tmp_calib_folder, number=self.nb_images, image_format="jpg")
                clear_folder(self.tmp_calib_folder, format="mp4") #supress the video from the file
                mtx, dist, objpoints, imgpoints = get_camera_parameters_chessboard(self.tmp_calib_folder,self.view_scale_percent,self.upscale_coeff, self.nCol, self.nRow, self.downscale_coeff)
                clear_folder(self.tmp_calib_folder) #supress the images from the file
                # Save the calibration parameters for the configuration selected by the user

                mtx = mtx.tolist()
                dist = dist.tolist()
                objpoints = [obj.tolist() for obj in objpoints]
                imgpoints = [img.tolist() for img in imgpoints]
                print("MTX :",mtx)
                print("Dist : ", dist)
                camera_manager = CameraManager()
                camera_manager.add_intrinsic_calib_to_camera_configuration(self.camera_ip, self.config_name, mtx, dist, objpoints, imgpoints)

        except Exception as e:
            raise ValueError(f"Error during intrinsic calibration : {e}")
        finally:
            self.finished.emit()

