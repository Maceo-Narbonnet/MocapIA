######################################################
### Comparaison Triangulation par paire / Globale  ###
######################################################


import numpy as np
import cv2
from scipy.optimize import least_squares

import h5py
import numpy as np

# # Chemin vers ton fichier HDF5
# hdf5_path = r"D:\Users\Etudiant\Documents\MOCAPIA5\mocapia_3\TestProject1\MoCap_Demo1\calibration\MoCap_Demo1_calibration_param.hdf5"
# points_cam = {"C3501325588979": np.array([[1022.1493682861328, 350.5553436279297], [1034.109245300293, 341.1583023071289], [1014.4608764648438, 336.8869171142578], [1042.6520080566406, 338.5954704284668], [992.2496795654297, 327.48987579345703], [1059.737548828125, 393.26918029785156], [947.8272895812988, 393.26918029785156], [1069.9888610839844, 478.6968536376953], [936.7216920852661, 471.00836181640625], [1055.4661560058594, 447.088623046875], [994.8125152587891, 447.088623046875], [1038.380630493164, 559.8531494140625], [976.8726997375488, 560.7074279785156], [1041.797737121582, 664.92919921875], [967.4756546020508, 669.2005615234375], [1047.7776718139648, 752.0653991699219], [960.6414413452148, 753.7739562988281], [1027.275032043457, 295.88163566589355], [1007.6266632080078, 370.2037124633789], [1007.6266632080078, 554.7274780273438], [1064.8632049560547, 791.3621215820312], [962.3499946594238, 799.9049072265625], [1077.6773529052734, 783.6736450195312], [942.7016296386719, 793.9249877929688], [1039.2349014282227, 767.4423828125], [964.0585479736328, 764.0252990722656]]), 
#               "C3501325621627": np.array([[977.9370269775391, 344.22371673583984], [989.4453353881836, 334.3594551086426], [969.7168045043945, 332.7154083251953], [1005.8857727050781, 331.0713653564453], [957.386474609375, 328.6053009033203], [1033.0124969482422, 387.79088592529297], [927.7936820983887, 385.32482147216797], [1031.3684539794922, 465.0609588623047], [905.5990867614746, 459.3068084716797], [991.9113998413086, 439.5782775878906], [940.1240119934082, 443.6883850097656], [1005.8857727050781, 545.6191101074219], [947.5222091674805, 544.7970886230469], [1017.3940811157227, 646.7278137207031], [945.8781661987305, 645.0837707519531], [1023.1482391357422, 729.7520446777344], [941.7680549621582, 725.6419372558594], [984.5131988525391, 290.79228496551514], [981.2251129150391, 365.5962905883789], [976.2929763793945, 543.1530456542969], [1022.3262100219727, 772.4971923828125], [926.14963722229, 765.9210205078125], [1041.2327117919922, 766.7430419921875], [912.1752624511719, 757.7008056640625], [1018.2161026000977, 742.0823974609375], [949.9882736206055, 743.7264404296875]]), 
#               "C3501325623877": np.array([[912.6486358642578, 332.15587615966797], [921.6728210449219, 321.12630462646484], [904.6271286010742, 316.1128692626953], [924.6808929443359, 317.1155548095703], [869.5330505371094, 302.07523345947266], [922.6755065917969, 381.28758239746094], [809.3717708587646, 377.27684020996094], [938.7185211181641, 474.5375671386719], [812.3798351287842, 468.5214385986328], [961.7803497314453, 445.4596252441406], [897.6083145141602, 440.44618225097656], [909.6405715942383, 566.7848815917969], [847.4739151000977, 567.7875671386719], [903.6244430541992, 691.1181945800781], [831.4309043884277, 700.1423645019531], [905.6298141479492, 782.36279296875], [822.4067153930664, 799.4085083007812], [912.6486358642578, 267.9838409423828], [872.5411148071289, 349.2015686035156], [878.557243347168, 562.7741088867188], [948.7454071044922, 818.4595336914062], [846.4712257385254, 850.5455932617188], [954.7615356445312, 807.4299926757812], [820.4013366699219, 851.5482788085938], [894.6002502441406, 798.4058227539062], [816.3905868530273, 812.4434204101562]]), 
#               "C3501350052453": np.array([[68.2141342163086, 321.4909210205078], [79.09333801269531, 309.62269592285156], [54.36786651611328, 308.6336784362793], [88.98352813720703, 313.57877349853516], [21.730239868164062, 311.60073471069336], [111.73096466064453, 378.85401916503906], [-2.006215810775757, 374.89794158935547], [143.37957763671875, 444.1292724609375], [-0.02817789651453495, 459.9535675048828], [136.45643615722656, 503.47039794921875], [16.785144805908203, 505.4484405517578], [102.82979583740234, 554.8993835449219], [25.686315536499023, 559.844482421875], [87.0054931640625, 691.3840026855469], [85.02745056152344, 687.4279174804688], [65.2470703125, 816.9893798828125], [136.45643615722656, 741.823974609375], [60.301979064941406, 267.0948829650879], [50.41178894042969, 358.0846252441406], [64.258056640625, 550.9432983398438], [123.59918975830078, 836.769775390625], [132.5003662109375, 829.8466186523438], [123.59918975830078, 828.8576049804688], [130.52232360839844, 826.8795776367188], [46.45571517944336, 843.6929321289062], [50.41178894042969, 715.1204528808594]])}
# with h5py.File(hdf5_path, "r") as f:
#     def print_structure(name, obj):
#         print(name, "->", type(obj))
#     f.visititems(print_structure)

# def read_projection_matrix(hdf5_path: str, cam_id: str) -> np.ndarray:
#     """
#     Lit la matrice de projection P (3x4) pour une caméra donnée depuis le fichier HDF5.
#     """
#     with h5py.File(hdf5_path, "r") as f:
#         P = f[f"extrinsics/{cam_id}/P"][:]   # dataset -> numpy array
#     return P


def triangulate_points_global(points_cam: dict, projection_matrices: dict = None) -> np.ndarray:
    """
    Global triangulation of 3D points from 2D points in multiple cameras  

    Args:
        points_cam: Dict {cam_ip: points_2d} where points_2d is a numpy array of shape (n,2)
        projection_matrices: Dict {cam_ip: P} where P is the projection matrix of shape (3x4).
                           If None, uses hardcoded matrices (legacy)

    Returns:
        points_3D: Numpy array of 3D triangulate points (shape: (n, 3)).
    """
    cam_ips = list(points_cam.keys())
    num_points = len(points_cam[cam_ips[0]])
    points_3D = np.full((num_points, 3), np.nan)
    
    # Utiliser les matrices fournies ou les matrices hardcoded (legacy)
    if projection_matrices is None:
        # Matrices hardcoded pour compatibilité legacy
        P1 = np.array([[ 2.75152574e+02, -6.30856094e+01,  1.29294773e+03,
            -2.90156491e+05],
           [-2.15656427e+02,  8.97512706e+02,  4.83652157e+02,
             2.35824540e+05],
           [-5.13269388e-01,  2.52439978e-04,  8.58227517e-01,
             5.96760992e+02]])      # ...979
        P2 = np.array([[-2.35204511e+02, -1.09625746e+01,  1.30229076e+03,
            -3.77239413e+05],
           [-3.75280813e+02,  9.14069131e+02,  3.31056032e+02,
             6.45456399e+05],
           [-7.99890342e-01,  2.99563252e-02,  5.99398081e-01,
             1.36932124e+03]])      # ...627
        P3 = np.array([[902. ,   0. , 968.4,   0. ],
           [  0. , 899.6, 526. ,   0. ],
           [  0. ,   0. ,   1. ,   0. ]])
                                    # ...877
        P4 = np.array([[-8.55567858e+02, -5.31624276e+01,  1.00825590e+03,
             1.14129902e+05],
           [-4.26349324e+02,  9.31191427e+02,  1.92522572e+02,
             9.44072415e+05],
           [-9.88213860e-01,  8.62654655e-02,  1.26458041e-01,
             2.08748127e+03]])       # ...453
        P_list = [P1,P2,P3,P4]
    else:
        # Utiliser les matrices du HDF5
        P_list = [projection_matrices[cam_ip] for cam_ip in cam_ips]

    for i in range(num_points):
        # Récupérer les points 2D pour toutes les caméras qui voient le point
        pts_2d_list = []
        for cam_ip in cam_ips:
            pts_2d = points_cam[cam_ip][i]
            if not np.any(np.isnan(pts_2d)):
                pts_2d_list.append(pts_2d)
        
        # Si au moins deux caméras voient le point, on peut trianguler
        if len(pts_2d_list) >= 2:
            # Étape 1: Initialisation avec DLT (deux premières caméras)
            pts1, pts2 = pts_2d_list[0], pts_2d_list[1]
            pts1 = np.array(pts1)
            pts2 = np.array(pts2)

            # Triangulation linéaire avec DLT (utilise les premières matrices de P_list)
            point_3d_homogeneous = cv2.triangulatePoints(P_list[0], P_list[1], pts1.reshape(1, 1, 2), pts2.reshape(1, 1, 2))
            point_3d = point_3d_homogeneous[:3].flatten() / point_3d_homogeneous[3, 0]  # Normalisation

            # Étape 2: Optimisation non-linéaire avec toutes les caméras
            def reprojection_error(x):
                """
                x: np.array shape (3,) -> point 3D
                P_list: list of 3x4 projection matrices
                pts_2d_list: list of 2D points in pixels
                """
                error = []
                X_h = np.append(x, 1)  # [X, Y, Z, 1]
                for P, pts_2d in zip(P_list, pts_2d_list):
                    proj_h = P @ X_h          # 3x1
                    proj_2d = proj_h[:2] / proj_h[2]  # division par w
                    error.extend(proj_2d - pts_2d)    # vecteur 2D
                print(error)
                return np.array(error)  # shape = 2*num_points
                # errors = []
                # for P, pts_2d in zip(P_list, pts_2d_list):
                #     # Projection du point 3D sur la caméra
                #     pts_2d_proj, _ = cv2.projectPoints(
                #         x.reshape(1, 3),
                #         np.zeros((3, 1)),  # Rotation nulle
                #         np.zeros((3, 1)),  # Translation nulle
                #         P[:, :3],          # Matrice intrinsèque (3x3)
                #         None
                #     )
                #     pts_2d_proj = pts_2d_proj.squeeze()
                #     errors.extend((pts_2d_proj - pts_2d).ravel())
                #     print(errors)
                # return np.array(errors)

            # Optimisation avec la méthode Levenberg-Marquardt
            result = least_squares(reprojection_error, point_3d, method='lm')
            points_3D[i, :] = result.x
    cam_idx = 0
    observed = np.array(points_cam[cam_ips[cam_idx]])
    projected = []
    import matplotlib.pyplot as plt
    for pt in points_3D:
        if not np.any(np.isnan(pt)):
            pts_proj, _ = cv2.projectPoints(pt.reshape(1,3), np.zeros((3,1)), np.zeros((3,1)), P_list[cam_idx][:,:3], None)
            projected.append(pts_proj.squeeze())

    projected = np.array(projected)

    # Affichage de validation désactivé (décommentez pour voir la validation de la triangulation)
    # plt.scatter(observed[:,0], observed[:,1], c='r', label='Observé')
    # plt.scatter(projected[:,0], projected[:,1], c='b', label='Projeté')
    # plt.legend()
    # plt.gca().invert_yaxis()
    # plt.show()
    return points_3D



