import pickle
import os
import glob
import cv2
import numpy as np
from tqdm import tqdm
from multiprocessing import Pool

def process_image(args):
    fname, objp, upscale_coeff, downscale_coeff, nCol, nRow, criteria, delete_image_error = args
    img = cv2.imread(fname)
    
    if upscale_coeff != 1:
        dim = (int(upscale_coeff * img.shape[1]), int(upscale_coeff * img.shape[0]))
        img_up_sampled = cv2.resize(img, dim, interpolation=cv2.INTER_AREA)
    else:
        img_up_sampled = img
        
    gray = cv2.cvtColor(img_up_sampled, cv2.COLOR_BGR2GRAY)

    ret, corners = cv2.findChessboardCorners(gray, (nCol, nRow), None,
                                             cv2.CALIB_CB_ADAPTIVE_THRESH +
                                             cv2.CALIB_CB_NORMALIZE_IMAGE +
                                             cv2.CALIB_CB_FAST_CHECK)

    if ret:
        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        objpoints = objp
        imgpoints = (corners2 / upscale_coeff) / downscale_coeff
        
        # Optionally save debug images
        # Draw corners
        cv2.drawChessboardCorners(img_up_sampled, (nCol, nRow), corners2, ret)
        return (objpoints, imgpoints, img_up_sampled)  # Return data for further processing
    else:
        print("aucun corner trouvé ", fname)
        if delete_image_error:
            os.remove(fname)
        return None

def detect_chessboard(image_path:str, view_scale_percent:int=50, upscale_coeff:float=2, nCol:int=11, nRow:int=10, downscale_coeff:float=1, debug_path:str=None, delete_image_error:bool=False):
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    objp = np.zeros((nCol * nRow, 3), np.float32)
    objp[:, :2] = np.mgrid[0:nCol, 0:nRow].T.reshape(-1, 2)

    images = sorted(glob.glob(image_path + r'\*.jpg'))

    if len(images) == 0:
        return 0

    # Prepare arguments for multiprocessing
    args_list = [(fname, objp, upscale_coeff, downscale_coeff, nCol, nRow, criteria, delete_image_error) for fname in images]


    with Pool() as pool:
        results = list(tqdm(pool.imap(process_image, args_list), total=len(args_list)))

    # Filter out None results
    objpoints = []
    imgpoints = []
    for result in results:
        if result is not None:
            objpoints.append(result[0])
            imgpoints.append(result[1])
            # Optionally save debug images if needed
            if debug_path is not None:
                cv2.imwrite(os.path.join(debug_path, "chessboard-" + os.path.basename(result[2])), result[2])

    cv2.destroyAllWindows()
    print("Fin de la recherche des damiers")
    return (objpoints, imgpoints)





def get_camera_parameters_chessboard(image_path:str, nCol:int = 10, nRow:int = 7, view_scale_percent:int=50, upscale_coeff:float = 2,  downscale_coeff:float=1):
    """
    Detects the checkerboard on all images in the folder specified in image_path, then calculates the camera's intrinsic parameters. Returns the matrix K, the list of distortion coefficients, the coordinates of the checkerboard corners in space, and the coordinates of the checkerboard points on the images.
    image_path: folder containing the calibration images
    view_scale_percent: scale (in percentage) at which to display checkerboard previews during checkerboard detection on the images
    upscale_coeff: coefficient by which to enlarge the image for checkerboard detection. A coefficient of 1 will not change the image, a coefficient of 2 will double the image size by bilinear interpolation before detecting the checkerboard, a coefficient of 3 will triple the size etc.
    nCol: number of columns of the checkerboard. Note that this is the number of corners, not the number of squares (which is equal to nCol + 1).
    nRow: number of rows of the checkerboard. Note that this is the number of corners, not the number of squares (which is equal to nRow + 1).
    downscale_coeff: coefficient by which to divide the resolution for intrinsic parameters calculation. For example, if downscale coeff = 2 and the images are originally in 720px by 1280px, then the intrinsic parameters will be calculated to be used at a resolution of 360px by 640px.
    """
    images = glob.glob(image_path + r'\*.jpg')
    if len(images) != 0:
        img = img = cv2.imread(images[0])
        origin_gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        width = int(origin_gray.shape[1] / downscale_coeff)
        height = int(origin_gray.shape[0] / downscale_coeff)

        # # dsize
        dsize = (width, height)

        # # resize image
        target_gray = cv2.resize(origin_gray, dsize)
    objpoints, imgpoints = detect_chessboard(image_path, view_scale_percent=view_scale_percent, upscale_coeff=upscale_coeff, nCol=nCol, nRow=nRow, downscale_coeff=downscale_coeff)
    ret, mtx, dist, _rvecs, _tvecs = cv2.calibrateCamera(objpoints, imgpoints, target_gray.shape[::-1], None, None)
    print("Intrinsic parameters : ")
    print(f"Matrix K : {mtx}")


    return mtx, dist, objpoints, imgpoints






