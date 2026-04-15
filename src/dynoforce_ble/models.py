"""Data models for DynoForce BLE packets."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import CalibrationStatus, FlipType, UnityCounterMode


@dataclass(frozen=True)
class StatePacket:
    """Force sensor state packet (DynoGrip/DynoPull/DynoLift).

    Base packet is 20 bytes; extended adds calibration data up to 41 bytes.
    """

    # Base fields (20 bytes)
    t_ms: int
    force: float  # Current force in kg
    slope: float  # Rate of change
    peak: float  # Current attempt peak in kg
    attempt_count: int
    battery_percent: int  # 0-100
    charging: bool

    # Extended fields (37+ bytes, None if not present)
    battery_voltage: float | None = None
    calibration_factor: float | None = None
    tare_offset: int | None = None
    raw: int | None = None
    calibration_status: CalibrationStatus | None = None

    # Peak reset extension (38+ bytes)
    peak_reset_count: int | None = None

    # Overload extension (41 bytes)
    overload_count: int | None = None
    overload_active: bool | None = None

    @property
    def force_n(self) -> float:
        """Force in Newtons."""
        return self.force * 9.80665

    @property
    def force_lb(self) -> float:
        """Force in pounds."""
        return self.force * 2.20462


@dataclass(frozen=True)
class UnityCounterPacket:
    """IMU state packet from UnityCounter (ESP32-C3 + MPU6050).

    Base packet is 35 bytes; flip extension adds to 41; accel to 43.
    """

    # Base fields (35 bytes)
    t_ms: int
    angle_x: float  # Pitch in degrees
    angle_y: float  # Roll in degrees
    angle_z: float  # Tilt from vertical (0-180)
    counter: int
    duration_ms: int  # Current hold duration
    attempts: int
    record: int  # Session record
    battery_percent: int  # 0-100
    active_mode: UnityCounterMode
    altitude: float  # Barometric altitude in meters
    temperature: float  # Temperature in Celsius
    holding: bool

    # Flip detail extension (41 bytes, firmware v2.1+)
    flip_type: FlipType | None = None
    flip_degrees: int | None = None
    flip_sequence: int | None = None
    flip_twist: int | None = None

    # Acceleration extension (43 bytes, firmware v2.2+)
    accel_mag: float | None = None  # Filtered acceleration in g


@dataclass(frozen=True)
class DeviceInfo:
    """Device identification from INFO characteristic.

    Supports both binary (14 bytes) and ASCII text formats.
    """

    product_line_code: int
    product_line: str
    hw_revision: str
    fw_version: str
    serial_number: str


@dataclass
class DiscoveredDevice:
    """A DynoForce device found during BLE scanning."""

    address: str  # BLE address / UUID
    name: str  # Advertised name
    rssi: int  # Signal strength in dBm
    is_unity_counter: bool = False
