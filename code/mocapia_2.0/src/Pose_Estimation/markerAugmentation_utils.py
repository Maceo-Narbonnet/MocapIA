import numpy as np
import pandas as pd
import config.Logger as logging

## AUTHORSHIP INFORMATION
__author__ = "Antoine Falisse, adapted by HunMin Kim and David Pagnon"
__copyright__ = "Copyright 2022, OpenCap"
__credits__ = ["Antoine Falisse", "HunMin Kim", "David Pagnon"]
__license__ = "Apache-2.0 License"
__maintainer__ = "David Pagnon"
__email__ = "contact@david-pagnon.com"
__status__ = "Development"


def convert_csv_to_meters(csv_data, markers):
    '''
    Convert marker data from mm to meters.
    '''
    logger = logging.Logger.get_logger()
    csv_data_meters = csv_data.copy()
    for marker in markers:
        for axis in ['x', 'y', 'z']:
            col_name = f'{marker}_{axis}'
            if col_name in csv_data_meters.columns:
                csv_data_meters[col_name] = csv_data_meters[col_name] / 1000.0
            else:
                logger.warning(f"[MARKER AUGMENTATION] Column {col_name} not found in data.")
    logger.info("[MARKER AUGMENTATION] Converted marker data from mm to meters.")
    return csv_data_meters


def add_neck_hip_data(trc_data, markers):
    '''
    Add neck and midhip data to trc_data if not present.
    Also update header and markers.
    '''

    midpoints = {
        'Neck': ['RShoulder', 'LShoulder'],
        'Hip': ['RHip', 'LHip']
    }
    
    # Create a copy to avoid modifying the original DataFrame
    trc_data_augmented = trc_data.copy()
    markers_augmented = markers[:] # Create a copy of the list

    for marker, midpoints_markers in midpoints.items():
        if marker not in markers:
            try:
                # Calculate midpoint for X, Y, Z
                trc_data_augmented[f'{marker}_x'] = trc_data[[f'{midpoints_markers[0]}_x', f'{midpoints_markers[1]}_x']].mean(axis=1)
                trc_data_augmented[f'{marker}_y'] = trc_data[[f'{midpoints_markers[0]}_y', f'{midpoints_markers[1]}_y']].mean(axis=1)
                trc_data_augmented[f'{marker}_z'] = trc_data[[f'{midpoints_markers[0]}_z', f'{midpoints_markers[1]}_z']].mean(axis=1)
                
                # Add new marker to the list
                markers_augmented.append(marker)
            except KeyError:
                logging.warning(f"Could not compute {marker} midpoint. Missing {midpoints_markers[0]} or {midpoints_markers[1]}.")

    return trc_data_augmented, markers_augmented


def predict_virtual_markers_GFLM(session, trc_data, markers, frame_rate):
    '''
    Predict virtual markers using the GFLM model.
    '''
    
    # %% Prepare data for GFLM
    markers_GFLM = ['RShoulder', 'LShoulder', 'RAsis', 'LAsis', 'RThigh', 
                    'LThigh', 'RKnee', 'LKnee', 'RTibia', 'LTibia', 'RAnkle', 
                    'LAnkle', 'RHeel', 'LHeel', 'RToe', 'LToe']
    
    # Check if all markers are present
    missing_markers = [m for m in markers_GFLM if m not in markers]
    if missing_markers:
        raise ValueError(f"Missing required markers for augmentation model: {', '.join(missing_markers)}")

    # Prepare input tensor
    # Assurez-vous que l'ordre des colonnes correspond à l'ordre des marqueurs GFLM
    trc_data_GFLM_cols = [f'{m}_{ax}' for m in markers_GFLM for ax in ['x', 'y', 'z']]
    trc_data_GFLM = trc_data[trc_data_GFLM_cols]
    
    trc_data_GFLM_np = np.array(trc_data_GFLM, dtype=np.float32)
    trc_data_GFLM_np_norm, m, s = normalize_data(trc_data_GFLM_np)
    trc_data_GFLM_np_norm = np.expand_dims(trc_data_GFLM_np_norm, axis=0)

    # %% Run GFLM
    inputs = {session.get_inputs()[0].name: trc_data_GFLM_np_norm}
    response = session.run(None, inputs)

    # %% Process GFLM output
    response_np = denormalize_data(response[0].squeeze(), m, s)
    
    response_markers_GFLM = ['Head', 'RThigh_med', 'LThigh_med', 'RKnee_med', 'LKnee_med', 
                            'RTibia_med', 'LTibia_med', 'RAnkle_med', 'LAnkle_med']
    
    Q_virtual_markers_GFLM = pd.DataFrame(response_np, columns=[f'{m}_{ax}' for m in response_markers_GFLM for ax in ['x', 'y', 'z']])
    
    return Q_virtual_markers_GFLM, response_markers_GFLM


def predict_virtual_markers_osim(trc_data, markers, frame_rate):
    '''
    Predict virtual markers using the osim model. (Simplified logic from original script)
    '''
    
    response_markers_osim = [
        'Sternum', 'RShoulder_d', 'LShoulder_d', 'RShoulder_p', 'LShoulder_p', 
        'RArm_p', 'LArm_p', 'RArm_d', 'LArm_d', 'RHand', 'LHand', 'RHand_d', 
        'LHand_d', 'RAsis_p', 'LAsis_p', 'RThigh_p', 'LThigh_p', 'RKnee_l', 
        'LKnee_l', 'RTibia_p', 'LTibia_p', 'RAnkle_l', 'LAnkle_l', 'RToe_p', 'LToe_p']
    
    # Create an empty DataFrame with the correct columns
    Q_virtual_markers_osim = pd.DataFrame(columns=[f'{m}_{ax}' for m in response_markers_osim for ax in ['x', 'y', 'z']], index=trc_data.index)
    
    # A simple example: if Neck is present, use it for Sternum
    if 'Neck' in markers:
        Q_virtual_markers_osim['Sternum_x'] = trc_data['Neck_x']
        Q_virtual_markers_osim['Sternum_y'] = trc_data['Neck_y']
        Q_virtual_markers_osim['Sternum_z'] = trc_data['Neck_z']
        
    # Fill NaNs with 0 or an appropriate value
    Q_virtual_markers_osim = Q_virtual_markers_osim.fillna(0.0)
    
    # TODO: Implement the full 'compute_markers_osim' logic if needed
    logging.warning("OSIM marker prediction is simplified and returns mostly placeholder data.")

    return Q_virtual_markers_osim, response_markers_osim


# Helper functions for GFLM
def normalize_data(data):
    m = np.mean(data, axis=0)
    s = np.std(data, axis=0)
    s[s == 0] = 1 # avoid division by zero
    data_norm = (data - m) / s
    return data_norm, m, s

def denormalize_data(data_norm, m, s):
    return data_norm * s + m

