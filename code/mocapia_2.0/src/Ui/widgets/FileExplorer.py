import sys
from PyQt5.QtWidgets import QApplication, QTreeView, QFileSystemModel, QVBoxLayout, QWidget, QMenu, QAction, QLineEdit, QDialog, QDialogButtonBox
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtCore import Qt, QUrl, QSortFilterProxyModel
import os
import shutil

class CustomFileSystemModel(QFileSystemModel):
    """Used to add custom icons to the file explorer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setHeaderData(0, Qt.Horizontal, "")

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DecorationRole:
            file_path = self.filePath(index)
            _, extension = os.path.splitext(file_path)
            extension = extension.lower()

            # Add custom icons based on the file extension
            if extension == ".json":
                return QIcon(r"Ui\assets\json.svg")
            elif extension in [".jpg", ".jpeg", ".png", ".gif"]:
                return QIcon(r"Ui\assets\image.svg")
            elif extension == ".mp4":
                return QIcon(r"Ui\assets\video.svg")
            elif extension == ".csv":
                return QIcon(r"Ui\assets\csv.svg")
            elif extension == ".pdf":
                return QIcon(r"Ui\assets\curve.svg")

        return super().data(index, role)
    
    def flags(self, index):
        default_flags = super().flags(index)
        if index.isValid():
            return default_flags | Qt.ItemIsEditable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        return default_flags

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction

class FilterProxyModel(QSortFilterProxyModel):
    """Proxy model to filter out files with specific names."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filtered_filenames = ["config.json"]  # Files to hide

    def filterAcceptsRow(self, source_row, source_parent):
        """Filter rows based on file name."""
        index = self.sourceModel().index(source_row, 0, source_parent)
        file_name = self.sourceModel().fileName(index)
        
        # Hide files with specific names
        if file_name in self.filtered_filenames:
            return False
        return True

class RenameDialog(QDialog):
    """Dialog to rename a file."""
    def __init__(self, current_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Renommer le fichier")
        self.setFixedSize(300, 100)

        self.line_edit = QLineEdit(self)
        self.line_edit.setText(current_name)
        self.line_edit.selectAll()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.line_edit)
        layout.addWidget(buttons)

    def get_new_name(self):
        return self.line_edit.text()

class FileExplorer(QWidget):
    """Simple file explorer widget to display files and folders in a given directory."""

    def __init__(self, folder_path:str):
        super().__init__()
        self.setWindowTitle("File Explorer")
        self.setFixedWidth(250)

        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Rechercher un fichier")
        self.search_bar.textChanged.connect(self.filter_files)

        # Create a custom file system model
        self.model = CustomFileSystemModel()
        self.model.setRootPath(folder_path)
        
        # Create a filter proxy model
        self.proxy_model = FilterProxyModel()
        self.proxy_model.setSourceModel(self.model)

        # Create a tree view and set the model
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.proxy_model)

        # Set the root index to the folder path
        self.tree_view.setRootIndex(self.proxy_model.mapFromSource(self.model.index(folder_path)))

        # Set drag and drop
        self.tree_view.setDragEnabled(True)
        self.tree_view.setAcceptDrops(True)
        self.tree_view.setDropIndicatorShown(True)
        self.tree_view.setDragDropMode(QTreeView.InternalMove)

        # Hide unnecessary columns
        self.tree_view.setColumnHidden(1, True)  # Hide the "Size" column
        self.tree_view.setColumnHidden(2, True)  # Hide the "Type" column
        self.tree_view.setColumnHidden(3, True)  # Hide the "Date Modified" column

        # Layout the widgets
        layout = QVBoxLayout()
        layout.addWidget(self.search_bar)
        layout.addWidget(self.tree_view)
        self.setLayout(layout)

        # Signals and slots for context menu
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.open_context_menu)

    def open_file(self, source_index):
        """Open the selected file or folder with the default application."""
        # source_index = self.proxy_model.mapToSource(index)
        file_path = self.model.filePath(source_index)
        # print("Opening file:", file_path)
        if os.path.exists(file_path):             # os.path.isfile() can only judge the file, but os.path.exists() can judge both file and folder
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        else:
            print("Not a valid file:", file_path)

    def delete_file(self, file_path):
        """Delete the selected file."""
        if os.path.isfile(file_path) or os.path.islink(file_path):
            os.remove(file_path)
            # print("File deleted:", file_path)
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)
            # print("Directory deleted:", file_path)

    def rename_file(self, index):
        """Rename the selected file."""
        source_index = self.proxy_model.mapToSource(index)
        file_path = self.model.filePath(source_index)
        
        # Open rename dialog
        dialog = RenameDialog(os.path.basename(file_path), self)
        if dialog.exec_() == QDialog.Accepted:
            new_name = dialog.get_new_name()
            new_path = os.path.join(os.path.dirname(file_path), new_name)
            
            try:
                os.rename(file_path, new_path)  # Rename the file
                self.model.setRootPath(self.model.rootPath())  # Refresh the view
            except Exception as e:
                print(f"Error renaming file: {e}")

    def open_context_menu(self, position):
        """Open the context menu on right-click."""
        index = self.tree_view.indexAt(position)
        if not index.isValid():
            return

        source_index = self.proxy_model.mapToSource(index)
        file_path = self.model.filePath(source_index)
        menu = QMenu()

        open_action = QAction("Ouvrir", self)
        open_action.triggered.connect(lambda: self.open_file(source_index))
        menu.addAction(open_action)

        delete_action = QAction("Supprimer", self)
        delete_action.triggered.connect(lambda: self.delete_file(file_path))
        menu.addAction(delete_action)

        rename_action = QAction("Renommer", self)
        rename_action.triggered.connect(lambda: self.rename_file(index))
        menu.addAction(rename_action)
        
        copy_path_action = QAction("Copier path", self)
        copy_path_action.triggered.connect(lambda: QApplication.clipboard().setText(file_path.replace('/', '\\')))
        menu.addAction(copy_path_action)

        menu.exec_(self.tree_view.viewport().mapToGlobal(position))

    def filter_files(self, text):
        """Filter the files based on the given text."""
        self.model.setNameFilters([f"*{text}*"])
        self.model.setNameFilterDisables(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    folder_path = os.path.expanduser("~")  # Default user folder
    explorer = FileExplorer(folder_path)
    explorer.show()
    sys.exit(app.exec_())
