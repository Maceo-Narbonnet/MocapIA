import numpy as np
import c3d
import pandas as pd
import re
import logging
import json

def read_config_json(config_path):
    """
    Charge le fichier de configuration principal depuis un fichier JSON.
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        # json.load() lit le fichier et le convertit en dictionnaire Python
        config_data = json.load(f)
    
    # Votre ancienne fonction retournait 'level' et 'config_dicts'.
    # 1. 'config_dicts' : C'est maintenant simplement votre dictionnaire 'config_data'.
    config_dicts = config_data
    
    # 2. 'level' : Cette information n'est pas dans votre JSON. 
    # C'était probablement une valeur calculée par l'ancienne fonction.
    # Si vous n'en avez plus besoin, vous pouvez retourner None.
    level = None # Ou une autre valeur par défaut si nécessaire
    
    return level, config_dicts

def convert_to_c3d(trc_path):
    '''
    Make Visual3D compatible c3d files from a trc path

    INPUT:
    - trc_path: string, trc file to convert

    OUTPUT:
    - c3d file
    '''

    c3d_path = trc_path.replace('.trc', '.c3d')
    marker_names, trc_data_np = extract_trc_data(trc_path)
    create_c3d_file(c3d_path, marker_names, trc_data_np)

    return c3d_path

def extract_trc_data(trc_path):
    '''
    Extract marker names and coordinates from a trc file.

    INPUTS:
    - trc_path: Path to the trc file

    OUTPUTS:
    - marker_names: List of marker names
    - marker_coords: Array of marker coordinates (n_frames, t+3*n_markers)
    '''

    # marker names
    with open(trc_path, 'r') as file:
        lines = file.readlines()
        marker_names_line = lines[3]
        marker_names = marker_names_line.strip().split('\t')[2::3]

    # time and marker coordinates
    trc_data_np = np.genfromtxt(trc_path, skip_header=5, delimiter = '\t')[:,1:] 

    return marker_names, trc_data_np

def create_c3d_file(c3d_path, marker_names, trc_data_np):
    '''
    Create a c3d file from the data extracted from a trc file.

    INPUTS:
    - c3d_path: Path to the c3d file
    - marker_names: List of marker names
    - trc_data_np: Array of marker coordinates (n_frames, t+3*n_markers)

    OUTPUTS:
    - c3d file
    '''

    # retrieve frame rate
    times = trc_data_np[:,0]
    frame_rate = round((len(times)-1) / (times[-1] - times[0]))

    # write c3d file
    writer = c3d.Writer(point_rate=frame_rate, analog_rate=0, point_scale=1.0, point_units='mm', gen_scale=-1.0)
    writer.set_point_labels(marker_names)
    writer.set_screen_axis(X='+Z', Y='+Y')
    
    for frame in trc_data_np:
        residuals = np.full((len(marker_names), 1), 0.0)
        cameras = np.zeros((len(marker_names), 1))
        coords = frame[1:].reshape(-1,3)*1000
        points = np.hstack((coords, residuals, cameras))
        writer.add_frames([(points, np.array([]))])

    writer.set_start_frame(0)
    writer._set_last_frame(len(trc_data_np)-1)

    with open(c3d_path, 'wb') as handle:
        writer.write(handle)


def read_trc(trc_path):
    '''
    Read a TRC file and extract its contents.

    INPUTS:
    - trc_path (str): The path to the TRC file.

    OUTPUTS:
    - tuple: A tuple containing the Q coordinates, frames column, time column, marker names, and header.
    '''

    try:
        with open(trc_path, 'r') as trc_file:
            header = [next(trc_file) for _ in range(5)]
        markers = header[3].split('\t')[2::3]
        markers = [m.strip() for m in markers if m.strip()] # remove last \n character
       
        trc_df = pd.read_csv(trc_path, sep="\t", skiprows=4, encoding='utf-8')
        frames_col, time_col = trc_df.iloc[:, 0], trc_df.iloc[:, 1]
        Q_coords = trc_df.drop(trc_df.columns[[0, 1]], axis=1)
        Q_coords = Q_coords.loc[:, ~Q_coords.columns.str.startswith('Unnamed')] # remove unnamed columns
        Q_coords.columns = np.array([[m,m,m] for m in markers]).ravel().tolist()

        return Q_coords, frames_col, time_col, markers, header
    
    except Exception as e:
        raise ValueError(f"Error reading TRC file at {trc_path}: {e}")
    
