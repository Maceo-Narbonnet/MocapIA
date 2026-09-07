import cv2

def get_clicked_points(image_path):
    """
    Fonction qui permet de cliquer sur une image et de recuperer les coordonnees des points cliques en pixels.

    :param image_path: Chemin vers l'image sur laquelle cliquer.
    :return: Liste de tuples contenant les coordonnees (x, y) des points cliques.
    """
    clicked_points = []

    def on_mouse_click(event, x, y, flags, param):
        "Callback pour gerer les clics de souris."
        if event == cv2.EVENT_LBUTTONDOWN:  # Si clic gauche
            clicked_points.append((x, y))
            print(f"Point clique : ({x}, {y})")

    # Charger l'image
    image = cv2.imread(image_path)
    if image is None:
        print("Erreur : Impossible de charger l'image.")
        return []

    # Creer une fenêtre et enregistrer les clics
    cv2.namedWindow("Cliquez sur les points")
    cv2.setMouseCallback("Cliquez sur les points", on_mouse_click)

    print("Cliquez sur les points de l'image. Appuyez sur 'q' pour terminer.")
    while True:
        temp_image = image.copy()
        # Dessiner les points cliques sur l'image temporaire
        for pt in clicked_points:
            cv2.circle(temp_image, pt, radius=5, color=(0, 255, 0), thickness=-1)

        cv2.imshow("Cliquez sur les points", temp_image)
        key = cv2.waitKey(1)

        if key == ord('q'):  # Quitter en appuyant sur 'q'
            break

    cv2.destroyAllWindows()
    print("Points cliques :", clicked_points)
    return clicked_points

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def plot_points_3d(points, point_labels=None, limits=None, point_colors=None):
    """
    Trace une liste de points dans un environnement 3D.

    Arguments :
    - points : list of list/tuple/np.ndarray, liste de points (chaque point est [x, y, z]).
    - point_labels : list of str, etiquettes pour les points (facultatif, doit être de la même longueur que points).
    - limits : dict, limites des axes sous la forme {'x': [min, max], 'y': [min, max], 'z': [min, max]}.
    - point_colors : list of str, couleurs pour chaque point (facultatif, doit être de la même longueur que points).
    """
    # Convertir la liste de points en un tableau numpy pour la manipulation
    fig = plt.figure(figsize=(10, 8))
    points = np.array(points)

    # Verifier que les points sont dans un format correct
    if points.shape[1] != 3:
        raise ValueError("Chaque point doit avoir exactement 3 coordonnees : [x, y, z]")

    # Verifier si le nombre de couleurs est valide
    if point_colors is not None:
        if len(point_colors) != len(points):
            raise ValueError("Le nombre de couleurs doit correspondre au nombre de points")

    # Initialiser la figure 3D
    ax = fig.add_subplot(111, projection='3d')

    # Tracer les points avec les couleurs specifiees
    if point_colors is None:
        # Si aucune couleur n'est specifiee, utiliser la couleur par defaut (bleu)
        ax.scatter(points[:, 0], points[:, 1], points[:, 2], color='blue', s=50)
    else:
        # Sinon, utiliser les couleurs specifiees pour chaque point
        ax.scatter(points[:, 0], points[:, 1], points[:, 2], color=point_colors, s=50)

    # Ajouter les etiquettes pour chaque point (facultatif)
    if point_labels is not None:
        if len(point_labels) != len(points):
            raise ValueError("Le nombre d'etiquettes doit correspondre au nombre de points")
        for point, label in zip(points, point_labels):
            ax.text(point[0], point[1], point[2], label, color='red')

    # Configurer les limites des axes
    if limits:
        ax.set_xlim(limits.get('x', [points[:, 0].min() - 1, points[:, 0].max() + 1]))
        ax.set_ylim(limits.get('y', [points[:, 1].min() - 1, points[:, 1].max() + 1]))
        ax.set_zlim(limits.get('z', [points[:, 2].min() - 1, points[:, 2].max() + 1]))
    else:
        ax.set_xlim([points[:, 0].min() - 1, points[:, 0].max() + 1])
        ax.set_ylim([points[:, 1].min() - 1, points[:, 1].max() + 1])
        ax.set_zlim([points[:, 2].min() - 1, points[:, 2].max() + 1])

    # Ajouter des etiquettes aux axes
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_zlabel('Z (mm)')
    plt.title("Positions baguettes et cameras avec Vicon")

    # Afficher la grille
    ax.grid(True)

    # Ajouter une legende
    ax.legend()

    # Afficher le graphe
    plt.show()


def dist_eucl(pt1, pt2):
    return np.linalg.norm(pt1 - pt2)


def change_ref(tab: np.ndarray):
    """
    Change the reference of the points in `tab` to a new reference defined 
    by the first three points of `tab`.
    
    Parameters:
        tab (np.ndarray): Array of points (N, 3) in the original reference frame.
                          The first three points (P1, P2, P3) define the new reference.

    Returns:
        tuple:
            - points_in_new_ref (np.ndarray): Transformed points in the new reference (N, 3).
            - R (np.ndarray): Rotation matrix (3, 3) defining the new reference orientation.
            - T (np.ndarray): Translation vector (3,) defining the new reference origin.
    """
    # Points defining the new reference
    P1 = tab[0]
    P2 = tab[1]
    P3 = tab[2]
    
    # Calculate the new x' axis
    x_prime = P2 - P1
    x_prime /= np.linalg.norm(x_prime)

    # Calculate the new y' axis
    y_temp = P3 - P1
    y_prime = y_temp - np.dot(y_temp, x_prime) * x_prime
    y_prime /= np.linalg.norm(y_prime)

    # Calculate the new z' axis
    z_prime = np.cross(x_prime, y_prime)
    z_prime /= np.linalg.norm(z_prime)

    # Construct the rotation matrix
    R = np.column_stack((x_prime, y_prime, z_prime))
    
    # Translation vector (origin of new reference)
    T = P1

    # Transform all points to the new reference frame
    points_in_new_ref = np.dot(tab - T, R)

    return points_in_new_ref, R, T


def plot_3d_points_with_normal(points):
    """
    Trace les points 3D et la direction du vecteur normal au plan forme par les trois premiers points.

    Args:
        points (numpy.ndarray): Tableau NumPy de forme (N, 3) contenant les points 3D.
    """
    if points.shape[0] < 3:
        raise ValueError("Au moins trois points sont necessaires pour definir un plan.")

    # Les trois premiers points
    p1, p2, p3 = points[:3]

    # Calcul du vecteur normal
    v1 = p2 - p1
    v2 = p3 - p1
    normal = np.cross(v1, v2)
    normal = normal / np.linalg.norm(normal)  # Normalisation du vecteur normal

    # Coordonnees du centre du triangle pour tracer le vecteur normal
    center = (p1 + p2 + p3) / 3

    # Creation de la figure 3D
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Tracer les points
    ax.scatter(points[:, 0], points[:, 1], points[:, 2], color='blue', label='Points')

    # Tracer le vecteur normal
    ax.quiver(
        center[0], center[1], center[2],  # Origine du vecteur
        normal[0], normal[1], normal[2],  # Composantes du vecteur
        color='red', length=100, normalize=True, label='Vecteur normal'
    )

    # Configuration de la figure
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.legend()
    ax.set_title("Points 3D et vecteur normal")

    plt.show()

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def find_normal(pt1, pt2, pt3, sens:bool=True, norm:int=10):
    """
    Trouve le vecteur normal au plan defini par les trois points donnes.

    Parameters:
        pt1, pt2, pt3: tuples ou listes de coordonnees (x, y, z)
        sens: booleen pour inverser le sens de la normale
        norm: longueur de la normale à afficher
    """
    # Convertir les points en tableaux numpy
    p1 = np.array(pt1)
    p2 = np.array(pt2)
    p3 = np.array(pt3)

    # Calculer deux vecteurs du plan
    v1 = p2 - p1
    v2 = p3 - p1

    # Calculer la normale au plan (produit vectoriel)
    normal = np.cross(v1, v2)
    normal_unit = normal / np.linalg.norm(normal)*norm
    if sens: # Inverser le sens de la normale
        normal_unit = -normal_unit

    return normal_unit


    ax.quiver(p1[0], p1[1], p1[2], normal_unit[0], normal_unit[1], normal_unit[2],
              length=1.0, color='green', label='Normale')

    # Ajouter des etiquettes et une legende
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.legend()

    # Afficher le graphique
    plt.show()

def plot_exp(O, X, Y, cams, others_points):
    """
    Trace des points dans un espace 3D, pour les camera trace aussi leur orientation., pour les points 0,X,Y trace aussi un repère orthonorme.

    Parameters:
        O, X, Y: tuples ou listes de coordonnees (x, y, z) pour les points O, X et Y."""

    # Initialiser la figure
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    # Tracer les points O, X et Y
    ax.scatter(*O, color='red', s=50)
    ax.scatter(*X, color='green', s=50)
    ax.scatter(*Y, color='blue', s=50)
    normal = find_normal(O, X, Y, norm=1, sens=False)
    ax.quiver(O[0], O[1], O[2], normal[0], normal[1], normal[2], color='red', length=500.0)
    ax.quiver(O[0], O[1], O[2], X[0]-O[0], X[1]-O[1], X[2]-O[2], color='green', length=3.5)
    ax.quiver(O[0], O[1], O[2], Y[0]-O[0], Y[1]-O[1], Y[2]-O[2], color='blue', length=4)
    ax.text(O[0], O[1], O[2], 'O', color='black')
    ax.text(X[0], X[1], X[2], 'X', color='black')
    ax.text(Y[0], Y[1], Y[2], 'Y', color='black')


    # Tracer les points des cameras
    colors = ['r', 'g', 'b', 'purple']
    for i, cam in enumerate(cams):
        for point in cam:
            ax.scatter(point[0], point[1], point[2], color=colors[i], s=50)
        point = cam[0]
        ax.text(point[0], point[1], point[2], f'Cam {i+1}', color="black")
        normal = find_normal(cam[0], cam[1], cam[2], norm=500)
        ax.quiver(point[0], point[1], point[2], normal[0], normal[1], normal[2], color=colors[i], length=1.0)
    
    # Tracer les autres points
    for i, point in enumerate(others_points):
        ax.scatter(point[0], point[1], point[2], color='black', s=50)

    # Ajouter des etiquettes et une legende
    plt.title("Positions baguettes et cameras pour Vicon et pour les cameras GoPro")
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.legend()

    # Afficher le graphique
    plt.show()


import math

def calculate_angle(origin, point_b, point_c):
    """
    Calcule l'angle entre les vecteurs formes par trois points en 3D : origine, point_b et point_c.

    :param origin: Tuple (x1, y1, z1) representant le point d'origine
    :param point_b: Tuple (x2, y2, z2) representant le deuxième point
    :param point_c: Tuple (x3, y3, z3) representant le troisième point
    :return: Angle en degres entre les vecteurs origine->point_b et origine->point_c
    """
    # Coordonnees des vecteurs
    x1, y1, z1 = origin
    x2, y2, z2 = point_b
    x3, y3, z3 = point_c

    # Vecteurs
    vector_ab = (x2 - x1, y2 - y1, z2 - z1)
    vector_ac = (x3 - x1, y3 - y1, z3 - z1)

    # Produit scalaire des deux vecteurs
    dot_product = (vector_ab[0] * vector_ac[0]) + (vector_ab[1] * vector_ac[1]) + (vector_ab[2] * vector_ac[2])

    # Normes des deux vecteurs
    norm_ab = math.sqrt(vector_ab[0]**2 + vector_ab[1]**2 + vector_ab[2]**2)
    norm_ac = math.sqrt(vector_ac[0]**2 + vector_ac[1]**2 + vector_ac[2]**2)

    # Calcul du cosinus de l'angle
    if norm_ab == 0 or norm_ac == 0:
        raise ValueError("Les vecteurs ne doivent pas être nuls.")

    cos_theta = dot_product / (norm_ab * norm_ac)

    # Gerer les erreurs d'arrondi qui pourraient placer cos_theta legèrement hors de [-1, 1]
    cos_theta = max(-1, min(1, cos_theta))

    # Calcul de l'angle en radians puis en degres
    angle_rad = math.acos(cos_theta)
    angle_deg = math.degrees(angle_rad)

    return angle_deg

# Exemple d'utilisation
# if __name__ == "__main__":
    # print(get_clicked_points(r"D:\Users\Etudiant\Documents\MoCapIA3\MocapIA_3\TestProject\ViconProject\calibration\tmp\C3501350052453_tmp\frame_0078.jpg"))
    # print(get_clicked_points(r"D:\Users\Etudiant\Documents\MoCapIA3\MocapIA_3\TestProject\ViconProject\calibration\tmp\C3501325621627_tmp\frame_0078.jpg"))
    # print(get_clicked_points(r"D:\Users\Etudiant\Documents\MoCapIA3\MocapIA_3\TestProject\ViconProject\calibration\tmp\C3501325588979_tmp\frame_0078.jpg"))
    # print(get_clicked_points(r"D:\Users\Etudiant\Documents\MoCapIA3\MocapIA_3\TestProject\ViconProject\calibration\tmp\C3501325623877_tmp\frame_0078.jpg"))





#PT53 = [(1206, 864), (1243, 855), (1185, 849), (1165, 835), (1187, 869), (837, 527), (969, 519), (837, 661), (966, 648), (1076, 406), (1092, 406), (1086, 412), (1041, 431), (1109, 429), (1011, 477), (1119, 480), (1035, 512), (1109, 526), (1043, 532), (1104, 534), (1052, 617), (1104, 606), (1050, 685), (1093, 653), (1052, 717), (1101, 687)]
#PT27 = [(1095, 850), (1119, 829), (1062, 838), (1030, 827), (1082, 861), (469, 504), (643, 485), (482, 688), (650, 646), (820, 340), (836, 339), (832, 349), (768, 372), (847, 368), (729, 429), (858, 431), (772, 473), (856, 483), (779, 493), (848, 491), (800, 592), (851, 580), (800, 676), (825, 633), (813, 709), (838, 667)]
#PT79 = [(775, 845), (814, 871), (804, 830), (831, 815), (756, 834), (1121, 459), (1272, 491), (1095, 603), (1229, 648), (1209, 340), (1229, 343), (1217, 352), (1197, 376), (1283, 389), (1184, 429), (1291, 470), (1165, 472), (1242, 525), (1170, 503), (1236, 523), (1145, 598), (1217, 643), (1132, 689), (1255, 699), (1090, 721), (1234, 743)]
#PT77 = [(742, 915), (789, 926), (761, 895), (778, 876), (720, 909), (913, 508), (1048, 525), (905, 641), (1037, 661), (1009, 407), (1025, 407), (1017, 416), (1002, 433), (1071, 438), (988, 480), (1085, 507), (984, 520), (1054, 553), (990, 546), (1056, 559), (982, 641), (1048, 654), (980, 714), (1079, 700), (955, 744), (1064, 738)]