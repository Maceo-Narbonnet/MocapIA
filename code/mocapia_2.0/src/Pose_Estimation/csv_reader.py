import pandas as pd
import numpy as np
from Ui.widgets.Plot_Manager import Point3D
from typing import List

Bodypart = str



class CSVReader:
    """This class is used to read 3D points from a CSV file and convert them to Point3D objects."""
    def __init__(self, file_path: str, sep:str = ",", skiprows:int = 3):
        """Initialize the CSVReader object with the file path, the separator and the number of rows to skip."""
        self.file_path = file_path
        self.separator = sep
        self.skiprows = skiprows


    def read_bodypart(self, bodypart: Bodypart) ->np.ndarray:
        """Read the x,y,z coordinates of a body for each frames part from a CSV file."""

        # Charger les données avec pandas en sautant les lignes d'en-tête inutiles
        df = pd.read_csv(self.file_path, skiprows=self.skiprows, sep=self.separator)

        # Extract target columns indices
        columns = df.columns.tolist()
        target_columns = [columns.index(bodypart)]
        target_columns += [target_columns[0]+1, target_columns[0]+2]

        # Extract the x,y,z coordinates of the body part, convert them to a numpy array in float values and return it
        return df.iloc[2:, target_columns].to_numpy().astype(float)


    def convert_array_to_point3D(self, array: np.ndarray, bodypart : Bodypart) -> Point3D:
        """Convert a numpy array to a list of Point3D objects."""
        return Point3D(array[:, 0], array[:, 1], array[:, 2], label=bodypart)


    def convert_csv_to_point3D(self, bodyparts:List[Bodypart], T:np.ndarray = None) -> List[Point3D]:
        """Convert for all bodyparts in the list. to a list of Point3D objects."""
        points = []
        if T is None:
            for bodypart in bodyparts:
                array = self.read_bodypart(bodypart)
                points.append(self.convert_array_to_point3D(array, bodypart))
            return points
        else:
            for bodypart in bodyparts:
                array = self.read_bodypart(bodypart)
                points.append(self.convert_array_to_point3D(self.change_ref(T, array), bodypart))
            return points


    def change_ref(self, T:np.ndarray, points:np.ndarray)->np.ndarray:
        """Change the reference of the 3D points with the transformation matrix.
        Args :
        T : np.ndarray : homogenous transformation matrix (shape : (4,4))
        points : np.ndarray : 3D points (shape : (nb_points, 3))
        Returns :
        np.ndarray : 3D points with the new reference (shape : (nb_points, 3))"""

        # Add a colum of ones to the points (N x 4) to get the homogeneous coordinates
        points_homogeneous = np.column_stack((points, np.ones(points.shape[0])))
        # applie the transformation matrix to the points
        points_transformed_homogeneous = np.dot(points_homogeneous, T.T)
        # Remove the last column of ones to get the 3D points
        points_R2 = points_transformed_homogeneous[:, :3]
        return points_R2










