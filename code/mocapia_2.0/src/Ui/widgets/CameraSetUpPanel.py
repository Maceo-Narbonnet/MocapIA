# Ui/widgets/CameraSetupPanel.py
from typing import Dict, List, Any
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QHBoxLayout, QVBoxLayout, QLabel,
    QCheckBox, QComboBox, QSizePolicy, QPushButton, QMessageBox
)
import os, sys, contextlib

@contextlib.contextmanager
def _suppress_output():
    devnull = open(os.devnull, 'w')
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout = devnull
        sys.stderr = devnull
        yield
    finally:
        sys.stdout = old_out
        sys.stderr = old_err
        devnull.close()
def _load_all_cameras_from_manager():
    """
    Read cameras and configurations from CameraManager.camera_data,
    compatible with both list/dict structures.
    Returns a unified structure:
    [
      {
        "name": <display name>,
        "ip":   <camera IP>,
        "configs": [ {"name": <config name>, "params": <parameters dict>}, ... ],
        "default_index": <the first index marked favorite, or 0 if none>
      },
      ...
    ]
    """

    cams = []
    try:
        with _suppress_output():
            from config.Config_Manager import CameraManager
            cm = CameraManager()
        data = getattr(cm, "camera_data", None)
        if not data:
            return cams

        # --- Case A：list ---
        if isinstance(data, list):
            for entry in data:
                ip = (entry or {}).get("ip")
                disp_name = (entry or {}).get("name") or ip or ""
                conf_list = (entry or {}).get("configurations") or []
                items = []
                default_idx = 0
                for i, conf in enumerate(conf_list):
                    conf_name = (conf or {}).get("name") or f"Config_{i+1}"
                    params = dict((conf or {}).get("parameters") or {})
                    items.append({"name": conf_name, "params": params})
                    if params.get("favorite") and default_idx == 0:
                        default_idx = i
                if not items:
                    items = [{
                        "name": "Default",
                        "params": {"resolution":"1080p","fps":"30","fov":"Linear","favorite":True,"other":{}}
                    }]
                cams.append({
                    "name": disp_name,
                    "ip": ip or "",
                    "configs": items,
                    "default_index": default_idx
                })

        # --- Case B：dict ---
        elif isinstance(data, dict):
            for ip, meta in data.items():
                disp_name = (meta or {}).get("name") or ip
                confs = (meta or {}).get("configurations") or {}
                items = []
                default_idx = 0
                if isinstance(confs, list):
                    for i, conf in enumerate(confs):
                        conf_name = (conf or {}).get("name") or f"Config_{i+1}"
                        params = dict((conf or {}).get("parameters") or {})
                        items.append({"name": conf_name, "params": params})
                        if params.get("favorite") and default_idx == 0:
                            default_idx = i
                elif isinstance(confs, dict):
                    for i, (conf_name, params) in enumerate(confs.items()):
                        params = dict(params or {})
                        items.append({"name": conf_name, "params": params})
                        if params.get("favorite") and default_idx == 0:
                            default_idx = i
                if not items:
                    items = [{
                        "name": "Default",
                        "params": {"resolution":"1080p","fps":"30","fov":"Linear","favorite":True,"other":{}}
                    }]
                cams.append({
                    "name": disp_name,
                    "ip": str(ip),
                    "configs": items,
                    "default_index": default_idx
                })

    except Exception as e:
        print(f"[WARN] CameraManager not available: {e}")
        cams = [
            {
                "name": "Camera A", "ip": "C3501350052453",
                "configs": [{"name":"Default", "params":{"resolution":"1080p","fps":"30","fov":"Linear","favorite":True,"other":{}}}],
                "default_index": 0
            }
        ]
    return cams



class _RowWidget(QWidget):
    """Visualization of one row in the list (checkbox, name/IP, config dropdown)"""
    def __init__(self, cam: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.cam = cam  

        self.chk = QCheckBox()
        self.chk.setChecked(True)

        self.lbl = QLabel(f"{cam.get('name','')}   |   IP: {cam.get('ip','')}")
        self.lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.combo = QComboBox()
        for i, conf in enumerate(cam["configs"]):
            self.combo.addItem(conf["name"], conf["params"])
        self.combo.setCurrentIndex(cam.get("default_index", 0))

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 2, 8, 2)
        lay.addWidget(self.chk)
        lay.addWidget(self.lbl, 1)
        lay.addWidget(QLabel("Config:"))
        lay.addWidget(self.combo)

    def is_enabled(self) -> bool:
        return self.chk.isChecked()

    def current_params(self) -> Dict[str, Any]:
        return dict(self.combo.currentData() or {})

    def ip(self) -> str:
        return str(self.cam.get("ip",""))

    def name(self) -> str:
        return str(self.cam.get("name", ""))

    def current_config_name(self) -> str:
        return str(self.combo.currentText() or "")


class CameraSetupPanel(QWidget):
    """
    - Left QListWidget: each row is a _RowWidget
    - get_camera_setup(): returns the camera_setup list for config.json according to current visible order
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.listw = QListWidget()
        self.listw.setSelectionMode(QListWidget.SingleSelection)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Select cameras, choose a config:"))
        lay.addWidget(self.listw, 1)

        # Load cameras
        self._populate()

    def _populate(self):
        self.listw.clear()
        cams = _load_all_cameras_from_manager()
        for cam in cams:
            item = QListWidgetItem(self.listw)
            row = _RowWidget(cam, self.listw)
            item.setSizeHint(row.sizeHint())
            self.listw.addItem(item)
            self.listw.setItemWidget(item, row)

    def get_camera_setup(self) -> List[Dict[str, Any]]:
        """
        Read current order and selections, return:
        [
          {"name":"Hero12_1","ip":"...","config_params":{"resolution":"1080p","fps":"30","fov":"Linear","favorite":true,"other":{}}},
          ...
          ]
        """
        result: List[Dict[str, Any]] = []
        for i in range(self.listw.count()):
            item = self.listw.item(i)
            row = self.listw.itemWidget(item)
            if not isinstance(row, _RowWidget):
                continue
            if not row.is_enabled():
                continue
            ip = row.ip()
            params = row.current_params() or {}
            # Ensure keys exist
            params.setdefault("resolution", "1080p")
            params.setdefault("fps", "30")
            params.setdefault("fov", "Linear")
            params.setdefault("favorite", True)
            params.setdefault("other", {})

            result.append({
                "name": row.name(),
                "ip": ip,
                "config_name": row.current_config_name(),
                "config_params": params
            })
        return result
