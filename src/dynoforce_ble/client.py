"""Async BLE client for DynoForce devices."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from bleak import BleakClient

from .constants import (
    COMMAND_UUID,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_RECONNECT_DELAY,
    DEFAULT_SCAN_TIMEOUT,
    INFO_UUID,
    MAX_RECONNECT_ATTEMPTS,
    MAX_RECONNECT_DELAY,
    STATE_UUID,
)
from .events import ConnectionState, EventEmitter, EventType
from .models import DeviceInfo, DiscoveredDevice, StatePacket, UnityCounterPacket
from .parsers import parse_device_info, parse_state_packet, parse_unity_counter_packet
from .scanner import find_first, is_unity_counter, scan

logger = logging.getLogger("dynoforce_ble")


class DynoForceClient:
    """Async BLE client for DynoForce fitness devices.

    Manages connection, reconnection, packet parsing, and event dispatch.

    Usage::

        async with DynoForceClient() as client:
            await client.connect_first()
            client.on_state_packet(lambda p: print(f"Force: {p.force:.1f} kg"))
            await asyncio.sleep(30)

    Or without context manager::

        client = DynoForceClient()
        await client.connect("AA:BB:CC:DD:EE:FF")
        ...
        await client.disconnect()
    """

    def __init__(
        self,
        auto_reconnect: bool = True,
        scan_timeout: float = DEFAULT_SCAN_TIMEOUT,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
    ) -> None:
        self._auto_reconnect = auto_reconnect
        self._scan_timeout = scan_timeout
        self._connect_timeout = connect_timeout

        self._client: BleakClient | None = None
        self._state = ConnectionState.DISCONNECTED
        self._events = EventEmitter()
        self._is_unity_counter = False
        self._device_info: DeviceInfo | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._running = True
        self._last_address: str | None = None

    # ── Context manager ─────────────────────────────────────────────

    async def __aenter__(self) -> DynoForceClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.disconnect()

    # ── Properties ──────────────────────────────────────────────────

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """True when device is connected and streaming data."""
        return self._state == ConnectionState.READY

    @property
    def is_unity_counter(self) -> bool:
        """True if connected device is a UnityCounter (IMU)."""
        return self._is_unity_counter

    @property
    def device_info(self) -> DeviceInfo | None:
        """Device info read from INFO characteristic (available after connect)."""
        return self._device_info

    # ── Event subscription ──────────────────────────────────────────

    def on_state_packet(
        self, callback: Callable[[StatePacket], None]
    ) -> Callable[[], None]:
        """Subscribe to force sensor state packets. Returns unsubscribe function."""
        return self._events.on(EventType.STATE_PACKET, callback)

    def on_unity_counter_packet(
        self, callback: Callable[[UnityCounterPacket], None]
    ) -> Callable[[], None]:
        """Subscribe to UnityCounter IMU packets. Returns unsubscribe function."""
        return self._events.on(EventType.UNITY_COUNTER_PACKET, callback)

    def on_device_info(
        self, callback: Callable[[DeviceInfo], None]
    ) -> Callable[[], None]:
        """Subscribe to device info events. Returns unsubscribe function."""
        return self._events.on(EventType.DEVICE_INFO, callback)

    def on_connection_change(
        self, callback: Callable[[ConnectionState], None]
    ) -> Callable[[], None]:
        """Subscribe to connection state changes. Returns unsubscribe function."""
        return self._events.on(EventType.CONNECTION_CHANGE, callback)

    def on_error(
        self, callback: Callable[[Exception], None]
    ) -> Callable[[], None]:
        """Subscribe to error events. Returns unsubscribe function."""
        return self._events.on(EventType.ERROR, callback)

    # ── Scanning ────────────────────────────────────────────────────

    async def scan(
        self,
        timeout: float | None = None,
        name_filter: str | None = None,
    ) -> list[DiscoveredDevice]:
        """Scan for DynoForce devices.

        Args:
            timeout: Scan duration in seconds (default: scan_timeout from init).
            name_filter: Optional prefix filter (e.g. "DynoGrip").

        Returns:
            List of discovered devices sorted by signal strength.
        """
        self._set_state(ConnectionState.SCANNING)
        try:
            devices = await scan(
                timeout=timeout or self._scan_timeout,
                name_filter=name_filter,
            )
            return devices
        finally:
            if self._state == ConnectionState.SCANNING:
                self._set_state(ConnectionState.DISCONNECTED)

    # ── Connection ──────────────────────────────────────────────────

    async def connect(self, address: str) -> None:
        """Connect to a specific device by BLE address.

        Args:
            address: BLE MAC address or UUID (macOS).
        """
        self._cancel_reconnect()
        self._set_state(ConnectionState.CONNECTING)
        self._last_address = address
        self._running = True

        try:
            self._client = BleakClient(
                address,
                disconnected_callback=self._on_disconnect,
                timeout=self._connect_timeout,
            )
            await self._client.connect()
            self._set_state(ConnectionState.CONNECTED)

            # Subscribe to state notifications
            await self._client.start_notify(STATE_UUID, self._on_notification)
            self._set_state(ConnectionState.READY)
            logger.info("Connected to %s", address)

            # Read device info (non-blocking)
            asyncio.ensure_future(self._read_device_info())

        except Exception as exc:
            logger.error("Connection failed: %s", exc)
            self._set_state(ConnectionState.ERROR)
            self._events.emit(EventType.ERROR, exc)
            if self._auto_reconnect and self._running:
                self._schedule_reconnect()

    async def connect_first(
        self,
        timeout: float | None = None,
        name_filter: str | None = None,
    ) -> None:
        """Scan and connect to the first (strongest) DynoForce device.

        Args:
            timeout: Scan timeout in seconds.
            name_filter: Optional name prefix filter.

        Raises:
            ConnectionError: If no device is found.
        """
        self._set_state(ConnectionState.SCANNING)
        device = await find_first(
            timeout=timeout or self._scan_timeout,
            name_filter=name_filter,
        )
        if not device:
            self._set_state(ConnectionState.DISCONNECTED)
            raise ConnectionError("No DynoForce device found")

        self._is_unity_counter = device.is_unity_counter
        logger.info("Found %s (%s, RSSI %d)", device.name, device.address, device.rssi)
        await self.connect(device.address)

    async def disconnect(self) -> None:
        """Disconnect from current device and stop auto-reconnect."""
        self._running = False
        self._cancel_reconnect()

        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(STATE_UUID)
            except Exception:
                pass
            try:
                await self._client.disconnect()
            except Exception:
                pass

        self._client = None
        self._set_state(ConnectionState.DISCONNECTED)

    # ── Commands ────────────────────────────────────────────────────

    async def send_command(self, payload: bytes) -> None:
        """Send a raw command to the device.

        Use functions from ``dynoforce_ble.commands`` to build payloads.

        Raises:
            ConnectionError: If not connected.
        """
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to any device")
        await self._client.write_gatt_char(COMMAND_UUID, payload, response=True)

    async def tare(self) -> None:
        """Send TARE command (zero the scale at current load)."""
        from . import commands

        await self.send_command(commands.tare())

    async def calibrate(self, known_weight_kg: float) -> None:
        """Send CALIBRATE command with known weight in kg."""
        from . import commands

        await self.send_command(commands.calibrate(known_weight_kg))

    async def set_name(self, name: str) -> None:
        """Rename the device (max 20 chars, device restarts)."""
        from . import commands

        await self.send_command(commands.set_name(name))

    async def play_melody(self, melody_id: int) -> None:
        """Play a predefined melody on device buzzer."""
        from . import commands

        await self.send_command(commands.buzzer(melody_id))

    async def reset_peak(self) -> None:
        """Reset peak force on device."""
        from . import commands

        await self.send_command(commands.reset_peak())

    async def set_inactivity_timeout(self, seconds: int) -> None:
        """Set inactivity alarm timeout (0 = disabled)."""
        from . import commands

        await self.send_command(commands.set_inactivity_timeout(seconds))

    async def set_tx_power(self, level: int) -> None:
        """Set BLE transmit power (0-7)."""
        from . import commands

        await self.send_command(commands.set_tx_power(level))

    # ── Internal ────────────────────────────────────────────────────

    def _set_state(self, state: ConnectionState) -> None:
        if self._state != state:
            self._state = state
            self._events.emit(EventType.CONNECTION_CHANGE, state)

    def _on_disconnect(self, _client: BleakClient) -> None:
        logger.info("Device disconnected")
        self._set_state(ConnectionState.DISCONNECTED)
        if self._auto_reconnect and self._running:
            self._schedule_reconnect()

    def _on_notification(self, _sender: int, data: bytearray) -> None:
        if self._is_unity_counter:
            packet = parse_unity_counter_packet(data)
            if packet:
                self._events.emit(EventType.UNITY_COUNTER_PACKET, packet)
        else:
            packet = parse_state_packet(data)
            if packet:
                self._events.emit(EventType.STATE_PACKET, packet)

    async def _read_device_info(self) -> None:
        if not self._client or not self._client.is_connected:
            return
        try:
            raw = await self._client.read_gatt_char(INFO_UUID)
            info = parse_device_info(raw)
            if info:
                self._device_info = info
                if info.product_line == "UnityCounter":
                    self._is_unity_counter = True
                self._events.emit(EventType.DEVICE_INFO, info)
                logger.info(
                    "Device: %s fw=%s sn=%s",
                    info.product_line,
                    info.fw_version,
                    info.serial_number,
                )
        except Exception as exc:
            logger.warning("Could not read device info: %s", exc)

    def _schedule_reconnect(self) -> None:
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.ensure_future(self._reconnect_loop())

    def _cancel_reconnect(self) -> None:
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            self._reconnect_task = None

    async def _reconnect_loop(self) -> None:
        delay = DEFAULT_RECONNECT_DELAY
        for attempt in range(MAX_RECONNECT_ATTEMPTS):
            if not self._running or self._state == ConnectionState.READY:
                return

            logger.info(
                "Reconnect attempt %d/%d in %.1fs",
                attempt + 1,
                MAX_RECONNECT_ATTEMPTS,
                delay,
            )
            await asyncio.sleep(delay)

            if not self._running:
                return

            try:
                if self._last_address:
                    await self.connect(self._last_address)
                else:
                    await self.connect_first()
                if self._state == ConnectionState.READY:
                    return
            except Exception:
                pass

            delay = min(delay * 2, MAX_RECONNECT_DELAY)

        logger.warning("Max reconnect attempts (%d) reached", MAX_RECONNECT_ATTEMPTS)
