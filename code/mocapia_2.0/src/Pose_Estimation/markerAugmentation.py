#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
###########################################################################
## MARKER AUGMENTATION LOGIC (Adapted for MoCapIA)                       ##
###########################################################################

Augments 3D coordinates from a CSV file.

Estimates the position of 43 additional markers.
Uses the LSTM model trained on Stanford data, converted to ONNX.
    
INPUTS: 
- a .csv file (with the specific 5-line header)
- a configuration dictionary

OUTPUT: 
- an augmented .csv file
'''

## INIT     IMPORTS     
import os
import copy
import numpy as np
import pandas as pd
import onnxruntime as ort
import glob
from typing import List, Tuple, Dict, Any
from config.Logger import Logger

from Pose_Estimation.filtering_utils import read_config_json
from Pose_Estimation.csv_utils import read_csv_data
from Pose_Estimation.markerAugmentation_utils import convert_csv_to_meters

# ========== ADDITION: HALPE_26 ↔ OPENSIM CORRESPONDENCES ==========

HALPE26_TO_OPENSIM_MAPPING = {
    # Format: 'Halpe26_Marker': 'opensim_study_marker'
    # 'Neck': 'C7_study',
    #'RShoulder': 'r_shoulder_study',
    #'LShoulder': 'L_shoulder_study'
    # 'RElbow': 'r_lelbow_study',
    # 'LElbow': 'L_lelbow_study',
    # 'RWrist': 'r_lwrist_study',
    # 'LWrist': 'L_lwrist_study',
    # 'RHip': 'r.ASIS_study',
    # 'LHip': 'L.ASIS_study',
    # 'RKnee': 'r_knee_study',
    # 'LKnee': 'L_knee_study',
    # 'RAnkle': 'r_ankle_study',
    # 'LAnkle': 'L_ankle_study',
    # 'RBigToe': 'r_toe_study',
    # 'LBigToe': 'L_toe_study',
    # 'RSmallToe': 'r_5meta_study',
    # 'LSmallToe': 'L_5meta_study',
    # 'RHeel': 'r_calc_study',
    # 'LHeel': 'L_calc_study',
}

OPENSIM_VIRTUAL_ONLY = [
    'r.PSIS_study', 'L.PSIS_study',
    'r_mknee_study', 'L_mknee_study',
    'r_mankle_study', 'L_mankle_study',
    'r_melbow_study', 'L_melbow_study',
    'r_mwrist_study', 'L_mwrist_study',
    'r_thigh1_study', 'r_thigh2_study', 'r_thigh3_study',
    'L_thigh1_study', 'L_thigh2_study', 'L_thigh3_study',
    'r_sh1_study', 'r_sh2_study', 'r_sh3_study',
    'L_sh1_study', 'L_sh2_study', 'L_sh3_study',
    'RHJC_study', 'LHJC_study',
    'RThumb', 'RIndex', 'RPinky',
    'LThumb', 'LIndex', 'LPinky',
]


## FUNCTIONS

def getOpenPoseMarkers_lowerExtremity2():
    feature_markers = [
        "Neck", "RShoulder", "LShoulder", "RHip", "LHip", "RKnee", "LKnee",
        "RAnkle", "LAnkle", "RHeel", "LHeel", "RSmallToe", "LSmallToe",
        "RBigToe", "LBigToe"]

    response_markers = [
        'r.ASIS_study', 'L.ASIS_study', 'r.PSIS_study',
        'L.PSIS_study', 'r_knee_study', 'r_mknee_study', 
        'r_ankle_study', 'r_mankle_study', 'r_toe_study', 
        'r_5meta_study', 'r_calc_study', 'L_knee_study', 
        'L_mknee_study', 'L_ankle_study', 'L_mankle_study',
        'L_toe_study', 'L_calc_study', 'L_5meta_study', 
        'r_shoulder_study', 'L_shoulder_study', 'C7_study', 
        'r_thigh1_study', 'r_thigh2_study', 'r_thigh3_study',
        'L_thigh1_study', 'L_thigh2_study', 'L_thigh3_study',
        'r_sh1_study', 'r_sh2_study', 'r_sh3_study', 'L_sh1_study',
        'L_sh2_study', 'L_sh3_study', 'RHJC_study', 'LHJC_study']

    return feature_markers, response_markers


def getMarkers_upperExtremity_noPelvis2():
    feature_markers = [
        "Neck", "RShoulder", "LShoulder", "RElbow", "LElbow", "RWrist",
        "LWrist"]

    response_markers = ["r_lelbow_study", "r_melbow_study", "r_lwrist_study",
                        "r_mwrist_study", "L_lelbow_study", "L_melbow_study",
                        "L_lwrist_study", "L_mwrist_study"]

    return feature_markers, response_markers


def hybrid_augmentation(csv_halpe26: str, csv_lstm: str, output_path: str) -> str:
    """
    Merges real markers (Halpe_26) and virtual markers (LSTM). Not used in current version (see config json).
    
    Strategy:
    1. Replace *_study markers with Halpe_26 equivalent by REAL DATA
    2. Keep virtual LSTM markers without equivalent (clusters, hands, etc.)
    
    Args:
        csv_halpe26: Path to filtered CSV (real Halpe_26 markers)
        csv_lstm: Path to augmented LSTM CSV (all virtual markers)
        output_path: Path to final hybrid CSV
        
    Returns:
        str: Output file path
    """
    logger = Logger.get_logger()
    
    # 1. Load both CSVs
    csv_halpe_data, frames_halpe, time_halpe, markers_halpe, header_halpe = read_csv_data(csv_halpe26)
    csv_lstm_data, frames_lstm, time_lstm, markers_lstm, header_lstm = read_csv_data(csv_lstm)

    csv_halpe_data = convert_csv_to_meters(csv_halpe_data, markers_halpe)
    logger.info("[AUGMENTATION] Halpe_26 data converted from mm to m")
    
    logger.info(f"[AUGMENTATION] Halpe_26: {len(markers_halpe)} real markers")
    logger.info(f"[AUGMENTATION] LSTM: {len(markers_lstm)} virtual markers")
    
    # 2. Create hybrid DataFrame (base = complete LSTM)
    csv_hybrid = csv_lstm_data.copy()
    
    # 3. Replace *_study markers with their Halpe_26 equivalents
    replaced_count = 0
    for halpe_marker, opensim_marker in HALPE26_TO_OPENSIM_MAPPING.items():
        if halpe_marker in markers_halpe and opensim_marker in markers_lstm:
            # Replace the 3 columns (x, y, z)
            for axis in ['x', 'y', 'z']:
                halpe_col = f'{halpe_marker}_{axis}'
                opensim_col = f'{opensim_marker}_{axis}'
                
                if halpe_col in csv_halpe_data.columns and opensim_col in csv_hybrid.columns:
                    csv_hybrid[opensim_col] = csv_halpe_data[halpe_col].values
            
            replaced_count += 1
            logger.info(f"[AUGMENTATION] {opensim_marker:25s} <- {halpe_marker:15s} (REAL)")
    
    logger.info(f"\n[AUGMENTATION] {replaced_count} markers replaced by real data")
    logger.info(f"[AUGMENTATION] {len(OPENSIM_VIRTUAL_ONLY)} virtual markers retained\n")
    
    # 4. Save hybrid CSV
    final_df = csv_hybrid.copy()
    final_df.insert(0, 'Frame', frames_lstm.values)
    
    # Recreate header (5 lines)
    new_header_lines = [header_lstm[0], header_lstm[1]]
    
    # Line 3: Marker list
    new_markers_str = ",".join(markers_lstm)
    new_header_lines.append(new_markers_str + '\n')
    
    # Line 4: Axes
    num_markers = len(markers_lstm)
    axes_str = "Frames" + ",X,Y,Z" * num_markers
    new_header_lines.append(axes_str + '\n')
    
    # Line 5: Units
    num_coords = num_markers * 3
    units_str = ",mm" * num_coords
    new_header_lines.append(units_str + '\n')
    
    # Write file
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        f.writelines(new_header_lines)
        final_df.to_csv(f, index=False, header=False)
    
    logger.info(f"OK - Hybrid CSV created: {output_path}")
    return output_path


def augment_markers_all(config_dict: Dict[str, Any], csv_path_in: str) -> float:
    '''
    Main function for marker augmentation on A SINGLE CSV file.
    Reads the CSV, applies the ONNX model, and writes the augmented CSV.
    '''
    logger = Logger.get_logger()
    # --- 1. Read augmentation configuration ---
    try:
        augmenter_config = config_dict['markerAugmentation']
    except KeyError:
        logger.error("The 'markerAugmentation' key is missing in config.json.")
        return np.nan

    feet_on_floor = augmenter_config.get('feet_on_floor')
    frame_range = augmenter_config.get('frame_range') # Note: 'frame_range' is in 'markerAugmentation' in your code
    subject_height = augmenter_config.get('participant_height')
    subject_mass = augmenter_config.get('participant_mass')

    default_height = config_dict.get('kinematics', {}).get('default_height', 1.75)

    augmenterDir = augmenter_config.get('model_dir')
    augmenterModelName = augmenter_config.get('augmenterModelName')
    augmenter_model = augmenter_config.get('augmenter_model')

    # Config checking
    if not augmenterDir:
        raise ValueError("[MARKER AUGMENTATION] The 'model_dir' for augmentation is not specified in Config.toml ")
    if not augmenterModelName:
        raise ValueError("[MARKER AUGMENTATION] The 'augmenterModelName' is not specified in Config.toml ")
    if not augmenter_model:
        raise ValueError("[MARKER AUGMENTATION] The 'augmenter_model' is not specified in Config.toml ")

    # Define output path
    base, ext = os.path.splitext(csv_path_in)
    csv_path_out = f"{base}_{augmenterModelName}.csv"

    logger.info(f"--- Processing file: {os.path.basename(csv_path_in)} ---")

    # --- 2. Handle height and mass (for a single file) ---
    if subject_height is None or subject_height == 0:
        subject_height = default_height
        logger.warning(f"[MARKER AUGMENTATION] No height (participant_height) found. Using default height: {default_height}m.")
    elif isinstance(subject_height, list):
        subject_height = subject_height[0] # Take the first height if it's a list
    
    if subject_mass is None or subject_mass == 0:
        subject_mass = 70
        logger.warning("[MARKER AUGMENTATION] No mass (participant_mass) found. Using default mass: 70kg.")
    elif isinstance(subject_mass, list):
        subject_mass = subject_mass[0] # Take the first mass if it's a list

    # --- 3. Define models ---
    # Lower body           
    augmenterModelType_lower = '{}_lower'.format(augmenter_model)
    feature_markers_lower, response_markers_lower = getOpenPoseMarkers_lowerExtremity2()
    # Upper body
    augmenterModelType_upper = '{}_upper'.format(augmenter_model)
    feature_markers_upper, response_markers_upper = getMarkers_upperExtremity_noPelvis2()        
    augmenterModelType_all = [augmenterModelType_lower, augmenterModelType_upper]
    feature_markers_all = [feature_markers_lower, feature_markers_upper]
    response_markers_all = [response_markers_lower, response_markers_upper]
    logger.info(f'[MARKER AUGMENTATION] Using Stanford augmentation model {augmenterModelName} {augmenter_model}.')
    if feet_on_floor:
        logger.info("[MARKER AUGMENTATION] Feet will be vertically offset to ground level (y=0.01).")

    # --- 4. Data processing ---
    try:
        # Import CSV file
        # Returns a flat DataFrame (e.g.: Nose_x, Nose_y, Nose_z)
        csv_data, frames_col, time_col, markers, header_lines = read_csv_data(csv_path_in)
    except Exception as e:
        logger.error(f"[MARKER AUGMENTATION] Unable to read file {csv_path_in}. Error: {e}")
        return np.nan # Stop processing for this file
    
    # Convert data from mm to meters
    csv_data = convert_csv_to_meters(csv_data, markers)
    logger.info("[MARKER AUGMENTATION] Converted marker data from mm to meters")

    # Frame range selection
    if frame_range is None or frame_range in ('all', 'auto', []):
         f_range = [frames_col.iloc[0], frames_col.iloc[-1]]
    else:
         f_range = [max(frames_col.iloc[0], frame_range[0]), min(frames_col.iloc[-1], frame_range[1])]

    try:
        # Find pandas indices, not frame numbers
        f_index_start = frames_col[frames_col == f_range[0]].index[0]
        f_index_end_candidates = frames_col[frames_col == f_range[1]].index
        if f_index_end_candidates.empty:
            f_index_end = len(csv_data)
        else:
            f_index_end = f_index_end_candidates[-1] + 1

    except IndexError:
         logger.warning(f"[MARKER AUGMENTATION] Invalid frame range ({f_range}). Using full range.")
         f_index_start = 0
         f_index_end = len(csv_data)

    csv_data = csv_data.iloc[f_index_start:f_index_end].reset_index(drop=True)
    frames_col = frames_col.iloc[f_index_start:f_index_end].reset_index(drop=True)
    time_col = time_col.iloc[f_index_start:f_index_end].reset_index(drop=True)

    # Check that all feature markers are present
    feature_markers_joined = set(feature_markers_all[0] + feature_markers_all[1])
    missing_markers = list(feature_markers_joined - set(markers))
    if len(missing_markers) > 0:
        logger.error(f"[MARKER AUGMENTATION] Marker augmentation requires markers: {missing_markers}.")
        logger.error(f"[MARKER AUGMENTATION] These markers are missing from file {csv_path_in}. File ignored.")
        return np.nan # Stop processing

    # Loop over augmentation types (lower, upper)
    for idx_augm, augmenterModelType in enumerate(augmenterModelType_all):
        feature_markers = feature_markers_all[idx_augm]
        response_markers = response_markers_all[idx_augm]
        
        augmenterModelDir = os.path.join(augmenterDir, augmenterModelName, 
                                         augmenterModelType)
        
        # %% Input preprocessing
        
        # Step 1: Select marker data (flat format)
        try:
            feature_cols = [f'{m}_{ax}' for m in feature_markers for ax in ['x', 'y', 'z']]
            csv_data_feature = csv_data[feature_cols]
        except KeyError:
            missing = set(feature_cols) - set(csv_data.columns)
            logger.error(f"[MARKER AUGMENTATION] Missing feature columns: {missing}. File ignored.")
            break # Exit augmentation loop

        # Step 2: Normalize with reference marker position (Hip)
        if 'Hip_x' not in csv_data.columns:
             logger.error(f"[MARKER AUGMENTATION] Reference marker 'Hip' ('Hip_x', 'Hip_y', 'Hip_z') is missing. File ignored.")
             break # Exit augmentation loop
        
        # Use Hip_x, Hip_y, Hip_z columns for tiling
        hip_data_np = csv_data[['Hip_x', 'Hip_y', 'Hip_z']].values
        norm_csv_data_feature = csv_data_feature.values - np.tile(hip_data_np, (1, csv_data_feature.shape[1] // 3))

        # Step 3: Normalize with subject height
        norm2_csv_data_feature = copy.deepcopy(norm_csv_data_feature)
        norm2_csv_data_feature = norm2_csv_data_feature / subject_height # Use single value
        
        # Step 4: Add remaining features (height, mass)
        inputs = copy.deepcopy(norm2_csv_data_feature)
        inputs = np.concatenate(
                (inputs, subject_height * np.ones((inputs.shape[0], 1))), axis=1) # Use single value
        inputs = np.concatenate(
                (inputs, subject_mass * np.ones((inputs.shape[0], 1))), axis=1) # Use single value
            
        # Step 5: Preprocess data (center-reduce)
        pathMean = os.path.join(augmenterModelDir, "mean.npy")
        print("DEBUG pathMean =", pathMean)
        trainFeatures_mean = np.load(pathMean, allow_pickle=True)

        pathSTD = os.path.join(augmenterModelDir, "std.npy")
        trainFeatures_std = np.load(pathSTD, allow_pickle=True)

        inputs = (inputs - trainFeatures_mean) / trainFeatures_std
            
        # Step 6: Reshape for LSTM model
        inputs = np.reshape(inputs, (1, inputs.shape[0], inputs.shape[1]))
            
        # %% Load model and predict
        onnx_path = os.path.join(augmenterModelDir, "model.onnx")
        if not os.path.exists(onnx_path):
            logger.error(f"[MARKER AUGMENTATION] ONNX model file not found: {onnx_path}")
            break
        
        session = ort.InferenceSession(onnx_path)
        outputs = session.run(['output_0'], {'inputs': inputs.astype(np.float32)})[0]

        # %% Output post-processing
        # Step 1: Reshape
        outputs = np.reshape(outputs, (outputs.shape[1], outputs.shape[2]))
            
        # Step 2: Denormalize with height
        unnorm_outputs = outputs * subject_height # Use single value
        
        # ✅ CRITICAL FIX
        # Step 3: Denormalize with reference position (Hip)
        # 
        # OLD CODE (BUGGY):
        # unnorm2_outputs = unnorm_outputs + np.tile(hip_data_np, (1, unnorm_outputs.shape[1] // 3))
        #
        # NEW CODE (FIXED):
        # Repeat Hip's 3 coordinates for EACH TRIPLET of columns
        num_response_markers = len(response_markers)  # Ex: 8 markers for upper body
        hip_tiled = np.tile(hip_data_np, (1, num_response_markers))  # (N_frames, 24)

        # Dimension verification
        if hip_tiled.shape != unnorm_outputs.shape:
            logger.error(f"[MARKER AUGMENTATION] Dimension ERROR during denormalization!")
            logger.error(f"[MARKER AUGMENTATION] hip_tiled.shape = {hip_tiled.shape}")
            logger.error(f"[MARKER AUGMENTATION] unnorm_outputs.shape = {unnorm_outputs.shape}")
            logger.error(f"[MARKER AUGMENTATION] Number of response markers = {num_response_markers}")
            raise ValueError("Dimension incompatibility in denormalization.")

        unnorm2_outputs = unnorm_outputs + hip_tiled


        # %% Add response markers to DataFrame (flat format)
        response_cols = [f'{m}_{ax}' for m in response_markers for ax in ['x', 'y', 'z']]
        csv_data_response = pd.DataFrame(unnorm2_outputs, columns=response_cols)
        csv_data = pd.concat([csv_data, csv_data_response], axis=1)

        markers += response_markers
        logger.info(f"[MARKER AUGMENTATION] {augmenterModelType} markers added.")

    else: # If for loop completed without 'break'
        # %% Extract minimum y position (flat format)
        response_markers_conc = [m for resp in response_markers_all for m in resp]
        y_cols = [f'{m}_y' for m in response_markers_conc if f'{m}_y' in csv_data.columns]
        
        if not y_cols:
            logger.warning(f"[MARKER AUGMENTATION] No response marker 'y' column found for ground offset.")
            min_y_pos = 0.0
        else:
            min_y_pos = csv_data[y_cols].min().min()
            
        # %% Offset if option enabled (flat format)
        if feet_on_floor:
            logger.info(f"[MARKER AUGMENTATION] Minimum Y position detected: {min_y_pos:.4f}. Offsetting to Y=0.01.")
            # Find all Y columns and offset them
            all_y_cols = [col for col in csv_data.columns if col.endswith('_y')]
            csv_data[all_y_cols] = csv_data[all_y_cols] - (min_y_pos - 0.01)
            
        # Create final DataFrame, WITHOUT 'Time' column
        final_df = csv_data.copy()
        final_df['Frame'] = frames_col.values
        
        # Reorganize to put 'Frame' at the beginning
        cols_to_move = ['Frame']
        # 'other_cols' now contains all coordinate columns (Nose_x, Nose_y, ...)
        other_cols = [col for col in final_df.columns if col not in cols_to_move]
        final_df = final_df[cols_to_move + other_cols]
        
        # Recreate 5-line header
        
        # Lines 1 & 2 (unchanged from original)
        new_header_lines = [header_lines[0], header_lines[1]]
        
        # Line 3 (Marker list)
        # 'markers' is the updated Python list (e.g.: ['Nose', ..., 'r.ASIS_study'])
        new_markers_str = ",".join(markers)
        new_header_lines.append(new_markers_str + '\n')
        
        # Line 4 (Axes: Frames,X,Y,Z,X,Y,Z,...)
        num_markers = len(markers)
        axes_str = "Frames" + ",X,Y,Z" * num_markers
        new_header_lines.append(axes_str + '\n')

        # Line 5 (Units: ,mm,mm,mm,...)
        # (One comma for 'Frames', then 'mm' for each coordinate)
        num_coords = num_markers * 3
        units_str = ",mm" * num_coords
        new_header_lines.append(units_str + '\n')
        
        try:
            with open(csv_path_out, 'w', newline='', encoding='utf-8') as f:
                f.writelines(new_header_lines)
                final_df.to_csv(f, index=False, header=False)
            logger.info(f"[MARKER AUGMENTATION] Augmented coordinates stored in {csv_path_out}.")
        except Exception as e:
            logger.error(f"[MARKER AUGMENTATION] Unable to write output file {csv_path_out}. Error: {e}")
            return np.nan
        
        return min_y_pos # Success

    # If loop was interrupted by 'break'
    logger.error("[MARKER AUGMENTATION] Processing was interrupted due to an error (see logs above).")
    return np.nan


if __name__ == "__main__":
    # --- Test block for direct execution ---
    logger = Logger.get_logger()
    # 1. Configure logging to see output in terminal
    
    # 2. Define path to your configuration file
    CONFIG_FILE_PATH = r"D:\Users\Etudiant\Documents\MOCAPIA5\mocapia_3\src\config\Settings\config.json"
    CSV_FILE_PATH = r"D:\Users\Etudiant\Documents\SAM 3D\sam_3d\output\keypoints_3D_merged_labframe.csv"

    logger.info(f"Attempting to load configuration file: {CONFIG_FILE_PATH}")

    if not os.path.exists(CONFIG_FILE_PATH):
        logger.error(f"[MARKER AUGMENTATION] ERROR: Configuration file not found at: {CONFIG_FILE_PATH}")
        logger.error("[MARKER AUGMENTATION] Please create this file or correct the path in the script.")
    elif not os.path.exists(CSV_FILE_PATH):
        logger.error(f"[MARKER AUGMENTATION] ERROR: Test CSV file not found at: {CSV_FILE_PATH}")
        logger.error("[MARKER AUGMENTATION] Please correct the path in the script.")
    else:
        try:
            # 3. Load configuration
            # Using function from filtering_utils
            level, config_dict = read_config_json(CONFIG_FILE_PATH)
            
            if not config_dict:
                logger.error("[MARKER AUGMENTATION] Configuration file is empty or invalid.")
            else:
                logger.info("[MARKER AUGMENTATION] Configuration loaded successfully.")

                # 4. Call main function
                logger.info("--- Starting augment_markers_all ---")
                augment_markers_all(config_dict, CSV_FILE_PATH)
                logger.info("--- End of augment_markers_all ---")
                logger.info("[MARKER AUGMENTATION] Test completed successfully.")

        except ImportError:
             logger.error("[MARKER AUGMENTATION] Import error. Make sure 'filtering_utils.py' is accessible (e.g.: in same folder or in PYTHONPATH).")
        except Exception as e:
            logger.error("[MARKER AUGMENTATION] An error occurred during execution:")
            logger.error(e, exc_info=True) # Display full traceback
            logger.error("[MARKER AUGMENTATION] Test failed.")