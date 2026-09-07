from PyQt5.QtWidgets import QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QApplication, QScrollArea, QGridLayout, QMessageBox, QComboBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal, QTimer, pyqtSlot
from Ui.widgets.Recorder_Indicator import RecordingIndicator
import pyqtgraph.opengl as gl
import pyqtgraph as pg
from OpenGL.GL import *
from OpenGL.GLUT import *
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import sys
import os
import cv2
from typing import List, Tuple, final



PLOT2D_FIXED_SIZE:final = (750, 300)  # Taille fixe des plots 2D

class QPlayButton(QPushButton):
    """Button that changes its icon between play and pause"""
    def __init__(self):
        super().__init__()
        self.setIcon(QIcon(r"Ui\assets\pause.svg"))
        self.play:bool = True

    def change_icon(self):
        """Use this function to change the icon of the button between play and pause"""
        if self.play:
            self.setIcon(QIcon(r"Ui\assets\play.svg"))
            self.play = False
        else:
            self.setIcon(QIcon(r"Ui\assets\pause.svg"))
            self.play = True


class TimelineManager(QWidget):
    """Timeline manager to controls the timeline of a unique plot,
    it contains buttons to play, pause, fast forward, rewind and loop
    throw signals to the plot to control it"""

    #signals
    play_signal = pyqtSignal()
    pause_signal = pyqtSignal()
    fast_forward_signal = pyqtSignal()
    rewind_signal = pyqtSignal()
    loop_signal_true = pyqtSignal()
    loop_signal_false = pyqtSignal()
    save_all_signal = pyqtSignal() #signal to save all plots and 3D render (images in .png for 2D plots and video in .mp4 for 3D render)


    def __init__(self):
        super().__init__()

        self.layout = QHBoxLayout() #main layout

        #buttons declaration
        self.play_pause_button = QPlayButton()
        self.fast_forward_button = QPushButton()
        self.rewind_button = QPushButton()
        self.loop_button = QPushButton()
        self.save_all_button = QPushButton()

        #add icons to buttons
        self.fast_forward_button.setIcon(QIcon(r"Ui\assets\fast-forward.svg"))
        self.rewind_button.setIcon(QIcon(r"Ui\assets\rewind.svg"))
        self.loop_button.setCheckable(True)
        self.loop_button.setChecked(True)
        self.loop_button.setIcon(QIcon(r"Ui\assets\loop.svg"))
        self.save_all_button.setIcon(QIcon(r"Ui\assets\save_black.svg"))

        #bindings
        self.play_pause_button.clicked.connect(self.on_click_play_pause_button)
        self.fast_forward_button.clicked.connect(self.on_click_fast_forward_button)
        self.rewind_button.clicked.connect(self.on_click_rewind_button)
        self.loop_button.clicked.connect(self.on_click_loop_button)
        self.save_all_button.clicked.connect(self.on_click_save_all_button)

        #add to layout
        self.layout.addWidget(self.rewind_button)
        self.layout.addWidget(self.play_pause_button)
        self.layout.addWidget(self.fast_forward_button)
        self.layout.addWidget(self.loop_button)
        self.layout.addStretch()
        self.layout.addWidget(self.save_all_button)

        #buttons infos
        self.loop_button.setToolTip("Repeat plot animation")
        self.save_all_button.setToolTip("Save all plots")

        self.setLayout(self.layout)

    #! ---------- BUTTONS FUNCTIONS ---------- !#
    def on_click_play_pause_button(self):
        self.play_pause_button.change_icon()
        if self.play_pause_button.play:
            self.play_signal.emit()
        else:
            self.pause_signal.emit()

    def on_click_fast_forward_button(self):
        self.fast_forward_signal.emit()

    def on_click_rewind_button(self):
        self.rewind_signal.emit()

    def on_click_loop_button(self):
        if self.loop_button.isChecked():
            self.loop_signal_true.emit()
        else:
            self.loop_signal_false.emit()

    def on_click_save_all_button(self):
        self.save_all_signal.emit()



class Plot2D(QWidget):
    """
    Plot2D class to display a 2D curve in real time
    Args:
    timeline_manager (TimelineManager) : The timeline manager to control the plot (check line 35 in Plot_Manager.py)
    Y_data : (1D array-like) The data to display
    framerate : (int > 0) The number of frames per second, default is 30
    title : (str, optional) The title of the plot, default is "Curve Visual"
    Y_title : (str, optional) The title of the Y axis, default is "Angle"
    Y_units : (str, optional) The units of the Y axis, default is "degrees"
    """

    def __init__(self, timeline_manager:TimelineManager, Y_data:np.ndarray, framerate:int=30, title:str="Curve Visual", Y_title:str="Angle", Y_units:str="degrees", stacking:bool = True, timeline_width:int = 3, grid:bool = True):
        super().__init__()

        # Arguments validation
        assert type(framerate) == int, "framerate must be an integer"
        assert framerate > 0, "framerate must be positive"
        assert type(title) == str, "title must be a string"
        assert type(Y_title) == str, "Y_title must be a string"
        assert type(Y_units) == str, "Y_units must be a string"
        assert type(stacking) == bool, "stacking must be a boolean"
        assert type(timeline_width) == int, "timeline_width must be an integer"
        assert timeline_width > 0, "timeline_width must be positive"
        assert type(grid) == bool, "grid must be a boolean"
        assert isinstance(timeline_manager, TimelineManager), "timeline_manager must be a TimelineManager object"

        #class stettings 
        self.setMinimumHeight(200)

        #class attributes setup
        self.framerate = framerate # Number of frames per second
        self.time_per_frame = 1000 // framerate  # Time in milliseconds for each frame
        self.current_index = 0 # Index of the current frame
        # self.is_paused = False #True if user clicked on pause button
        self.is_looping = True #True if user clicked on loop button

        self.Y_data = Y_data # Data is a 1D array-like of values to display (generally float or int)
        self.X_data = np.array([i * (1 / framerate) for i in range(len(self.Y_data))])  # Time associated with each frame
        self.max_points = timeline_width * framerate  # Number of visible points at a given time
        self.stacking=stacking

        #Initialization of the plot (PyQtGraph)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#000000')
        self.plot_widget.setTitle(title)
        self.plot_widget.setLabel('left', Y_title, units=Y_units, color='red', size='20pt')
        self.plot_widget.setLabel('bottom', 'Temps', units='s',color='red', size='20pt')

        # Improve axes and grid
        self.plot_widget.showGrid(x=grid, y=grid)

        # Curve style
        self.pen = pg.mkPen(color=(255, 0, 0), width=2)  # Courbe rouge et épaisse

        # Curve to plot
        self.curve = self.plot_widget.plot(self.X_data, self.Y_data, pen=self.pen)
        self.curve.setData([], [])  # Ne pas afficher les données immédiatement

        # Create a layout and add the plot_widget
        layout = QVBoxLayout()
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)


        #Connections with the timeline manager's signals
        timeline_manager.play_signal.connect(self.play)
        timeline_manager.pause_signal.connect(self.pause)
        timeline_manager.fast_forward_signal.connect(self.fast_forward)
        timeline_manager.rewind_signal.connect(self.rewind)
        timeline_manager.loop_signal_true.connect(self.loop_true)
        timeline_manager.loop_signal_false.connect(self.loop_false)


        #Animation timer
        self.timer = QTimer()
        self.timer.setInterval(self.time_per_frame)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

    #! ---------- UPDATE PLOT FUNCTIONS ---------- !#
    @pyqtSlot()
    def update_plot(self):
        """Update the plot with the next frame of data using the chosen stacking mode"""
        if self.stacking:
            self.update_curve_stacked()
        else:
            self.update_curve_unstacked()


    def update_curve_stacked(self):
        """Update the plot with the next frame of data in stacked mode (one of the two modes available)"""
        if self.current_index < len(self.Y_data):
            self.curve.setData(self.X_data[:self.current_index + 1], self.Y_data[:self.current_index + 1], pen=self.pen)
            self.current_index += 1
        else:
            if self.is_looping:
                self.current_index = 0
            else:
                self.timer.stop()

    def update_curve_unstacked(self):
        """Update the plot with the next frame of data in unstacked mode (one of the two modes available)"""
        if self.current_index < len(self.Y_data):
            # Mettre à jour la courbe avec toutes les valeurs disponibles jusqu'à maintenant
            self.data_line = self.plot_widget.plot(self.X_data[:self.max_points], self.Y_data[:self.max_points])
            self.data_line.setData(self.X_data[:self.current_index+1], self.Y_data[:self.current_index+1], pen=self.pen)

            # Faire défiler la vue pour centrer les derniers points visibles
            if self.current_index >= self.max_points:
                self.plot_widget.setXRange(self.X_data[self.current_index - self.max_points], self.X_data[self.current_index])

            # Avance le pointeur pour la prochaine valeur
            self.current_index += 1
        else:
            if self.is_looping:
                self.current_index = 0
            else:
                self.timer.stop()

    #!---------- TIMELINE MANAGER FUNCTIONS ----------!#
    #! All functions to control the plot from the timeline manager, to pause it, play it, fast forward, rewind, loop or not ...

    @pyqtSlot()
    def play(self):
        # self.is_paused = False
        self.timer.start()

    @pyqtSlot()
    def pause(self):
        # self.is_paused = True
        self.timer.stop()

    @pyqtSlot()
    def fast_forward(self):
        self.current_index += self.framerate*3 #skip 3 seconds
        if self.current_index >= len(self.Y_data):
            self.current_index = len(self.Y_data) - 1
        self.curve.setData(self.X_data[:self.current_index + 1], self.Y_data[:self.current_index + 1], pen=self.pen)

    @pyqtSlot()
    def rewind(self):
        self.current_index -= self.framerate*3
        if self.current_index < 0:
            self.current_index = 0
        self.curve.setData(self.X_data[:self.current_index + 1], self.Y_data[:self.current_index + 1], pen=self.pen)

    @pyqtSlot()
    def loop_true(self):
        self.is_looping = True

    @pyqtSlot()
    def loop_false(self):
        self.is_looping = False



class Plot2D_With_Buttons(QWidget):
    """Plot2D with buttons to maximize, minimize, delete and save the plot as an image
    Args: same as Plot2D class"""
    def __init__(self, timeline_manager:TimelineManager, project_path, Y_data:np.ndarray, framerate=120, title="Curve Visual", Y_title="Angle", Y_units="degrees", stacking = True, timeline_width = 3, grid = True):
        super().__init__()

        self.project_path = project_path
        #initiallize class attributes
        self.minimized = False
        self.maximazed = False
        self.original_size = PLOT2D_FIXED_SIZE

        #main layout
        self.main_layout = QGridLayout() #main layout

        #plot 
        self.plot = Plot2D(timeline_manager, Y_data, framerate, title, Y_title, Y_units, stacking, timeline_width, grid)
        self.main_layout.addWidget(self.plot, 0, 0, 50, 50)
        self.setLayout(self.main_layout)

        #buttons
        self.maximize_button = QPushButton()
        self.minimize_button = QPushButton()
        self.delete_button = QPushButton()
        self.save_button = QPushButton()

        #buttons icons
        self.maximize_button.setIcon(QIcon(r"Ui\assets\maximize.svg"))
        self.minimize_button.setIcon(QIcon(r"Ui\assets\minimize.svg"))
        self.delete_button.setIcon(QIcon(r"Ui\assets\trash.svg"))
        self.save_button.setIcon(QIcon(r"Ui\assets\save.svg"))

        #adjuste button style
        self.maximize_button.setFixedSize(30, 30)
        self.minimize_button.setFixedSize(30, 30)
        self.delete_button.setFixedSize(30, 30)
        self.save_button.setFixedSize(30, 30)
        self.maximize_button.setStyleSheet("border: none; background-color: #000000;")
        self.minimize_button.setStyleSheet("border: none; background-color: #000000;")
        self.delete_button.setStyleSheet("border: none; background-color: #000000;")
        self.save_button.setStyleSheet("border: none; background-color: #000000;")

        #bindings
        self.maximize_button.clicked.connect(self.on_click_maximize_button)
        self.minimize_button.clicked.connect(self.on_click_minimize_button)
        self.delete_button.clicked.connect(self.on_click_delete_button)
        self.save_button.clicked.connect(self.save_plot)
        timeline_manager.save_all_signal.connect(self.save_plot)

        #add to layout
        self.main_layout.addWidget(self.save_button, 1, 3)
        self.main_layout.addWidget(self.maximize_button, 1, 46)
        self.main_layout.addWidget(self.minimize_button, 1, 47)
        self.main_layout.addWidget(self.delete_button, 1, 48)

        self.setFixedSize(self.original_size[0], self.original_size[1]) #! Modify this to set a fixed size
        self.updateGeometry()

    #! ---------- BUTTONS FUNCTIONS ---------- !#
    def on_click_maximize_button(self):
        if self.maximazed:
            self.setFixedSize(self.original_size[0], self.original_size[1])
            self.updateGeometry() 
            self.maximazed = False
        else:
            self.setFixedSize(self.original_size[0], 500)
            self.updateGeometry()
            self.maximazed = True
            self.minimized = False

    def on_click_minimize_button(self):
        if self.minimized :
            self.setFixedSize(self.original_size[0], self.original_size[1])
            self.updateGeometry()   
            self.minimized = False
        else:
            self.setFixedSize(self.original_size[0], 45)
            self.updateGeometry()
            self.minimized = True
            self.maximazed = False

    def on_click_delete_button(self):
        self.deleteLater()

    def save_plot(self):
        """This function save the plot as an image in the folder Ui"""
        self.video_filepath = f''
        try:
            title = self.plot.plot_widget.plotItem.titleLabel.text # Get the title of the plot
            
            original_path = os.path.normpath(self.project_path)    #exemple: D:\Users\Etudiant\Documents\MoCapIA4\mocapia_3\TestProject\MoCap_Demo5\analysis\Capture 1\Capture 1_3D_points_.csv
            target_folder = "analysis"
            parts = original_path.split(os.sep)
            if target_folder in parts:
                index = parts.index(target_folder)
                before_analysis_path = os.sep.join(parts[:index])    #D:\Users\Etudiant\Documents\MoCapIA4\mocapia_3\TestProject\MoCap_Demo5
            else:
                print("Target folder not found in path.")
                
            # save_folder = r"D:\Users\Etudiant\Documents\Stages-TX\TN09-Mocapia3-Colin\test\Ui" #! Change this path to save the image in another folder
            save_folder = os.path.join(before_analysis_path, "2D line graphs")
            os.makedirs(save_folder, exist_ok=True)
            
            base_name = title.replace(" ", "_")
            ext = f".png"
            file_name = f"{base_name}_{1}{ext}"
            self.video_filepath = os.path.join(save_folder, file_name)
            
            # Check whether there already exists output_1 in the folder, if it doesn't exist output_1, it create output_2
            i = 1
            while True:
                file_name = f"{base_name}_{i}{ext}"
                self.video_filepath = os.path.join(save_folder, file_name)
                if not os.path.exists(self.video_filepath):
                    break
                i += 1
            # file_name = f"{title}.png".replace(" ", "_") # Format the file name
            # full_path = save_folder + "\\" + file_name
            full_path = self.video_filepath

            img = self.plot.plot_widget.grab()  # Capture the plot as an image
            img.save(full_path, "PNG")  # Format of the image
            QMessageBox.information(self, "Success", f"Plot saved successfully as {file_name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occured while saving the plot : {e}")


class Point3D:
    """Contiens all coordinates of a point in 3D for each frames
    Args:
    X (np.ndarray) : 1D array-like of X coordinates
    Y (np.ndarray) : 1D array-like of Y coordinates
    Z (np.ndarray) : 1D array-like of Z coordinates

    fill a line with np.nan if the point is not visible at the current frame"""

    def __init__(self, X:np.ndarray, Y:np.ndarray, Z:np.ndarray, label:str=None):
        """/!\ X, Y and Z are 1D array-like"""
        assert len(X) == len(Y) == len(Z), "X, Y and Z must have the same length"

        self.X, self.Y, self.Z = X, Y, Z
        # self.x_proj, self.y_proj = None, None #2D coordinates of the point projected on the screen for one frame
        self.clicked = False #set to True if the point is clicked by the user. 
        self.label = label #label to display when the point is clicked, used also for naming points in auto titled plots

    def coordinate_at_frame(self, current_index:int):
        """Return the coordinates of the point at the current frame as a tuple (x, y, z), tuple of (nan, nan, nan) if the point is not visible at the current frame"""
        assert current_index >= 0, "current_index must be positive"
        if current_index < len(self.X):
            return self.X[current_index], self.Y[current_index], self.Z[current_index]
        return (np.nan, np.nan, np.nan) #return nan if the point is not visible at the current frame
    


class PlotManager(QWidget):
    """PlotManager class to manage MULTIPLES 2D plots in a scroll area
    Args:
    timeline_manager (TimelineManager) : The timeline manager to control ALL the plots, /!\ only one timeline manager for all the plots"""

    def __init__(self, timeline_manager:TimelineManager, csv_path:str, points:List[Point3D]):
        super().__init__()

        #cste
        self.FUNC_LIST:List[str] = ["Distance(select only 2 points)", "Angle(select only 3 points)", "X_value", "Y_value", "Z_value"] #All the functions that can be plotted

        #class attributes setup
        self.timeline_manager = timeline_manager

        self.csv_path:str = csv_path
        self.points_render_3D = points #to know what points are clicked in the 3D render

        #main layout
        self.layout =QVBoxLayout()

        #scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: #000000;")

        self.plot_widget = QWidget()
        self.plot_layout = QVBoxLayout()
        self.plot_widget.setLayout(self.plot_layout)
        self.scroll_area.setWidget(self.plot_widget)
        self.layout.addWidget(self.scroll_area)

        #button and combo box
        self.plot_combo_box = QComboBox()
        for func in self.FUNC_LIST : self.plot_combo_box.addItem(func)

        self.add_plot_button = QPushButton("Add Plot")
        self.add_plot_button.clicked.connect(self.add_plot)


        self.layout.addWidget(self.plot_combo_box)
        self.layout.addWidget(self.add_plot_button)

        self.setLayout(self.layout)


    def add_plot(self): #! Modify this function to add a new type of plot
        """Add a new plot to the scroll area
        /!\ Modify this function to add a new type of plot"""

        functionnality = self.plot_combo_box.currentText()
        points_to_plot = [pts for pts in self.points_render_3D if pts.clicked]

        if functionnality == "Distance(select only 2 points)" and len(points_to_plot) == 2:
            distance = self.distance_points(points_to_plot[0], points_to_plot[1])
            title = f"Distance {points_to_plot[0].label} - {points_to_plot[1].label}"
            print(title)
            # check whether there already exists the same title's 2D graphe
            for i in range(self.plot_layout.count()):
                existing_plot = self.plot_layout.itemAt(i).widget()
                if existing_plot.windowTitle() == title:
                    print("This 2D graph already exists")
                    QMessageBox.warning(self, "Error", "This 2D graph already exists")
                    return
            new_plot = Plot2D_With_Buttons(self.timeline_manager, self.csv_path, distance, framerate = 30, title=f"Distance {points_to_plot[0].label} - {points_to_plot[1].label}", Y_units="mm", Y_title="Distance")
            new_plot.setMinimumHeight(200)
            new_plot.setWindowTitle(title)
            self.plot_layout.addWidget(new_plot)
        if functionnality == "Distance(select only 2 points)" and len(points_to_plot) != 2:
            QMessageBox.warning(self, "Error", "To draw the 'Distance' 2D graph, you should only select 2 points")


        if functionnality == "Angle(select only 3 points)" and len(points_to_plot) == 3:
            angle = self.angle_points(points_to_plot[0], points_to_plot[1], points_to_plot[2])
            title = f"Angle {points_to_plot[1].label} - {points_to_plot[0].label} - {points_to_plot[2].label}"
            print(title)
            # check whether there already exists the same title's 2D graphe
            for i in range(self.plot_layout.count()):
                existing_plot = self.plot_layout.itemAt(i).widget()
                if existing_plot.windowTitle() == title:
                    print("This 2D graph already exists")
                    QMessageBox.warning(self, "Error", "This 2D graph already exists")
                    return
            new_plot = Plot2D_With_Buttons(self.timeline_manager, self.csv_path, angle, framerate = 30, title=f"Angle {points_to_plot[1].label} - {points_to_plot[0].label} - {points_to_plot[2].label}", Y_units="degrees", Y_title="Flexion angle (0° = extension)")
            new_plot.setMinimumHeight(200)
            new_plot.setWindowTitle(title)
            self.plot_layout.addWidget(new_plot)
        if functionnality == "Angle(select only 3 points)" and len(points_to_plot) != 3:
            QMessageBox.warning(self, "Error", "To draw the 'Angle' 2D graph, you should only select 3 points")

        if functionnality == "X_value" and len(points_to_plot) != 0:
            for point in points_to_plot:
                new_plot = Plot2D_With_Buttons(self.timeline_manager, self.csv_path, point.X, framerate = 30, title=f"X value {point.label}", Y_units="mm", Y_title="X value")
                new_plot.setMinimumHeight(200)
                self.plot_layout.addWidget(new_plot)

        if functionnality == "Y_value" and len(points_to_plot) != 0:
            for point in points_to_plot:
                new_plot = Plot2D_With_Buttons(self.timeline_manager, self.csv_path, point.Y, framerate = 30, title=f"Y value {point.label}", Y_units="mm", Y_title="Y value")
                new_plot.setMinimumHeight(200)
                self.plot_layout.addWidget(new_plot)

        if functionnality == "Z_value" and len(points_to_plot) != 0:
            for point in points_to_plot:
                new_plot = Plot2D_With_Buttons(self.timeline_manager, self.csv_path, point.Z, framerate = 30, title=f"Z value {point.label}", Y_units="mm", Y_title="Z value")
                new_plot.setMinimumHeight(200)
                self.plot_layout.addWidget(new_plot)




    def distance_points(self, pt1:Point3D, pt2:Point3D):
        """Compute the distance between two points in 3D"""
        return np.sqrt((pt1.X - pt2.X)**2 + (pt1.Y - pt2.Y)**2 + (pt1.Z - pt2.Z)**2)

    def angle_points(self, origin: Point3D, pt2: Point3D, pt3: Point3D) -> np.ndarray:
        """
        Calcule l'angle entre trois points dans un espace 3D, pour chaque instant t.
        :param origin: Point3D représentant l'origine des deux vecteurs.
        :param pt2: Point3D représentant l'extrémité du premier vecteur.
        :param pt3: Point3D représentant l'extrémité du second vecteur.
        :return: Tableau numpy contenant les angles (en degrés) pour chaque instant t.
        """
        # Calcul des vecteurs v1 et v2 à chaque instant
        v1 = np.stack([pt2.X - origin.X, pt2.Y - origin.Y, pt2.Z - origin.Z], axis=1)  # Shape: (N, 3)
        v2 = np.stack([pt3.X - origin.X, pt3.Y - origin.Y, pt3.Z - origin.Z], axis=1)  # Shape: (N, 3)

        # Normes des vecteurs
        norm_v1 = np.linalg.norm(v1, axis=1)  # Shape: (N,)
        norm_v2 = np.linalg.norm(v2, axis=1)  # Shape: (N,)

        # Vérification pour éviter les divisions par zéro (vecteurs de norme nulle)
        zero_norms = (norm_v1 == 0) | (norm_v2 == 0)
        if np.any(zero_norms):
            raise ValueError("One or more vectors have zero length at some time steps.")

        # Produit scalaire entre les vecteurs à chaque instant
        dot_product = np.sum(v1 * v2, axis=1)  # Shape: (N,)

        # Calcul du cosinus de l'angle, en s'assurant qu'il est dans [-1, 1]
        cos_angle = np.clip(dot_product / (norm_v1 * norm_v2), -1.0, 1.0)  # Shape: (N,)

        # Calcul des angles en radians puis conversion en degrés
        angle_rad = np.arccos(cos_angle)  # Shape: (N,)
        angles_deg = np.degrees(angle_rad)  # Shape: (N,)

        return angles_deg









class Camera3D:
    """Contiens the coordinates of a camera and the orientation of the camera in 3D, this values are constant for all frames
    Args:
    T : np.ndarray : 1D array-like of the camera coordinates [x, y, z]
    R : np.ndarray : 2D array-like of the camera orientation matrix"""

    def __init__(self, T:np.ndarray, R:np.ndarray, size:int=50):
        self.center = T
        self.size = size
        self.R = R




class Render3D(QWidget):
    """Render3D class to display a 3D animation in real time
    Args:
    timeline_manager (TimelineManager) : The timeline manager to control the plot (can be the same as the 2D plots)
    Y_data : (List[Point3D]) The data to display
    framerate : (int > 0) The number of frames per second, default is 30"""
    def __init__(self, timeline_manager, project_path, Y_data: List[Point3D],Cams: List[Camera3D] = None, framerate: int = 120):
        super().__init__()

        # Arguments validation
        assert isinstance(timeline_manager, TimelineManager), "timeline_manager must be a TimelineManager object"
        assert isinstance(Y_data, list), "Y must be a list of Point3D objects"
        assert type(framerate) == int, "framerate must be an integer"
        assert framerate > 0, "framerate must be positive"

        self.project_path = project_path
        # Class attributes setup
        self.Y = Y_data  # list of points objects
        self.max_frame = max(len(point.X) for point in self.Y)  # max number of frames
        self.Cams = Cams

        self.framerate = framerate
        self.time_per_frame = 1000 // framerate  # Time in milliseconds for each frame
        self.current_index = 0

        # self.is_paused = False
        self.is_looping = True
        self.saving = False

        original_path = os.path.normpath(self.project_path)    #exemple: D:\Users\Etudiant\Documents\MoCapIA4\mocapia_3\TestProject\MoCap_Demo5\analysis\Capture 1\Capture 1_3D_points_.csv
        target_folder = "analysis"
        parts = original_path.split(os.sep)
        if target_folder in parts:
            index = parts.index(target_folder)
            before_analysis_path = os.sep.join(parts[:index])    #D:\Users\Etudiant\Documents\MoCapIA4\mocapia_3\TestProject\MoCap_Demo5
        else:
            print("Target folder not found in path.")
        # self.save_path = r"D:\Users\Etudiant\Documents\MoCapIA3\MocapIA_3\TestProject\Test_Calibration\analysis\capture_test" #! Change this path to save the video in another folder
        before_analysis_path = os.getcwd()
        self.save_path = os.path.join(before_analysis_path, "3D model video")
        os.makedirs(self.save_path, exist_ok=True)

        #main layout
        layout = QVBoxLayout(self)
        self.setFixedSize(750, 500)

        # Create a 3D widget
        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor('black')
        grid_size = self.get_grid_size()
        self.view.setWindowTitle('Affichage 3D en temps réel')
        self.view.setCameraPosition(distance=np.sqrt(3*float(grid_size)**2)*2)
        layout.addWidget(self.view)

        #!---------- ADD GRID TO 3D PLOT ----------!#
        gz = gl.GLGridItem()
        gz.translate(grid_size//2, grid_size//2, 0)
        gz.setSize(grid_size, grid_size)
        gz.setSpacing(grid_size//20, grid_size//20)
        self.view.addItem(gz)

        gz = gl.GLGridItem()
        gz.translate(grid_size//2, -grid_size//2, 0)
        gz.setSize(grid_size, grid_size)
        gz.setSpacing(grid_size//20, grid_size//20)
        self.view.addItem(gz)

        gz = gl.GLGridItem()
        gz.translate(-grid_size//2, grid_size//2, 0)
        gz.setSize(grid_size, grid_size)
        gz.setSpacing(grid_size//20, grid_size//20)
        self.view.addItem(gz)

        gz = gl.GLGridItem()
        gz.translate(-grid_size//2, -grid_size//2, 0)
        gz.setSize(grid_size, grid_size)
        gz.setSpacing(grid_size//20, grid_size//20)
        self.view.addItem(gz)

        #!------------------------------------------!#

        #! ---------- ADD REFERENCE AXIS TO 3D PLOT ----------!#
        axis = gl.GLAxisItem(glOptions='additive', antialias=False)
        axis.setSize(grid_size//5, grid_size//5, grid_size//5)
        self.view.addItem(axis)


        #! ---------- ADD CAMERAS TO 3D PLOT ----------!#

        # if self.Cams is not None:
        #     for cam in self.Cams:
        #         mesh = self.draw_one_cam(cam)
        #         print(type(mesh))
        #         self.view.addItem(mesh)

        if self.Cams is not None:
            for cam in self.Cams:
                self.view.addItem(self.draw_one_cam(cam))


        # Create a 3D scatter plot
        self.scatter_plot = gl.GLScatterPlotItem()
        self.view.addItem(self.scatter_plot)


        # Connect signals with the timeline manager
        timeline_manager.play_signal.connect(self.play)
        timeline_manager.pause_signal.connect(self.pause)
        timeline_manager.fast_forward_signal.connect(self.fast_forward)
        timeline_manager.rewind_signal.connect(self.rewind)
        timeline_manager.loop_signal_true.connect(self.loop_true)
        timeline_manager.loop_signal_false.connect(self.loop_false)
        # Connect mouse click event
        self.view.mousePressEvent = self.mouse_clicked

        # Create a timer to update the graph regularly
        self.timer = QTimer()
        self.timer.setInterval(self.time_per_frame)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

    @pyqtSlot()
    def update_plot(self):
        """Update the 3D plot with the next frame of data"""
        if self.current_index < self.max_frame:

            #? ---------- Calculate the trail of the main points ---------- ?#
            def calculate_trail(self, length_before=0, length_after=10):
                """Calculate the trail of the mains points"""
                trail = []
                for i in range(length_after):
                    if self.current_index - i >= 0:
                        trail +=[point.coordinate_at_frame(self.current_index - i) for point in self.Y]
                    else:
                        trail += [(np.nan, np.nan, np.nan)]
                for j in range(length_before):
                    if self.current_index + j < self.max_frame:
                        trail +=[point.coordinate_at_frame(self.current_index + j) for point in self.Y]
                    else:
                        trail += [(np.nan, np.nan, np.nan)]
                return trail

            #? ---------- Update the 3D plot ---------- ?#
            trail = calculate_trail(self)
            main_points = [point.coordinate_at_frame(self.current_index) for point in self.Y]
            points = np.array(main_points+trail, dtype=np.float32)

            colors = np.array([(1, 0, 0, 1) if point.clicked else (1, 1, 1, 1) for point in self.Y] + [(1,1,1,1) for _ in range(len(trail))])  # Update colors based on clicked state
            sizes = np.array([10 if point.clicked else 5 for point in self.Y]+[2 for _ in range(len(trail))]) # Update size based on clicked state

            self.scatter_plot.setData(pos=points, color=colors, size=sizes)
            self.current_index += 1

            joint_names = ["Nose","LEye", "REye", "LEar", "REar", "LShoulder",
            "RShoulder", "LElbow", "RElbow", "LWrist", "RWrist", "LHip", "RHip", 
            "LKnee", "RKnee", "LAnkle", "RAnkle", "Head", "Neck", "Hip", "LBigToe",
            "RBigToe", "LSmallToe", "RSmallToe", "LHeel", "RHeel"
            ]
            
            bones = [
                        ("Head", "REar"), ("Head", "LEar"),
                        ("Neck", "REar"), ("Neck", "LEar"),
                        ("RHip", "RKnee"), ("RKnee", "RAnkle"),
                        ("Neck", "LShoulder"), ("Neck", "RShoulder"),
                        ("LShoulder", "LElbow"), ("LElbow", "LWrist"),
                        ("RShoulder", "RElbow"), ("RElbow", "RWrist"),
                        ("Neck", "Hip"),
                        ("Hip", "LHip"), ("Hip", "RHip"),
                        ("LHip", "LKnee"), ("LKnee", "LAnkle"),
                        ("RHip", "RKnee"), ("RKnee", "RAnkle"),
                        ("LAnkle", "LHeel"), ("RAnkle", "RHeel"),
                        ("RBigToe", "RHeel"), ("RSmallToe", "RHeel"), ("RBigToe", "RSmallToe"),
                        ("LBigToe", "LHeel"), ("LSmallToe", "LHeel"), ("LBigToe", "LSmallToe"),
                    ]
            # refresh the new skeletal line for each frame（there we use self.lines to record line item）
            for line_item in getattr(self, 'lines', []):  # if there are old lines, remove them first
                self.view.removeItem(line_item)
            self.lines = []

            # get the current frame's coordinates（not including trail）
            joint_positions = {name: point.coordinate_at_frame(self.current_index) for name, point in zip(joint_names, self.Y)}

            for joint_a, joint_b in bones:
                if joint_a in joint_positions and joint_b in joint_positions:
                    p1 = joint_positions[joint_a]
                    p2 = joint_positions[joint_b]
                    pts = np.array([p1, p2], dtype=np.float32)
                    line = gl.GLLinePlotItem(pos=pts, color=(0, 1, 1, 1), width=2, antialias=True)
                    self.view.addItem(line)
                    self.lines.append(line)

            #? ---------- add labels to clicked points ---------- ?#

            for point in self.Y:
                if point.clicked:
                    self.label = self.draw_label(point.label, point.coordinate_at_frame(self.current_index))


            #? ---------- Save the frame as an image ---------- ?#
            if self.saving:
                self.save_frame()
        else:
            if self.is_looping:
                self.current_index = 0
            else:
                self.timer.stop()  # Stop the timer once all data is displayed


    def draw_one_cam(self, camera:Camera3D, color=(1, 0, 0, 1)):
        """Draw the camera in the 3D plot"""
        point_pos = camera.center.reshape(1, 3)
        scatter = gl.GLScatterPlotItem(pos =point_pos, color=color, size=10)
        return scatter


    @pyqtSlot()
    def play(self):
        self.timer.start(self.time_per_frame)  # Start or restart with the correct interval
        # self.is_paused = False

    @pyqtSlot()
    def pause(self):
        # self.is_paused = True
        self.timer.stop()

    @pyqtSlot()
    def fast_forward(self):
        self.current_index = min(self.current_index + self.framerate * 3, self.max_frame - 1)
        self.update_plot()

    @pyqtSlot()
    def rewind(self):
        self.current_index = max(self.current_index - self.framerate * 3, 0)
        self.update_plot()

    @pyqtSlot()
    def loop_true(self):
        self.is_looping = True

    @pyqtSlot()
    def loop_false(self):
        self.is_looping = False

    def closeEvent(self, event):
        self.view.close()
        event.accept()

    def get_grid_size(self) -> int:
        """Define a grid size for the plot, based on the maximum distances at the origin of points in Y_data"""

        max_x = max([max(point.X) for point in self.Y])
        max_y = max([max(point.Y) for point in self.Y])
        max_z = max([max(point.Z) for point in self.Y])

        return int(max(max_x, max_y, max_z))


    #! ////////////// Clickable plot ////////////// !#

    def mouse_clicked(self, event):
    # Récupère la position du clic de la souris
        mouse_x, mouse_y = event.pos().x(), event.pos().y()

        # Calcule la matrice de projection et de vue
        view_w, view_h = self.view.width(), self.view.height()
        m = self.view.projectionMatrix() * self.view.viewMatrix()
        m = np.array(m.data(), dtype=np.float32).reshape((4, 4))

        # Projette les points 3D en 2D
        one_mat = np.ones((len(self.Y), 1))
        points = np.array([point.coordinate_at_frame(self.current_index) for point in self.Y])
        points = np.concatenate((points, one_mat), axis=1)
        projected_points = np.matmul(points, m)

        # Normalise les coordonnées
        projected_points[:, :3] = projected_points[:, :3] / projected_points[:, 3].reshape(-1, 1)
        projected_2d = projected_points[:, :2]
        projected_2d[:, 0] = (projected_2d[:, 0] + 1) / 2 * view_w
        projected_2d[:, 1] = (1 - projected_2d[:, 1]) / 2 * view_h

        # Calcule la distance entre le clic et les points projetés
        distances = np.sqrt((projected_2d[:, 0] - mouse_x) ** 2 + (projected_2d[:, 1] - mouse_y) ** 2)
        min_index = np.argmin(distances)

        # Vérifie si le point est suffisamment proche pour être sélectionné
        threshold = 10  # in pixels
        if distances[min_index] < threshold:
            # Marque le point comme cliqué
            self.Y[min_index].clicked = not self.Y[min_index].clicked

        # Met à jour le graphique pour refléter l'état cliqué
        self.current_index = self.current_index-1 if self.current_index != 0 else 0# Force la mise à jour du graphique
        self.update_plot()

    #!----------SAVE A PLOT AS A VIDEO----------!#
    def save_frame(self):
        """Capture the current frame and save it as an image."""
        if not hasattr(self, 'video_writer') or not self.saving:
            return  # Do nothing if video_writer is not initialized or not saving

        img = self.view.grabFramebuffer()  # Capture the widget's image (QImage)
        img_np = img.constBits().asarray(img.byteCount())  # Get buffer
        img_np = np.array(img_np).reshape((img.height(), img.width(), 4))  # Reshape to RGBA format

        # Convert QImage (RGBA) to BGR format for OpenCV
        img_np_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)

        # Write the frame to the video
        self.video_writer.write(img_np_bgr)


    def start_saving(self, path, base_name="output", ext=".mp4"):
        """Start saving the video to the given path. (.mp4 format)"""
        self.saving = True
        self.save_path = path
        self.basename = base_name
        self.ext = ext
        self.video_filename = os.path.join(self.save_path, 'output_1.mp4')
        
        # Check whether there already exists output_1 in the folder, if it doesn't exist output_1, it create output_2
        i = 1
        while True:
            file_name = f"{base_name}_{i}{ext}"
            video_filename = os.path.join(self.save_path, file_name)
            if not os.path.exists(video_filename):
                 break
            i += 1

        # Define the codec and create VideoWriter object
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec for MP4
        # video_filename = os.path.join(self.save_path, 'output.mp4')

        # Get the widget's dimensions
        width = self.view.width()
        height = self.view.height()

        self.video_writer = cv2.VideoWriter(video_filename, fourcc, self.framerate, (width, height))

        print(f"[ANALYSIS PAGE] Started saving video to {video_filename}")

    def stop_saving(self):
        """Stop the video recording."""
        if not hasattr(self, 'video_writer'):
            return

        self.saving = False

        # Release the VideoWriter when done
        self.video_writer.release()
        del self.video_writer
        print(f"[ANALYSIS PAGE] Video saved successfully.")
    #!------------------------------------------!#

    def draw_label(self, label: str, pos: np.ndarray, color=(0, 1, 0, 1)):
        """Dessine un texte 3D à une position donnée avec une couleur spécifique."""
        # Créer une image avec PIL
        font = ImageFont.truetype("arial.ttf", 24)  # Utilisez une police existante sur votre système
        bbox = font.getbbox(label)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        image = Image.new("RGBA", (text_width, text_height), color)
        draw = ImageDraw.Draw(image)

        # Convertir la couleur OpenGL (R, G, B, A) en valeurs PIL (R, G, B, A, multipliées par 255)
        pil_color = tuple(int(c * 255) for c in color)

        # Dessiner le texte
        draw.text((0, 0), label, font=font, fill=pil_color)

        # Convertir l'image en texture OpenGL
        texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        image_data = image.tobytes("raw", "RGBA", 0, -1)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, image.width, image.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, image_data)

        # Dessiner la texture sur un quadrilatère 3D
        glEnable(GL_TEXTURE_2D)
        glColor4f(1, 1, 1, 1)  # Couleur blanche pour afficher la texture sans teinte
        glPushMatrix()
        glTranslatef(pos[0], pos[1], pos[2])  # Positionner le texte
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0)
        glVertex3f(0, 0, 0)
        glTexCoord2f(1, 0)
        glVertex3f(text_width / 100, 0, 0)  # Échelle à ajuster si nécessaire
        glTexCoord2f(1, 1)
        glVertex3f(text_width / 100, text_height / 100, 0)
        glTexCoord2f(0, 1)
        glVertex3f(0, text_height / 100, 0)
        glEnd()
        glPopMatrix()

        glDisable(GL_TEXTURE_2D)
        glDeleteTextures(1, [texture_id])





class Render3D_With_Buttons(QWidget):
    """ QWidget that contains a Render3D object and buttons to save the video in a grid layout
    Args:
    Same as Render3D class"""

    def __init__(self,timeline_manager:TimelineManager, project_path, Y_data: List[Point3D], framerate: int = 120):
        super().__init__()

        #class init
        self.timeline_manager = timeline_manager
        
        #project_path init
        self.project_path = project_path
        
        #Y_data init
        self.Y_data = Y_data
        
        #framerate init
        self.framerate = framerate

        #main layout of the widget
        self.layout = QGridLayout()

        #add Render3D object(not created yet)
        self.render3d = None
        
        # spy the 'play_signal'，touch the creation of Render3D
        # self.timeline_manager.play_signal.connect(self.create_render3d)
        
        #add Render3D object
        self.render3d = Render3D(timeline_manager, project_path, Y_data, framerate=framerate)
        self.render3d.setFixedSize(750, 700)
        self.layout.addWidget(self.render3d, 0, 0, 50, 50)

        #save button
        self.save_button = QPushButton(QIcon(r"Ui\assets\save.svg"), "")
        self.save_button.setFixedSize(30, 30)
        self.save_button.setStyleSheet("border: none; background-color: #000000;")
        self.save_button.setToolTip("Save Video")
        self.save_button.setCheckable(True)
        self.save_button.setChecked(False)
        self.save_button.clicked.connect(self.save_button_clicked)
        self.layout.addWidget(self.save_button, 1, 48, 1, 1)

        #save_recording indicator
        self.recording_indicator = RecordingIndicator()
        self.layout.addWidget(self.recording_indicator, 1, 47, 1, 1)

        self.setLayout(self.layout)

            
    def save_button_clicked(self):
        """Start or stop saving the video when the save button is clicked"""
        if self.save_button.isChecked():
            self.render3d.start_saving(self.render3d.save_path)
            self.recording_indicator.start_blinking()
        else:
            self.render3d.stop_saving()
            self.recording_indicator.stop_blinking()





#* ---------- TESTS ---------- *#


if __name__ == "__main__":
    from Pose_Estimation.csv_reader import CSVReader
    project_path = r"D:\Users\Etudiant\Documents\MoCapIA4\mocapia_3\TestProject\MoCap_Demo5\analysis\Capture 1\Capture 1_3D_points.csv"
    # csv_reading = CSVReader(r"D:\Users\Etudiant\Documents\MoCapIA3\MocapIA_3\TestProject\ViconProject\analysis\capture_1\capture_1_3D_points_.csv", skiprows=2)
    csv_reading = CSVReader(r"D:\Users\Etudiant\Documents\MoCapIA4\mocapia_3\TestProject\MoCap_Demo5\analysis\Capture 1\Capture 1_3D_points.csv", skiprows=2)
    point_to_plot = csv_reading.convert_csv_to_point3D(["Nose",
        "LEye", "REye", "LEar", "REar", "LShoulder", "RShoulder",
        "LElbow", "RElbow", "LWrist", "RWrist", "LHip", "RHip", "LKnee",
        "RKnee", "LAnkle", "RAnkle", "Head", "Neck", "Hip", "LBigToe",
        "RBigToe", "LSmallToe", "RSmallToe", "LHeel", "RHeel"
    ], T = np.array([[0.84069,   -0.087192,     0.53446,     -1470.1],[-0.54102,    -0.17749,     0.82206,     -1444.8],[0.023184,    -0.98025,    -0.19639,      1205.9],[0, 0, 0, 1]]))


    app = QApplication(sys.argv)
    timeline_manager = TimelineManager()
    render3d = Render3D(timeline_manager,project_path, point_to_plot, framerate=30)
    render3d.show()
    sys.exit(app.exec_())