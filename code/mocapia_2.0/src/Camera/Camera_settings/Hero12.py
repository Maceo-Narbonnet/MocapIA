#this file contains informations and settings to control the GoPro Hero12 camera

from enum import Enum
from typing import final
#! API status codes for GoPro12 cameras
class StatusCode(Enum):
    """Non exhaustive list of status codes for GoPro Hero12 cameras."""
    BatteryPresent = "1"
    InternalBatteryBars = "2"
    Overheating ="6"
    Busy = "8"
    QuickCapture= "9"
    Encoding = "10"
    LCDLock = "11"
    VideoEncodingDuration = "13"
    WirelessConnectionsEnabled = "17"
    PairingState = "19"
    LastPairingType = "20"
    WifiScanState = "22"
    LastWifiScanSucess = "23"
    WifiProvisioningState = "24"
    RemoteConnected = "27"
    AP_SSID = "29"
    WiFi_SSID = "30"
    ConnectedDevices = "31"
    PreviewStream = "32"
    PrimaryStorage = "33"
    RemainingPhotos = "34"
    RemainingVideoTime = "35"
    Photos = "38"
    Video = "39"
    OTA = "41"
    PendingFWUpdateCancel = "42"
    Locate = "45"
    TimelapseIntervalCountdown = "49"
    SDCardRemaining = "54"
    PreviewStreamAvailable = "55"
    WifiBars = "56"
    ActiveHilights = "58"
    TimeSinceLastHilight = "59"
    MinimumStatusPollPeriod = "60"
    LiveviewExposureSelectMode = "65"
    LiveviewY = "66"
    LiveviewX = "67"
    GPSLock = "68"
    APMode = "69"
    InternalBatteryPercentage = "70"
    MicrophoneAccessory = "74"
    ZoomLevel = "75"
    WirelessBand = "76"
    ZoomAvailable = "77"
    MobileFriendly = "78"
    FTU = "79"
    _5GHZAvailable = "81"
    Ready = "82"
    OTACharged = "83"
    Cold = "85"
    Rotation = "86"
    ZoomWhileEncoding = "88"
    Fatmode = "89"
    VideoPreset = "93"
    PhotoPreset = "94"
    TimeLapsePreset = "95"
    PresetGroup = "96"
    Preset = "97"
    PresetModified = "98"
    CaptureDelayActive = "101"
    MediaModState = "102"
    TimeWarpSpeed = "103"
    LensType = "105"
    Hindsight = "106"
    ScheduledCapturePresetID = "107"
    ScheduledCapture = "108"
    DisplayModStatus = "110"
    SDCardWriteSpeedError = "111"
    SDCardErrors = "112"
    TurboTransfer = "113"
    CameraControlID = "114"
    USBConnected = "115"
    USBControlled = "116"
    SDCardCapacity = "117"
    PhotoIntervalCaptureCount = "118"

class SettingsCode(Enum):
    """Settings code for GoPro cameras."""
    VIDEO_RESOLUTION = "2"
    VIDEO_FPS = "3"
    VIDEO_LENS = "121"
    HYPERSMOOTH = "135"

class BatteryLevel(Enum):
    ZERO = 0
    ONE = 1
    TWO = 2
    THREE = 3
    CHARGING = 4
    NO_BATTERY = 5

class Resolutions(Enum):
    """Resolutions available for GoPro cameras."""
    R4K = 1
    R2K7 = 4
    R1080 = 9
    R4K_4_3 = 18
    R5K7 = 100
    R5K3_8_7 = 107
    R4K_8_7 = 108
    R4K_9_16 = 109
    R1080_9_16 = 110
    R2K7_4_3 = 111

class DigitalLenses(Enum):
    """Digital lenses available for GoPro cameras."""
    WIDE = 0
    SUPERVIEW = 3
    LINEAR = 4
    NARROW = 2

class VideoLength(Enum):
    """Video length available for GoPro cameras."""
    WIDE = 0
    NARROW = 2
    SUPERVIEW = 3
    LINEAR = 4
    MAX_SUPERVIEW = 7
    LINEAR_HORIZONLEVELING = 8
    HYPERVIEW = 9
    LINEAR_HORIZONLOCK = 10
    MAX_HYPERVIEW = 11

class VideoBitrate(Enum):
    """Video bitrate available for GoPro cameras."""
    STANDARD = 0
    HIGH = 1

class VideoAspectRatio(Enum):
    """Video aspect ratio available for GoPro cameras."""
    R16_9 = 1
    R4_3 = 0
    R8_7 = 3
    R9_16 = 4

class ColorProfile(Enum):
    STANDARD = 0
    HDR = 1
    LOG = 2

class HyperSmooth(Enum):
    OFF = 0
    LOW = 1
    AUTOBOOST = 3

class FrameRate(Enum):
    FPS240 = 0
    FPS120 = 1
    FPS100 = 2
    FPS60 = 5
    FPS50 = 6
    FPS30 = 8
    FPS25 = 9
    FPS24 = 10
    FPS200 = 13

#! Settings compatibility
AVAILABLE_RESOLUTIONS : final = ["1080p", "2.7K", "4K", "5.3K"]
AVAILABLE_FPS : final = ["24", "30", "60", "120", "240"]
AVAILABLE_FOV : final = ["Linear+","Linear", "Wide", "SuperView", "HyperView"]

resolution_to_enum : final = {"1080p": Resolutions.R1080, "2.7K": Resolutions.R2K7, "4K": Resolutions.R4K, "5.3K": Resolutions.R5K7}
fps_to_enum : final = {"24": FrameRate.FPS24, "30": FrameRate.FPS30, "60": FrameRate.FPS60, "120": FrameRate.FPS120, "240": FrameRate.FPS240}
fov_to_enum : final = {"Linear+": VideoLength.LINEAR_HORIZONLEVELING, "Linear": VideoLength.LINEAR, "Wide": VideoLength.WIDE, "SuperView": VideoLength.SUPERVIEW, "HyperView": VideoLength.HYPERVIEW}

#this class is used to store the compatible settings for each resolution and frame rate
COMPATIBLE_SETTINGS : final = { 
    "1080p": {
        "24": ["Linear+","Linear", "Wide", "SuperView"],
        "30": ["Linear+","Linear", "Wide", "SuperView"],
        "60": ["Linear+","Linear", "Wide", "SuperView"],
        "120": ["Linear+","Linear", "Wide", "SuperView"],
        "240": ["Linear+","Linear", "Wide"]
    },
    "2.7K": {
        "240": ["Linear+","Linear", "Wide"]
    },
    "4K": {
        "24": ["Linear+","Linear", "Wide", "SuperView", "HyperView"],
        "30": ["Linear+","Linear", "Wide", "SuperView", "HyperView"],
        "60": ["Linear+","Linear", "Wide", "SuperView", "HyperView"],
        "120": ["Linear+","Linear", "Wide", "SuperView"]
    },
    "5.3K": {
        "24": ["Linear+","Linear", "Wide", "SuperView", "HyperView"],
        "30": ["Linear+","Linear", "Wide", "SuperView", "HyperView"],
        "60": ["Linear+","Linear", "Wide", "SuperView"],
    }
}