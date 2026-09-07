import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import pandas as pd
import logging
from pathlib import Path

def read_csv(file_path: str) -> pd.DataFrame:
    """Read a CSV from deeplabcut and return a pandas DataFrame."""
    assert isinstance(file_path, str), "File path must be a string."
    data = pd.read_csv(file_path, header= [1, 2], skiprows=[0])
    return data

def read_csv_data(file_path):
    """
    Lit un fichier CSV de coordonnées 3D avec un en-tête spécifique sur 5 lignes
    et le formate pour le script de filtrage.

    Args:
        file_path (str): Le chemin vers le fichier CSV.

    Returns:
        tuple: Contient Q_coords, frames_col, time_col, markers, header_lines.
               - Q_coords (DataFrame): Uniquement les colonnes de coordonnées.
               - frames_col (Series): La colonne des numéros d'images.
               - time_col (Series): La colonne de temps (calculée pour les plots).
               - markers (list): La liste des noms des points clés (ex: 'Nose').
               - header_lines (list): Les 5 lignes d'en-tête originales.
    """
    # 1. Lire les 5 premières lignes pour l'en-tête
    try:
        with open(file_path, 'r') as f:
            header_lines = [next(f) for _ in range(5)]
    except (IOError, StopIteration):
        raise ValueError(f"Impossible de lire l'en-tête de 5 lignes du fichier {file_path}.")

    # 2. Extraire la fréquence d'images (frame rate) depuis la 2ème ligne
    try:
        frame_rate = int(header_lines[1].strip())
        if frame_rate <= 0: raise ValueError
    except (ValueError, IndexError):
        # Si la lecture échoue, on utilise une valeur par défaut sûre
        frame_rate = 30
        logging.warning(f"Impossible de lire la fréquence d'images depuis le CSV. Utilisation de la valeur par défaut : {frame_rate} Hz.")
        
    # 3. Extraire les noms des marqueurs depuis la 3ème ligne
    # On sépare par la virgule et on ne garde que les éléments non vides
    markers = [name for name in header_lines[2].strip().split(',') if name]
    
    # 4. Construire la liste complète des noms de colonnes
    column_names = ['Frames']
    for marker in markers:
        column_names.extend([f'{marker}_x', f'{marker}_y', f'{marker}_z'])

    # 5. Lire les données numériques en sautant l'en-tête
    df = pd.read_csv(file_path, skiprows=5, header=None)
    
    # S'assurer que le nombre de colonnes lues correspond aux noms construits
    # (utile si des virgules en fin de ligne créent des colonnes vides)
    if len(df.columns) > len(column_names):
        df = df.iloc[:, :len(column_names)]
    
    df.columns = column_names

    # 6. Séparer les colonnes en groupes
    frames_col = df['Frames']
    coord_cols = [col for col in df.columns if col != 'Frames']
    Q_coords = df[coord_cols]
    
    # 7. Créer la colonne de temps (utile pour les graphiques)
    # Time = (Frame_Number - First_Frame_Number) / Frame_Rate
    first_frame = frames_col.iloc[0]
    time_col = (frames_col - first_frame) / frame_rate
    time_col.name = "Time"

    # 8. Retourner les données formatées, y compris l'en-tête original
    return Q_coords, frames_col, time_col, markers, header_lines



def get_coordinates(data: pd.DataFrame, body_part: int) -> np.ndarray:
    """Extract the x and y coordinates of a body part from a pandas DataFrame.
    Args:
        data : A pandas DataFrame containing x and y coordinates.
        body_part : Index of the body part to extract.
    Returns:
        A numpy array containing the x and y coordinates of the specified body part. shape : (n, 2)
    """
    assert isinstance(data, pd.DataFrame), "Data must be a pandas DataFrame."
    assert body_part >= 0, "Body part index must be greater than or equal to 0."
    assert body_part < data["x"].shape[1], "Body part index out of range."

    x = data["x"].iloc[:, body_part].values
    y = data["y"].iloc[:, body_part].values
    coordinates = np.array([x, y]).T
    return coordinates

def plot_coordinates(coord : np.ndarray):
    """Plot the x and y coordinates of a body part."""
    assert isinstance(coord, np.ndarray), "Coordinates must be a numpy array."
    assert coord.shape[1] == 2, "Coordinates must have 2 columns."

    # Remove rows with zeros
    coord = coord[(coord[:, 0] > 10) | (coord[:, 1] > 10)]
    x = coord[:, 0]
    y = coord[:, 1]
    plt.plot(x, y, "bo-")
    plt.xlabel("x")
    plt.ylabel("y")
    plt.title("Body Part Coordinates")
    plt.show()



def plot_coordinates_animation(coord: np.ndarray, fps: int = 20):
    """Plot an animated sequence of the x and y coordinates of a body part at the specified FPS."""
    assert isinstance(coord, np.ndarray), "Coordinates must be a numpy array."
    assert coord.shape[1] == 2, "Coordinates must have 2 columns."
    
    # Remove rows with coordinates close to zero
    coord = coord[(coord[:, 0] > 10) | (coord[:, 1] > 10)]
    x = coord[:, 0]
    y = coord[:, 1]
    
    # Set up the figure and axis
    fig, ax = plt.subplots()
    ax.set_xlim(min(x) - 10, max(x) + 10)
    ax.set_ylim(min(y) - 10, max(y) + 10)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("Body Part Coordinates - Animated")
    
    # Initialize a line object with no data
    line, = ax.plot([], [], "r+")

    # Update function for animation
    def update(frame):
        # Update the line with data up to the current frame
        line.set_data(x[:frame + 1], y[:frame + 1])
        return line,

    # Create the animation
    frames = len(x)  # Number of frames (one per point)
    interval = 1000 / fps  # Interval between frames in milliseconds
    anim = FuncAnimation(fig, update, frames=frames, interval=interval, blit=True)

    # Show the animation
    plt.show()

def eucl_dist(coords1:np.ndarray, coords2:np.ndarray) -> np.ndarray:
    """Compute the Euclidean distance between two sets of coordinates."""

    return np.sqrt((coords1[:,0] - coords2[:,0])**2 + (coords1[:,1] - coords2[:,1])**2)

def plot_dist(coordinate_list:list):
    """Plot the Euclidean distance between consecutive points."""
    for i in range(len(coordinate_list) - 1):
        dist = eucl_dist(coordinate_list[i], coordinate_list[i + 1])
        plt.plot(range(dist.shape[0]), dist, "b+")
        plt.show()
        print(f"Mean distance between consecutive points: {np.mean(dist)}")
        print(f"Standard deviation of the distance between consecutive points: {np.std(dist)}")




def center_3d(coordinates_3d: np.ndarray) -> tuple:
    """Take a 3D array of coordinates and return the mean of the x, y, and z coordinates.
    Args:
        coordinates_3d : A 3D numpy array of coordinates. shape : (n, 3)
    Returns:
        A tuple containing the mean x, y, and z coordinates.
    """
    assert isinstance(coordinates_3d, np.ndarray), "Coordinates must be a numpy array."
    assert coordinates_3d.shape[1] == 3, "Coordinates must have 3 columns."

    x = np.mean(coordinates_3d[:, 0])
    y = np.mean(coordinates_3d[:, 1])
    z = np.mean(coordinates_3d[:, 2])
    return x, y, z

def csv_to_trc(csv_path_in: str, trc_path_out: str):
    """
    Convertit un fichier CSV (format de votre pipeline) en fichier TRC 
    (requis par OpenSim), en convertissant les unités de mm en m.
    
    Format de sortie identique à Demo_SinglePerson_341-428_filt_butterworth_LSTM.trc
    """
    logger = logging.getLogger()
    
    try:
        # 1. Lire les données CSV
        Q_coords, frames_col, _, markers, header_lines = read_csv_data(csv_path_in)
        logger.info(f"CSV data loaded: {len(frames_col)} frames, {len(markers)} markers.")
    except Exception as e:
        logger.error(f"Failed to read CSV file: {csv_path_in}")
        raise e
        
    # 2. Obtenir les métadonnées
    try:
        frame_rate = int(header_lines[1].strip())
        logger.info(f"Frame rate detected: {frame_rate} Hz")
    except Exception:
        logger.warning("Frame rate not found in CSV header. Using default: 30 Hz")
        frame_rate = 30
        
    num_frames = len(frames_col)
    num_markers = len(markers)
    
    logger.info(f"Starting CSV to TRC conversion: {csv_path_in} -> {trc_path_out}")
    logger.info(f"Parameters: {num_frames} frames, {num_markers} markers, {frame_rate} Hz")
    
    # 3. Créer le header TRC (5 lignes)
    header = []
    
    # Ligne 1 : PathFileType
    header.append(f"PathFileType\t4\t(X/Y/Z)\t{Path(trc_path_out).name}\n")
    
    # Ligne 2 : Labels des colonnes
    header.append("DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\tOrigDataRate\tOrigDataStartFrame\tOrigNumFrames\n")
    
    # Ligne 3 : Valeurs des métadonnées
    header.append(f"{frame_rate}\t{frame_rate}\t{num_frames}\t{num_markers}\tm\t{frame_rate}\t{int(frames_col.iloc[0])}\t{num_frames}\n")
    
    # Ligne 4 : Noms des marqueurs (CORRECTION CRITIQUE)
    # Format EXACT : Frame#<TAB>Time<TAB>Marker1<TAB><TAB><TAB>Marker2<TAB><TAB><TAB>...
    # IMPORTANT : Chaque marqueur est suivi de 3 TABS, MÊME LE DERNIER !
    marker_line = "Frame#\tTime"
    for marker in markers:
        marker_line += f"\t{marker}\t\t"  # Marqueur + 2 tabs (total 3 avec le tab avant)
    header.append(marker_line + "\n")  # NE PAS faire rstrip() !
    
    # Ligne 5 : Labels X1, Y1, Z1, X2, Y2, Z2...
    labels_line = "\t\t"  # 2 tabs au début (sous Frame# et Time)
    for i in range(num_markers):
        labels_line += f"X{i+1}\tY{i+1}\tZ{i+1}\t"
    header.append(labels_line + "\n")  # NE PAS faire rstrip() !
    
    logger.debug("TRC header generated (5 lines)")
    
    # 4. Préparer les données
    # Recalculer la colonne 'Time'
    time_col = (frames_col - frames_col.iloc[0]) / frame_rate
    time_col.name = "Time"
    
    # CONVERSION D'UNITÉ : mm (CSV) -> m (TRC)
    logger.info("Converting coordinates from mm to m...")
    
    # Combiner les colonnes
    data_out = pd.concat([
        frames_col.reset_index(drop=True), 
        time_col.reset_index(drop=True)
    ], axis=1)
    
    # Ajouter les coordonnées
    Q_coords.columns = range(Q_coords.shape[1])
    data_out = pd.concat([
        data_out,
        Q_coords.reset_index(drop=True)
    ], axis=1)
    
    # Vérification des dimensions
    expected_data_cols = 2 + (num_markers * 3)  # Frame# + Time + (N marqueurs × 3 coords)
    actual_data_cols = data_out.shape[1]
    
    logger.debug(f"Data dimensions check: expected {expected_data_cols} columns, got {actual_data_cols}")
    
    if actual_data_cols != expected_data_cols:
        logger.warning(f"Column count mismatch: expected {expected_data_cols}, got {actual_data_cols} (offset: {actual_data_cols - expected_data_cols})")
    else:
        logger.info("Data dimensions validated successfully.")
    
    # 5. Écrire le fichier TRC
    try:
        with open(trc_path_out, 'w', newline='') as f:
            # Écrire les 5 lignes d'en-tête
            f.writelines(header)
            
            # Écrire les données
            data_out.to_csv(f, sep='\t', index=False, header=False, float_format='%.16f')
            
        logger.info(f"TRC file successfully created: {trc_path_out}")
        print(f"CSV to TRC conversion completed: {trc_path_out}")
        
    except Exception as e:
        logger.error(f"Failed to write TRC file: {trc_path_out}")
        raise e

    return trc_path_out
