"""Binary packet parsers for DynoForce BLE data."""

from __future__ import annotations

import math
import struct

from .constants import (
    CalibrationStatus,
    FlipType,
    PRODUCT_LINE_NAMES,
    UnityCounterMode,
)
from .models import DeviceInfo, StatePacket, UnityCounterPacket

# ── State packet formats (little-endian) ────────────────────────────

_STATE_BASE_FMT = "<IfffHBB"  # 20 bytes
_STATE_BASE_SIZE = struct.calcsize(_STATE_BASE_FMT)  # 20

_STATE_EXT_FMT = "<IfffHBBffiiB"  # 37 bytes
_STATE_EXT_SIZE = struct.calcsize(_STATE_EXT_FMT)  # 37

_STATE_PEAK_RESET_SIZE = 38  # + uint8 peakResetCount
_STATE_OVERLOAD_SIZE = 41  # + uint8 peakResetCount + uint16 overloadCount + uint8 overloadActive

# ── UnityCounter packet sizes ───────────────────────────────────────

_UNITY_BASE_SIZE = 35
_UNITY_FLIP_SIZE = 41  # v2.1+ flip details
_UNITY_ACCEL_SIZE = 43  # v2.2+ acceleration

# ── Info packet ─────────────────────────────────────────────────────

_INFO_BINARY_SIZE = 14


def parse_state_packet(data: bytes | bytearray) -> StatePacket | None:
    """Parse a DynoGrip/DynoPull/DynoLift state notification.

    Handles 20-byte base, 37-byte extended, 38-byte peak-reset,
    and 41-byte overload packet variants.

    Returns:
        Parsed StatePacket, or None if data is too short or invalid.
    """
    if len(data) < _STATE_BASE_SIZE:
        return None

    try:
        vals = struct.unpack_from(_STATE_BASE_FMT, data)
        t_ms, force, slope, peak, attempt_count, battery_pct, charging_raw = vals

        # Sanity check (matches TS parser isFinite + range check)
        if not math.isfinite(force) or force < -1000 or force > 1000:
            return None

        kwargs: dict = {
            "t_ms": t_ms,
            "force": force,
            "slope": slope,
            "peak": peak,
            "attempt_count": attempt_count,
            "battery_percent": min(battery_pct, 100),
            "charging": charging_raw == 1,
        }

        # Extended fields (37+ bytes)
        if len(data) >= _STATE_EXT_SIZE:
            ext = struct.unpack_from(_STATE_EXT_FMT, data)
            kwargs["battery_voltage"] = ext[7]
            kwargs["calibration_factor"] = ext[8]
            kwargs["tare_offset"] = ext[9]
            kwargs["raw"] = ext[10]
            try:
                kwargs["calibration_status"] = CalibrationStatus(ext[11])
            except ValueError:
                kwargs["calibration_status"] = CalibrationStatus.IDLE

        # Peak reset count (byte 37)
        if len(data) >= _STATE_PEAK_RESET_SIZE:
            kwargs["peak_reset_count"] = data[37]

        # Overload extension (bytes 37-40)
        if len(data) >= _STATE_OVERLOAD_SIZE:
            kwargs["peak_reset_count"] = data[37]
            kwargs["overload_count"] = struct.unpack_from("<H", data, 38)[0]
            kwargs["overload_active"] = data[40] != 0

        return StatePacket(**kwargs)
    except Exception:
        return None


def parse_unity_counter_packet(data: bytes | bytearray) -> UnityCounterPacket | None:
    """Parse a UnityCounter IMU state notification.

    Handles 35-byte base, 41-byte flip extension, 43-byte accel extension.

    Returns:
        Parsed UnityCounterPacket, or None if data is too short or invalid.
    """
    if len(data) < _UNITY_BASE_SIZE:
        return None

    try:
        offset = 0
        t_ms = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        angle_x = struct.unpack_from("<f", data, offset)[0]
        offset += 4
        angle_y = struct.unpack_from("<f", data, offset)[0]
        offset += 4
        angle_z = struct.unpack_from("<f", data, offset)[0]
        offset += 4
        counter = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        duration_ms = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        attempts = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        record = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        battery_pct = data[offset]
        offset += 1
        active_mode_raw = data[offset]
        offset += 1
        altitude = struct.unpack_from("<f", data, offset)[0]
        offset += 4
        temp_raw = struct.unpack_from("<h", data, offset)[0]
        offset += 2
        flags = data[offset]
        offset += 1

        # Validate angles (NaN check, matches TS isFinite)
        if not (math.isfinite(angle_x) and math.isfinite(angle_y) and math.isfinite(angle_z)):
            return None

        try:
            active_mode = UnityCounterMode(active_mode_raw)
        except ValueError:
            active_mode = UnityCounterMode.FLIP

        kwargs: dict = {
            "t_ms": t_ms,
            "angle_x": angle_x,
            "angle_y": angle_y,
            "angle_z": angle_z,
            "counter": counter,
            "duration_ms": duration_ms,
            "attempts": attempts,
            "record": record,
            "battery_percent": min(battery_pct, 100),
            "active_mode": active_mode,
            "altitude": altitude if math.isfinite(altitude) else 0.0,
            "temperature": temp_raw / 10.0,
            "holding": (flags & 0x01) != 0,
        }

        # Flip detail extension (41 bytes, firmware v2.1+)
        if len(data) >= _UNITY_FLIP_SIZE:
            flip_type_raw = data[offset]
            offset += 1
            flip_degrees = struct.unpack_from("<h", data, offset)[0]
            offset += 2
            flip_seq = data[offset]
            offset += 1
            flip_twist = struct.unpack_from("<h", data, offset)[0]
            offset += 2

            try:
                kwargs["flip_type"] = FlipType(flip_type_raw)
            except ValueError:
                kwargs["flip_type"] = FlipType.FRONT
            kwargs["flip_degrees"] = flip_degrees
            kwargs["flip_sequence"] = flip_seq
            kwargs["flip_twist"] = flip_twist

        # Acceleration extension (43 bytes, firmware v2.2+)
        if len(data) >= _UNITY_ACCEL_SIZE:
            accel_raw = struct.unpack_from("<H", data, offset)[0]
            kwargs["accel_mag"] = accel_raw / 100.0

        return UnityCounterPacket(**kwargs)
    except Exception:
        return None


def parse_device_info(data: bytes | bytearray) -> DeviceInfo | None:
    """Parse device info from INFO characteristic.

    Auto-detects binary (14 bytes) vs ASCII text format.

    Returns:
        Parsed DeviceInfo, or None if data is invalid.
    """
    if not data or len(data) < 3:
        return None

    # Detect format: ASCII starts with digit (0x30-0x39) or dot (0x2E)
    first_byte = data[0]
    if (0x30 <= first_byte <= 0x39) or first_byte == 0x2E:
        return _parse_info_text(data)
    else:
        return _parse_info_binary(data)


def _parse_info_text(data: bytes | bytearray) -> DeviceInfo | None:
    """Parse ASCII version string like '2.6.0' or '2.6.0-stable'."""
    try:
        version_str = bytes(data).decode("ascii", errors="ignore").strip()
        parts = version_str.split(".")
        if len(parts) < 3:
            return None
        patch = parts[2].split("-")[0]
        fw_version = f"{parts[0]}.{parts[1]}.{patch}"
        return DeviceInfo(
            product_line_code=0x01,
            product_line="DynoGrip-V1",
            hw_revision="1.0",
            fw_version=fw_version,
            serial_number="UNKNOWN",
        )
    except Exception:
        return None


def _parse_info_binary(data: bytes | bytearray) -> DeviceInfo | None:
    """Parse binary INFO packet (14 bytes)."""
    if len(data) < _INFO_BINARY_SIZE:
        return None
    try:
        plc = data[0]
        hw_major = data[1]
        hw_minor = data[2]
        fw_major = data[3]
        fw_minor = data[4]
        fw_patch = data[5]
        serial_bytes = data[6:14]
        serial_hex = serial_bytes.hex().upper()
        product_line = PRODUCT_LINE_NAMES.get(plc, "UNKNOWN")
        return DeviceInfo(
            product_line_code=plc,
            product_line=product_line,
            hw_revision=f"{hw_major}.{hw_minor}",
            fw_version=f"{fw_major}.{fw_minor}.{fw_patch}",
            serial_number=serial_hex,
        )
    except Exception:
        return None
