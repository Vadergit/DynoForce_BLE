"""Unit tests for DynoForce packet parsers."""

import math
import struct

import pytest

from dynoforce_ble.constants import CalibrationStatus, FlipType, UnityCounterMode
from dynoforce_ble.parsers import (
    parse_device_info,
    parse_state_packet,
    parse_unity_counter_packet,
)


# ── State Packet Tests ──────────────────────────────────────────────


class TestParseStatePacket:
    def _build_base(
        self,
        t_ms: int = 1000,
        force: float = 42.5,
        slope: float = 0.1,
        peak: float = 87.0,
        attempt_count: int = 5,
        battery_pct: int = 78,
        charging: int = 0,
    ) -> bytes:
        return struct.pack(
            "<IfffHBB", t_ms, force, slope, peak, attempt_count, battery_pct, charging
        )

    def _build_extended(self, **base_kwargs) -> bytes:
        base = self._build_base(**base_kwargs)
        ext = struct.pack(
            "<ffiiB",
            3.95,   # battery_voltage
            1.23,   # calibration_factor
            -500,   # tare_offset
            12345,  # raw
            1,      # calibration_status = TARE_OK
        )
        return base + ext

    def test_base_20_bytes(self) -> None:
        data = self._build_base()
        assert len(data) == 20

        p = parse_state_packet(data)
        assert p is not None
        assert p.t_ms == 1000
        assert p.force == pytest.approx(42.5)
        assert p.slope == pytest.approx(0.1)
        assert p.peak == pytest.approx(87.0)
        assert p.attempt_count == 5
        assert p.battery_percent == 78
        assert p.charging is False
        # Extended fields should be None
        assert p.battery_voltage is None
        assert p.calibration_factor is None
        assert p.raw is None

    def test_extended_37_bytes(self) -> None:
        data = self._build_extended()
        assert len(data) == 37

        p = parse_state_packet(data)
        assert p is not None
        assert p.force == pytest.approx(42.5)
        assert p.battery_voltage == pytest.approx(3.95)
        assert p.calibration_factor == pytest.approx(1.23)
        assert p.tare_offset == -500
        assert p.raw == 12345
        assert p.calibration_status == CalibrationStatus.TARE_OK

    def test_peak_reset_38_bytes(self) -> None:
        data = self._build_extended() + bytes([7])  # peakResetCount = 7
        assert len(data) == 38

        p = parse_state_packet(data)
        assert p is not None
        assert p.peak_reset_count == 7

    def test_overload_41_bytes(self) -> None:
        data = self._build_extended()
        data += bytes([3])  # peakResetCount = 3
        data += struct.pack("<H", 12)  # overloadCount = 12
        data += bytes([1])  # overloadActive = True
        assert len(data) == 41

        p = parse_state_packet(data)
        assert p is not None
        assert p.peak_reset_count == 3
        assert p.overload_count == 12
        assert p.overload_active is True

    def test_charging_flag(self) -> None:
        data = self._build_base(charging=1)
        p = parse_state_packet(data)
        assert p is not None
        assert p.charging is True

    def test_battery_clamped_to_100(self) -> None:
        data = self._build_base(battery_pct=120)
        p = parse_state_packet(data)
        assert p is not None
        assert p.battery_percent == 100

    def test_force_out_of_range_rejected(self) -> None:
        data = self._build_base(force=1500.0)
        assert parse_state_packet(data) is None

    def test_nan_force_rejected(self) -> None:
        data = self._build_base()
        # Overwrite force bytes with NaN
        nan_bytes = struct.pack("<f", float("nan"))
        data = data[:4] + nan_bytes + data[8:]
        assert parse_state_packet(data) is None

    def test_too_short_returns_none(self) -> None:
        assert parse_state_packet(b"\x00" * 19) is None
        assert parse_state_packet(b"") is None

    def test_force_n_property(self) -> None:
        p = parse_state_packet(self._build_base(force=10.0))
        assert p is not None
        assert p.force_n == pytest.approx(98.0665)

    def test_force_lb_property(self) -> None:
        p = parse_state_packet(self._build_base(force=10.0))
        assert p is not None
        assert p.force_lb == pytest.approx(22.0462)

    def test_negative_force(self) -> None:
        p = parse_state_packet(self._build_base(force=-25.0))
        assert p is not None
        assert p.force == pytest.approx(-25.0)

    def test_invalid_calibration_status_defaults_to_idle(self) -> None:
        data = self._build_base()
        ext = struct.pack("<ffiiB", 3.9, 1.0, 0, 0, 99)  # status=99 invalid
        p = parse_state_packet(data + ext)
        assert p is not None
        assert p.calibration_status == CalibrationStatus.IDLE


# ── UnityCounter Packet Tests ───────────────────────────────────────


class TestParseUnityCounterPacket:
    def _build_base(
        self,
        t_ms: int = 5000,
        angle_x: float = 15.5,
        angle_y: float = -3.2,
        angle_z: float = 90.0,
        counter: int = 12,
        duration_ms: int = 3500,
        attempts: int = 8,
        record: int = 15,
        battery_pct: int = 65,
        mode: int = 1,
        altitude: float = 432.5,
        temp_raw: int = 235,  # 23.5 C
        flags: int = 1,  # holding
    ) -> bytes:
        return struct.pack(
            "<IfffHIHHBBfhB",
            t_ms, angle_x, angle_y, angle_z,
            counter, duration_ms, attempts, record,
            battery_pct, mode, altitude, temp_raw, flags,
        )

    def test_base_35_bytes(self) -> None:
        data = self._build_base()
        assert len(data) == 35

        p = parse_unity_counter_packet(data)
        assert p is not None
        assert p.t_ms == 5000
        assert p.angle_x == pytest.approx(15.5)
        assert p.angle_y == pytest.approx(-3.2)
        assert p.angle_z == pytest.approx(90.0)
        assert p.counter == 12
        assert p.duration_ms == 3500
        assert p.attempts == 8
        assert p.record == 15
        assert p.battery_percent == 65
        assert p.active_mode == UnityCounterMode.FLIP
        assert p.altitude == pytest.approx(432.5)
        assert p.temperature == pytest.approx(23.5)
        assert p.holding is True
        # Extensions should be None
        assert p.flip_type is None
        assert p.accel_mag is None

    def test_flip_extension_41_bytes(self) -> None:
        base = self._build_base()
        flip = struct.pack("<BhBh", 1, -180, 5, 45)  # back flip, -180deg, seq=5, twist=45
        data = base + flip
        assert len(data) == 41

        p = parse_unity_counter_packet(data)
        assert p is not None
        assert p.flip_type == FlipType.BACK
        assert p.flip_degrees == -180
        assert p.flip_sequence == 5
        assert p.flip_twist == 45

    def test_accel_extension_43_bytes(self) -> None:
        base = self._build_base()
        flip = struct.pack("<BhBh", 0, 360, 10, -30)
        accel = struct.pack("<H", 135)  # 1.35g
        data = base + flip + accel
        assert len(data) == 43

        p = parse_unity_counter_packet(data)
        assert p is not None
        assert p.accel_mag == pytest.approx(1.35)

    def test_temperature_conversion(self) -> None:
        p = parse_unity_counter_packet(self._build_base(temp_raw=-50))
        assert p is not None
        assert p.temperature == pytest.approx(-5.0)

    def test_not_holding(self) -> None:
        p = parse_unity_counter_packet(self._build_base(flags=0))
        assert p is not None
        assert p.holding is False

    def test_battery_clamped(self) -> None:
        p = parse_unity_counter_packet(self._build_base(battery_pct=200))
        assert p is not None
        assert p.battery_percent == 100

    def test_nan_angles_rejected(self) -> None:
        data = self._build_base()
        nan_bytes = struct.pack("<f", float("nan"))
        data = data[:4] + nan_bytes + data[8:]  # angle_x = NaN
        assert parse_unity_counter_packet(data) is None

    def test_too_short_returns_none(self) -> None:
        assert parse_unity_counter_packet(b"\x00" * 34) is None
        assert parse_unity_counter_packet(b"") is None

    def test_invalid_mode_defaults_to_flip(self) -> None:
        p = parse_unity_counter_packet(self._build_base(mode=99))
        assert p is not None
        assert p.active_mode == UnityCounterMode.FLIP

    def test_boulder_mode(self) -> None:
        p = parse_unity_counter_packet(self._build_base(mode=0))
        assert p is not None
        assert p.active_mode == UnityCounterMode.BOULDER


# ── Device Info Tests ───────────────────────────────────────────────


class TestParseDeviceInfo:
    def test_binary_14_bytes(self) -> None:
        data = bytes([
            0x06,  # DynoPull-T1
            1, 0,  # hw 1.0
            1, 0, 2,  # fw 1.0.2
            0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22,  # serial
        ])
        assert len(data) == 14

        info = parse_device_info(data)
        assert info is not None
        assert info.product_line_code == 0x06
        assert info.product_line == "DynoPull-T1"
        assert info.hw_revision == "1.0"
        assert info.fw_version == "1.0.2"
        assert info.serial_number == "AABBCCDDEEFF1122"

    def test_binary_dynogrip_v1(self) -> None:
        data = bytes([0x01, 2, 1, 2, 7, 19] + [0] * 8)
        info = parse_device_info(data)
        assert info is not None
        assert info.product_line == "DynoGrip-V1"
        assert info.fw_version == "2.7.19"
        assert info.hw_revision == "2.1"

    def test_binary_unity_counter(self) -> None:
        data = bytes([0x09, 1, 0, 2, 1, 0] + [0xFF] * 8)
        info = parse_device_info(data)
        assert info is not None
        assert info.product_line == "UnityCounter"
        assert info.fw_version == "2.1.0"

    def test_text_format_simple(self) -> None:
        data = b"2.7.19"
        info = parse_device_info(data)
        assert info is not None
        assert info.fw_version == "2.7.19"
        assert info.product_line == "DynoGrip-V1"  # default for text

    def test_text_format_with_suffix(self) -> None:
        data = b"2.6.0-stable"
        info = parse_device_info(data)
        assert info is not None
        assert info.fw_version == "2.6.0"

    def test_unknown_product_line(self) -> None:
        data = bytes([0xFF, 1, 0, 1, 0, 0] + [0] * 8)
        info = parse_device_info(data)
        assert info is not None
        assert info.product_line == "UNKNOWN"

    def test_too_short_returns_none(self) -> None:
        assert parse_device_info(b"") is None
        assert parse_device_info(b"\x00\x01") is None

    def test_binary_too_short_returns_none(self) -> None:
        # First byte is not ASCII digit, so binary path, but too short
        data = bytes([0x01, 2, 1])
        assert parse_device_info(data) is None
