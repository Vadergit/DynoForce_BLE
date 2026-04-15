"""Unit tests for DynoForce command builder."""

import struct

import pytest

from dynoforce_ble.commands import (
    buzzer,
    buzzer_stop,
    calibrate,
    reset_peak,
    set_inactivity_timeout,
    set_name,
    set_tx_power,
    tare,
    tone,
)
from dynoforce_ble.constants import Command, Melody


class TestTare:
    def test_single_byte(self) -> None:
        assert tare() == bytes([0x01])

    def test_command_code(self) -> None:
        assert tare()[0] == Command.TARE


class TestCalibrate:
    def test_length(self) -> None:
        result = calibrate(20.0)
        assert len(result) == 5  # 1 byte cmd + 4 bytes float

    def test_command_code(self) -> None:
        assert calibrate(20.0)[0] == Command.CALIBRATE

    def test_weight_encoding(self) -> None:
        result = calibrate(20.0)
        weight = struct.unpack_from("<f", result, 1)[0]
        assert weight == pytest.approx(20.0)

    def test_zero_weight(self) -> None:
        result = calibrate(0.0)
        weight = struct.unpack_from("<f", result, 1)[0]
        assert weight == pytest.approx(0.0)

    def test_negative_weight(self) -> None:
        result = calibrate(-5.0)
        weight = struct.unpack_from("<f", result, 1)[0]
        assert weight == pytest.approx(-5.0)


class TestSetName:
    def test_basic(self) -> None:
        result = set_name("DynoGrip-001")
        assert result[0] == Command.SET_NAME
        assert result[1:] == b"DynoGrip-001"

    def test_truncation_at_20(self) -> None:
        result = set_name("A" * 30)
        assert len(result) == 21  # 1 + 20

    def test_utf8_encoding(self) -> None:
        result = set_name("Grip")
        assert result == bytes([0x03]) + b"Grip"


class TestBuzzer:
    def test_melody_beep(self) -> None:
        result = buzzer(Melody.BEEP)
        assert result == bytes([0x04, 0x01])

    def test_melody_success(self) -> None:
        result = buzzer(Melody.SUCCESS)
        assert result == bytes([0x04, 0x02])

    def test_default_is_beep(self) -> None:
        assert buzzer() == bytes([0x04, 0x01])

    def test_buzzer_stop(self) -> None:
        result = buzzer_stop()
        assert result == bytes([0x04, 0x00])


class TestTone:
    def test_format(self) -> None:
        result = tone(200, 880)
        assert len(result) == 5
        assert result[0] == Command.BUZZER
        assert result[1] == 0x00  # custom tone marker

    def test_duration_100ms_units(self) -> None:
        result = tone(500, 440)
        assert result[2] == 5  # 500ms / 100 = 5

    def test_frequency_encoding(self) -> None:
        result = tone(200, 1000)
        freq = struct.unpack_from("<H", result, 3)[0]
        assert freq == 1000

    def test_duration_clamped_max(self) -> None:
        result = tone(10000, 440)  # 10s > max 5s
        assert result[2] == 50  # max is 50 (5000ms / 100)

    def test_duration_clamped_min(self) -> None:
        result = tone(10, 440)  # 10ms rounds to 0, clamped to 1
        assert result[2] == 1

    def test_frequency_clamped(self) -> None:
        result = tone(200, 50)  # below 100
        freq = struct.unpack_from("<H", result, 3)[0]
        assert freq == 100


class TestSetInactivityTimeout:
    def test_basic(self) -> None:
        result = set_inactivity_timeout(300)
        assert result[0] == Command.SET_INACTIVITY
        val = struct.unpack_from("<H", result, 1)[0]
        assert val == 300

    def test_disable(self) -> None:
        result = set_inactivity_timeout(0)
        val = struct.unpack_from("<H", result, 1)[0]
        assert val == 0

    def test_clamped_max(self) -> None:
        result = set_inactivity_timeout(100000)
        val = struct.unpack_from("<H", result, 1)[0]
        assert val == 65535


class TestResetPeak:
    def test_single_byte(self) -> None:
        assert reset_peak() == bytes([0x09])


class TestSetTxPower:
    def test_basic(self) -> None:
        result = set_tx_power(5)
        assert result == bytes([0x0A, 5])

    def test_clamped_min(self) -> None:
        result = set_tx_power(-1)
        assert result[1] == 0

    def test_clamped_max(self) -> None:
        result = set_tx_power(10)
        assert result[1] == 7
