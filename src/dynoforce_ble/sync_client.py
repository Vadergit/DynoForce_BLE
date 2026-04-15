"""Synchronous wrapper around the async DynoForceClient."""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable

from .client import DynoForceClient
from .events import ConnectionState
from .models import DeviceInfo, DiscoveredDevice, StatePacket, UnityCounterPacket


class DynoForceSyncClient:
    """Synchronous BLE client for DynoForce devices.

    Runs the async event loop in a background thread.
    Suitable for scripts, notebooks, and GUI applications.

    Usage::

        client = DynoForceSyncClient()
        client.connect_first()
        client.on_state_packet(lambda p: print(f"Force: {p.force:.1f} kg"))
        time.sleep(30)
        client.disconnect()
    """

    def __init__(self, **kwargs: Any) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._client: DynoForceClient = self._run_coro(self._create_client(**kwargs))

    @staticmethod
    async def _create_client(**kwargs: Any) -> DynoForceClient:
        return DynoForceClient(**kwargs)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_coro(self, coro: Any, timeout: float = 60) -> Any:
        """Submit a coroutine to the event loop and wait for the result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    # ── Scanning ────────────────────────────────────────────────────

    def scan(
        self,
        timeout: float | None = None,
        name_filter: str | None = None,
    ) -> list[DiscoveredDevice]:
        """Scan for DynoForce devices."""
        return self._run_coro(
            self._client.scan(timeout=timeout, name_filter=name_filter)
        )

    # ── Connection ──────────────────────────────────────────────────

    def connect(self, address: str) -> None:
        """Connect to a specific device by BLE address."""
        self._run_coro(self._client.connect(address))

    def connect_first(
        self,
        timeout: float | None = None,
        name_filter: str | None = None,
    ) -> None:
        """Scan and connect to the first DynoForce device found."""
        self._run_coro(
            self._client.connect_first(timeout=timeout, name_filter=name_filter)
        )

    def disconnect(self) -> None:
        """Disconnect from current device."""
        self._run_coro(self._client.disconnect())

    # ── Properties ──────────────────────────────────────────────────

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._client.state

    @property
    def is_connected(self) -> bool:
        """True when device is connected and streaming."""
        return self._client.is_connected

    @property
    def is_unity_counter(self) -> bool:
        """True if connected device is a UnityCounter."""
        return self._client.is_unity_counter

    @property
    def device_info(self) -> DeviceInfo | None:
        """Device info (available after connect)."""
        return self._client.device_info

    # ── Events ──────────────────────────────────────────────────────

    def on_state_packet(
        self, callback: Callable[[StatePacket], None]
    ) -> Callable[[], None]:
        """Subscribe to force sensor state packets."""
        return self._client.on_state_packet(callback)

    def on_unity_counter_packet(
        self, callback: Callable[[UnityCounterPacket], None]
    ) -> Callable[[], None]:
        """Subscribe to UnityCounter IMU packets."""
        return self._client.on_unity_counter_packet(callback)

    def on_connection_change(
        self, callback: Callable[[ConnectionState], None]
    ) -> Callable[[], None]:
        """Subscribe to connection state changes."""
        return self._client.on_connection_change(callback)

    def on_device_info(
        self, callback: Callable[[DeviceInfo], None]
    ) -> Callable[[], None]:
        """Subscribe to device info events."""
        return self._client.on_device_info(callback)

    def on_error(
        self, callback: Callable[[Exception], None]
    ) -> Callable[[], None]:
        """Subscribe to error events."""
        return self._client.on_error(callback)

    # ── Commands ────────────────────────────────────────────────────

    def send_command(self, payload: bytes) -> None:
        """Send a raw command to the device."""
        self._run_coro(self._client.send_command(payload))

    def tare(self) -> None:
        """Send TARE command (zero the scale)."""
        self._run_coro(self._client.tare())

    def calibrate(self, known_weight_kg: float) -> None:
        """Send CALIBRATE command with known weight."""
        self._run_coro(self._client.calibrate(known_weight_kg))

    def set_name(self, name: str) -> None:
        """Rename the device (max 20 chars, restarts device)."""
        self._run_coro(self._client.set_name(name))

    def play_melody(self, melody_id: int) -> None:
        """Play a predefined melody on device buzzer."""
        self._run_coro(self._client.play_melody(melody_id))

    def reset_peak(self) -> None:
        """Reset peak force on device."""
        self._run_coro(self._client.reset_peak())

    def set_inactivity_timeout(self, seconds: int) -> None:
        """Set inactivity alarm timeout (0 = disabled)."""
        self._run_coro(self._client.set_inactivity_timeout(seconds))

    def set_tx_power(self, level: int) -> None:
        """Set BLE transmit power (0-7)."""
        self._run_coro(self._client.set_tx_power(level))

    # ── Cleanup ─────────────────────────────────────────────────────

    def close(self) -> None:
        """Disconnect and stop the background event loop."""
        try:
            self.disconnect()
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    def __enter__(self) -> DynoForceSyncClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
