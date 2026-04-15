"""BLE protocol constants for DynoForce devices."""

from __future__ import annotations

from enum import IntEnum

# Nordic UART Service UUIDs
SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
COMMAND_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  # Write with response
STATE_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # Notify (force/IMU data)
INFO_UUID = "6E400004-B5A3-F393-E0A9-E50E24DCCA9E"  # Read (device info)


class Command(IntEnum):
    """BLE command opcodes sent to COMMAND_UUID."""

    TARE = 0x01
    CALIBRATE = 0x02
    SET_NAME = 0x03
    BUZZER = 0x04
    SET_INACTIVITY = 0x05
    RESET_PEAK = 0x09
    SET_TX_POWER = 0x0A


class CalibrationStatus(IntEnum):
    """Calibration state reported in extended state packets."""

    IDLE = 0
    TARE_OK = 1
    TARE_ERROR = 2
    FACTOR_OK = 3
    FACTOR_ERROR = 4


class ProductLineCode(IntEnum):
    """Product line codes from INFO characteristic byte 0."""

    DYNOGRIP_V1 = 0x01
    DYNOGRIP_PRO = 0x02
    DYNOGRIP_LITE = 0x03
    DYNOLIFT_S1 = 0x04
    DYNOLIFT_S1_LEGACY = 0x05
    DYNOPULL_T1 = 0x06
    DYNOGRIP_NRF = 0x07
    DYNOPULL_NRF = 0x08
    UNITY_COUNTER = 0x09


PRODUCT_LINE_NAMES: dict[int, str] = {
    0x01: "DynoGrip-V1",
    0x02: "DynoGrip-Pro",
    0x03: "DynoGrip-Lite",
    0x04: "DynoLift-S1",
    0x05: "DynoLift-S1",
    0x06: "DynoPull-T1",
    0x07: "DynoGrip-nRF",
    0x08: "DynoPull-nRF",
    0x09: "UnityCounter",
}


class Melody(IntEnum):
    """Predefined melody IDs for the BUZZER command."""

    NONE = 0
    BEEP = 1
    SUCCESS = 2
    FAILURE = 3
    START = 4
    STOP = 5
    REP = 6
    THRESHOLD = 7
    DROP = 8
    COUNTDOWN_3 = 9
    COUNTDOWN_BEEP = 10
    ALARM = 11
    CALIBRATION_OK = 12
    CALIBRATION_ERR = 13
    CONNECT = 14
    DISCONNECT = 15
    GAME_START = 16
    GAME_OVER = 17
    HIGHSCORE = 18
    COIN = 19
    POWER_ON = 20


class UnityCounterMode(IntEnum):
    """Active mode on UnityCounter device."""

    BOULDER = 0
    FLIP = 1
    HANDSTAND = 2
    FRONT_LEVER = 3
    REP_COUNTER = 4


class FlipType(IntEnum):
    """Flip direction type for UnityCounter."""

    FRONT = 0
    BACK = 1
    SIDE_LEFT = 2
    SIDE_RIGHT = 3


# Name prefixes used for BLE scan fallback matching (uppercase)
DEVICE_NAME_PREFIXES = (
    "DYNOGRIP",
    "DYNOPULL",
    "DYNOLIFT",
    "DYNO",
    "PULLY",
    "GRIP",
    "LIFT",
    "FORCE",
    "UNITY",
)

# Connection defaults
DEFAULT_SCAN_TIMEOUT = 10.0
DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_RECONNECT_DELAY = 1.5
MAX_RECONNECT_DELAY = 10.0
MAX_RECONNECT_ATTEMPTS = 10

# Data streaming
BROADCAST_INTERVAL_MS = 16  # ~60Hz
BATTERY_UPDATE_INTERVAL_MS = 2000
