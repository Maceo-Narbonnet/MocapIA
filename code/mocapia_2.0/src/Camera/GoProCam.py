"""Utilities to control a GoPro camera over the OpenGoPro HTTP API.
Requires the camera to be in GoPro Connect (not MTP).

Doc: https://gopro.github.io/OpenGoPro/
"""
import os
import time as t
from typing import Union, Dict, Tuple
from enum import Enum as _Enum
from urllib.parse import urlparse

import requests
from Camera.Camera_settings import Hero12
import json
import re


class GoProCam:
    """
    Wrapper around OpenGoPro endpoints.

    identifier can be:
      - '172.24.153.51:8080'  (preferred)  -> direct HTTP base
      - ('C3501325621627','Default')       -> (serial, profile); will require a serial->ip mapping
      - 'C3501325621627'                   -> serial; will require a serial->ip mapping
    """

    def __init__(self, identifier: Union[str, Tuple[str, str]]):
        self.gopro_ip = self._resolve_http_base(identifier)  # like '172.24.153.51:8080'
        self.wifi_ip = "10.5.5.9:8080"  # fallback Wi-Fi control base if ever needed

    # -------------------------- helpers --------------------------

    @staticmethod
    def _looks_like_ip_port(value: str) -> bool:
        return isinstance(value, str) and (value.count(".") >= 3 or ":" in value)

    def _resolve_http_base(self, identifier: Union[str, Tuple[str, str]]) -> str:
        # 1) 直接传了 'ip:port'
        if isinstance(identifier, str) and self._looks_like_ip_port(identifier):
            return identifier

        # 2) tuple/list -> 取 serial；或者就是单串 serial
        if isinstance(identifier, (tuple, list)) and len(identifier) >= 1:
            serial = identifier[0]
        elif isinstance(identifier, str):
            serial = identifier
        else:
            raise ValueError(f"Unsupported identifier type: {type(identifier)}")

        # —— 新增：优先从 status.json 解析
        ip_from_status = self._ip_from_status(serial)
        if ip_from_status:
            return ip_from_status

        # —— 然后才尝试环境变量
        env_key = f"GOPRO_IP_{serial}"
        http_base = os.environ.get(env_key) or os.environ.get("GOPRO_HTTP_BASE")
        if http_base:
            return http_base

        # —— 最后兜底：使用你原工程里“根据序列号末三位推 IP”的规则（尽量稳妥）
        digits = "".join(ch for ch in serial if ch.isdigit())
        if len(digits) >= 3:
            a, b, c = digits[-3], digits[-2], digits[-1]
            guess = f"172.2{a}.1{b}{c}.51:8080"
            print(f"[WARN] No mapping found for {serial}. Falling back to guessed IP: {guess}")
            return guess

        # 还是不行，就报错（极端情况）
        raise RuntimeError(
            f"No IP mapping for serial '{serial}'. "
            f"Provide an explicit 'ip:port' or set env 'GOPRO_IP_{serial}' or 'GOPRO_HTTP_BASE'."
        )
    
    def _ip_from_status(self, serial: str) -> str:
        """
        在项目的 status.json 里查找 serial 对应的 IP。
        如果找到且没带端口，默认补 :8080。
        找不到返回 None。
        """
        try:
            # GoProCam.py 位于 src/Camera/，status.json 通常在 src/config/Settings/status.json
            status_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "config", "Settings", "status.json")
            )
            if not os.path.exists(status_path):
                return None

            with open(status_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            def walks(obj):
                # 递归搜索：字典/列表中成对出现的 serial + ip
                if isinstance(obj, dict):
                    found_serial = None
                    found_ip = None
                    for k, v in obj.items():
                        lk = str(k).lower()
                        if lk in ("serial", "serial_number", "sn", "id"):
                            if isinstance(v, str) and serial == v:
                                found_serial = v
                        if lk in ("ip", "gopro_ip", "http_ip", "address"):
                            if isinstance(v, str) and re.match(r"^\d+\.\d+\.\d+\.\d+(?::\d+)?$", v):
                                found_ip = v
                    if found_serial and found_ip:
                        return found_ip
                    # 继续递归子结构
                    for v in obj.values():
                        res = walks(v)
                        if res:
                            return res

                elif isinstance(obj, list):
                    for it in obj:
                        res = walks(it)
                        if res:
                            return res
                return None

            ip = walks(data)
            if ip and ":" not in ip:
                ip = ip + ":8080"
            return ip
        except Exception:
            return None


    @property
    def http_base(self) -> str:
        return f"http://{self.gopro_ip}"

    @property
    def host_only(self) -> str:
        """Extract '172.24.153.51' from '172.24.153.51:8080'."""
        return self.gopro_ip.split(":")[0]

    # ---------------------- connection management ----------------------

    def connect(self) -> bool:
        """Try to connect; return True if successful."""
        url = f"{self.http_base}/gp/gpControl/status"
        try:
            r = requests.get(url, timeout=2.0)
            if r.status_code == 200:
                print(f"GoPro est connectée!  Gopro ip : {self.gopro_ip}")
                return True
            print(f"Erreur de connexion: {r.status_code}")
            return False
        except requests.exceptions.RequestException as e:
            print(f"Erreur de connexion à la GoPro: {e}")
            return False

    def wait_until_ready(self):
        while self.get_status(Hero12.StatusCode.Busy) == 1:
            print("Waiting for the camera...")
            t.sleep(0.2)

    def enable_wired_control(self):
        r1 = requests.get(f"{self.http_base}/gopro/camera/control/wired_usb", params={"p": "1"})
        print(r1.status_code)
        r2 = requests.get(f"{self.http_base}/gopro/camera/control/set_ui_controller", params={"p": "2"})
        print(r2.status_code)
        if r1.status_code != 200 or r2.status_code != 200:
            raise ValueError(f"enable_wired_control failed: {r1.status_code} {r2.status_code}")

    def disable_wired_control(self):
        r1 = requests.get(f"{self.http_base}/gopro/camera/control/wired_usb", params={"p": "0"})
        r2 = requests.get(f"{self.http_base}/gopro/camera/control/set_ui_controller", params={"p": "0"})
        if r1.status_code != 200 or r2.status_code != 200:
            raise ValueError(f"disable_wired_control failed: {r1.status_code} {r2.status_code}")

    # --------------------------- media ops ---------------------------

    def _state_json(self) -> dict:
        return requests.get(f"{self.http_base}/gopro/camera/state").json()

    def check_number_of_files(self) -> int:
        media_list = requests.get(f"{self.http_base}/gopro/media/list").json()
        return len(media_list["media"][0]["fs"])

    def download_media(self, media_name: str, path: str) -> None:
        r = requests.get(f"{self.http_base}/videos/DCIM/100GOPRO/{media_name}")
        if r.status_code == 200:
            os.makedirs(path, exist_ok=True)
            full_path = os.path.join(path, media_name)
            with open(full_path, "wb") as f:
                f.write(r.content)
            print(f"Media {media_name} downloaded successfully -> {full_path}")
        else:
            print(f"Error while downloading {media_name}: {r.status_code}")

    def save_last_media(self, path: str) -> None:
        try:
            media_list = requests.get(f"{self.http_base}/gopro/media/list").json()
            last_media_name = media_list["media"][0]["fs"][-1]["n"]
            if last_media_name:
                self.download_media(last_media_name, path)
            else:
                raise ValueError("No last media name.")
        except Exception as e:
            print(f"save_last_media error: {e}")

    def save_all_media(self, path: str) -> None:
        try:
            media_list = requests.get(f"{self.http_base}/gopro/media/list").json()
            for media in media_list["media"][0]["fs"]:
                self.download_media(media["n"], path)
        except Exception as e:
            raise ValueError(f"save_all_media error: {e}")

    def delete_all_files(self):
        r = requests.get(f"{self.http_base}/gp/gpControl/command/storage/delete/all")
        if r.status_code != 200:
            raise ValueError(f"delete_all_files failed: {r.status_code}")

    # --------------------------- capture ops ---------------------------

    def start_video(self):
        r = requests.get(f"{self.http_base}/gopro/camera/shutter/start")
        print("start_video:", r.status_code, r.text)

    def stop_video(self):
        r = requests.get(f"{self.http_base}/gopro/camera/shutter/stop")
        print("stop_video:", r.status_code, r.text)

    def take_video(self, duration: int):
        assert isinstance(duration, int)
        self.wait_until_ready()
        self.start_video()
        t.sleep(duration)
        self.stop_video()

    def take_and_download_video(self, duration: int, path: str):
        assert isinstance(duration, int)
        self.disable_wired_control()
        self.wait_until_ready()
        self.enable_wired_control()
        self.wait_until_ready()
        self.take_video(duration)
        self.wait_until_ready()
        self.save_last_media(path)

    # --------------------------- webcam / rtsp ---------------------------

    def webcam_mode(self):
        r = requests.get(f"{self.http_base}/gopro/webcam/preview")
        if r.status_code != 200:
            raise ValueError(f"webcam_mode failed: {r.status_code}")

    def webcam_mode_exit(self):
        r = requests.get(f"{self.http_base}/gopro/webcam/exit")
        if r.status_code != 200:
            raise ValueError(f"webcam_mode_exit failed: {r.status_code}")

    def start_webcam(self, port: int = 8556) -> bool:
        """Start RTSP stream on given port (default 8556)."""
        url = f"{self.http_base}/gopro/webcam/start"
        params = {"res": "12", "fov": "4", "port": str(port), "protocol": "RTSP"}
        r = requests.get(url, params=params)
        if r.status_code == 200:
            print(f"Webcam RTSP démarrée avec succès sur le port {port}.")
            return True
        print(f"Erreur démarrage webcam RTSP: {r.status_code}, {r.text}")
        return False

    def stop_webcam(self):
        r = requests.get(f"{self.http_base}/gopro/webcam/stop")
        print("stop_webcam:", r.status_code, r.text)

    def is_streaming(self) -> bool:
        state = self._state_json()
        return str(state["status"].get("32", "0")) == "1"

    # --------------------------- settings / status ---------------------------

    def get_setting(self, setting_enum_object: Hero12.SettingsCode) -> int:
        setting_code = setting_enum_object.value
        state = self._state_json()
        try:
            return state["settings"][setting_code]
        except KeyError:
            print(f"get_setting: key {setting_code} not found.")

    def set_setting(self, setting_enum_object: Hero12.SettingsCode, setting_value: Union[int, _Enum]) -> None:
        if isinstance(setting_value, int):
            params = {"option": setting_value, "setting": setting_enum_object.value}
        else:
            params = {"option": setting_value.value, "setting": setting_enum_object.value}
        r = requests.get(f"{self.http_base}/gopro/camera/setting", params=params)
        if r.status_code == 403:
            raise ValueError(f"set_setting forbidden: {r.text}")
        elif r.status_code != 200:
            raise ValueError(f"set_setting error: {r.status_code}")

    def get_battery_level(self) -> Hero12.BatteryLevel:
        state = self._state_json()
        if state["status"]["1"] == 0:
            return Hero12.BatteryLevel.NO_BATTERY
        return Hero12.BatteryLevel(state["status"]["2"])

    def get_model(self):
        return requests.get(f"{self.http_base}/gopro/camera/info").json()["model_name"]

    def get_status(self, param: Hero12.StatusCode):
        assert isinstance(param, Hero12.StatusCode)
        return self._state_json()["status"][param.value]
