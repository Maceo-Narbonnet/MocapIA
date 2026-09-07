import pandas as pd
import numpy as np
import logging

def convert_trc_to_opensim(input_trc_path, output_trc_path):
    """
    Converts a TRC file from camera coordinate system to OpenSim coordinate system.
    
    Transformations for OpenSim (medical coordinate system):
    - X_camera -> X_opensim (medio-lateral, positive = patient's right)
    - Y_camera -> Y_opensim (antero-posterior, positive = forward)
    - Z_camera -> Z_opensim (vertical, positive = upward)
    
    WARNING: Adjustments may be needed depending on your camera orientation.
    If your skeleton is upside down in OpenSim, modify the signs below.
    """
    logger = logging.getLogger()
    
    logger.info(f"Starting TRC coordinate system conversion: {input_trc_path} -> {output_trc_path}")
    
    # Read the complete file
    try:
        with open(input_trc_path, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        logger.error(f"Failed to read TRC file: {input_trc_path}")
        raise e
    
    # First 5 lines are headers
    header_lines = lines[:5]
    data_lines = lines[5:]
    
    logger.info(f"TRC file loaded: {len(data_lines)} data lines detected after header")
    
    # Data conversion
    converted_data_lines = []
    first_valid_line_orig = None
    first_valid_line_conv = None
    
    for line_num, line in enumerate(data_lines):
        values = line.strip().split('\t')
        
        if len(values) < 3:
            logger.debug(f"Line {line_num + 6} skipped (only {len(values)} column(s))")
            converted_data_lines.append(line)
            continue
        
        frame_num = values[0]
        time = values[1]
        marker_values = values[2:]
        
        # Convert triplets (X, Y, Z) -> OpenSim
        converted_markers = []
        for i in range(0, len(marker_values), 3):
            if i+2 < len(marker_values):
                try:
                    x_cam = float(marker_values[i])
                    y_cam = float(marker_values[i+1])
                    z_cam = float(marker_values[i+2])
                    
                    # TRANSFORMATION FOR OPENSIM
                    # Adjust according to your camera orientation!
                    
                    # Option 1: If skeleton is upside down (head down)
                    x_opensim = x_cam          # Lateral (left-right)
                    y_opensim = z_cam          # Antero-posterior (front-back)
                    z_opensim = -y_cam         # Vertical (INVERTED to stand upright)
                    
                    # Option 2: If skeleton is lying on its side
                    # x_opensim = -y_cam
                    # y_opensim = x_cam
                    # z_opensim = z_cam
                    
                    # Option 3: If skeleton is facing the wrong direction
                    # x_opensim = -x_cam
                    # y_opensim = -z_cam
                    # z_opensim = -y_cam
                    
                    converted_markers.extend([str(x_opensim), str(y_opensim), str(z_opensim)])
                except ValueError:
                    # Keep values as is if conversion fails
                    logger.warning(f"Line {line_num + 6}: Could not convert triplet at position {i}")
                    converted_markers.extend(marker_values[i:i+3])
            else:
                # Not enough values for a complete triplet
                converted_markers.extend(marker_values[i:])
        
        new_line = '\t'.join([frame_num, time] + converted_markers) + '\n'
        converted_data_lines.append(new_line)
        
        if first_valid_line_orig is None and len(values) >= 5:
            first_valid_line_orig = values
            first_valid_line_conv = [frame_num, time] + converted_markers
    
    # Verification
    if first_valid_line_orig:
        logger.info(f"Coordinate transformation validation (first valid frame):")
        logger.info(f"  BEFORE (camera frame): Nose (X,Y,Z) = ({first_valid_line_orig[2]}, {first_valid_line_orig[3]}, {first_valid_line_orig[4]})")
        logger.info(f"  AFTER (OpenSim frame): Nose (X,Y,Z) = ({first_valid_line_conv[2]}, {first_valid_line_conv[3]}, {first_valid_line_conv[4]})")
        logger.info(f"Transformation applied: X_opensim = X_camera, Y_opensim = Z_camera, Z_opensim = -Y_camera")
    
    # Write the output file
    try:
        with open(output_trc_path, 'w') as f:
            f.writelines(header_lines)
            f.writelines(converted_data_lines)
    except Exception as e:
        logger.error(f"Failed to write converted TRC file: {output_trc_path}")
        raise e
    
    valid_frames_count = len([l for l in converted_data_lines if len(l.strip().split('\t')) >= 3])
    
    logger.info(f"TRC coordinate system conversion completed: {output_trc_path}")
    logger.info(f"Total frames converted: {valid_frames_count}")
    logger.info(f"WARNING: If skeleton orientation is incorrect in OpenSim, try Options 2 or 3 in the code (lines ~47-56)")

# Execution
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    input_trc = r"d:\Users\Etudiant\Documents\MOCAPIA5\forOpenSim\pose-3d\JJack_complete_3D_points__filt_butterworth_LSTM.trc"
    output_trc = r"d:\Users\Etudiant\Documents\MOCAPIA5\forOpenSim\pose-3d\JJack_complete_3D_points__filt_butterworth_LSTM_CONVERTED.trc"
    
    convert_trc_to_opensim(input_trc, output_trc)