"""Build binary command payloads for DynoForce devices."""

from __future__ import annotations

import struct

from .constants import Command, Melody


def tare() -> bytes:
    """Build TARE command. Zeros the scale at current load."""
    return bytes([Command.TARE])


def calibrate(known_weight_kg: float) -> bytes:
    """Build CALIBRATE command with known weight in kg."""
    return bytes([Command.CALIBRATE]) + struct.pack("<f", known_weight_kg)


def set_name(name: str) -> bytes:
    """Build SET_NAME command. Max 20 UTF-8 chars. Device restarts after."""
    encoded = name[:20].encode("utf-8")
    return bytes([Command.SET_NAME]) + encoded


def buzzer(melody_id: int | Melody = Melody.BEEP) -> bytes:
    """Build BUZZER/MELODY command to play a predefined melody."""
    return bytes([Command.BUZZER, int(melody_id)])


def buzzer_stop() -> bytes:
    """Stop any playing melody immediately."""
    return bytes([Command.BUZZER, Melody.NONE])


def tone(duration_ms: int = 200, frequency_hz: int = 880) -> bytes:
    """Play a custom tone at specified frequency.

    Args:
        duration_ms: Duration in ms (max 5000, sent in 100ms units).
        frequency_hz: Frequency in Hz (100-8000).
    """
    dur = max(1, min(round(duration_ms / 100), 50))
    freq = max(100, min(frequency_hz, 8000))
    return bytes([Command.BUZZER, 0x00, dur]) + struct.pack("<H", freq)


def set_inactivity_timeout(seconds: int) -> bytes:
    """Set inactivity alarm timeout. 0 = disabled."""
    clamped = max(0, min(seconds, 65535))
    return bytes([Command.SET_INACTIVITY]) + struct.pack("<H", clamped)


def reset_peak() -> bytes:
    """Reset peak/max force on device display."""
    return bytes([Command.RESET_PEAK])


def set_tx_power(level: int) -> bytes:
    """Set BLE transmit power level.

    Args:
        level: 0-7 (0=-12dBm, 5=+3dBm default, 7=+9dBm).
    """
    clamped = max(0, min(round(level), 7))
    return bytes([Command.SET_TX_POWER, clamped])
