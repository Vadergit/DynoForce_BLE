"""BLE device scanning and DynoForce detection."""

from __future__ import annotations

import asyncio

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from .constants import DEFAULT_SCAN_TIMEOUT, DEVICE_NAME_PREFIXES, SERVICE_UUID
from .models import DiscoveredDevice


def is_dyno_device(name: str | None, service_uuids: list[str] | None) -> bool:
    """Check if a BLE device is a DynoForce device.

    Primary: NUS Service UUID in advertisement.
    Fallback: Name prefix matching (case-insensitive).
    """
    if service_uuids:
        if SERVICE_UUID.lower() in [u.lower() for u in service_uuids]:
            return True

    if name:
        upper = name.strip().upper()
        return any(upper.startswith(prefix) for prefix in DEVICE_NAME_PREFIXES)

    return False


def is_unity_counter(name: str | None) -> bool:
    """Check if device name indicates a UnityCounter."""
    return bool(name and name.strip().upper().startswith("UNITY"))


async def scan(
    timeout: float = DEFAULT_SCAN_TIMEOUT,
    name_filter: str | None = None,
) -> list[DiscoveredDevice]:
    """Scan for DynoForce devices.

    Args:
        timeout: Scan duration in seconds.
        name_filter: Optional prefix filter (e.g., "DynoGrip").

    Returns:
        List of discovered devices, sorted by RSSI (strongest first).
    """
    found: dict[str, DiscoveredDevice] = {}

    def _detection_callback(device: BLEDevice, adv: AdvertisementData) -> None:
        name = adv.local_name or device.name or ""
        svc_uuids = adv.service_uuids or []

        if not is_dyno_device(name, svc_uuids):
            return

        if name_filter and not name.upper().startswith(name_filter.upper()):
            return

        found[device.address] = DiscoveredDevice(
            address=device.address,
            name=name or f"DynoForce ({device.address[-5:]})",
            rssi=adv.rssi or -100,
            is_unity_counter=is_unity_counter(name),
        )

    scanner = BleakScanner(detection_callback=_detection_callback)
    await scanner.start()
    await asyncio.sleep(timeout)
    await scanner.stop()

    return sorted(found.values(), key=lambda d: d.rssi, reverse=True)


async def find_first(
    timeout: float = DEFAULT_SCAN_TIMEOUT,
    name_filter: str | None = None,
) -> DiscoveredDevice | None:
    """Scan and return the first (strongest signal) DynoForce device found."""
    devices = await scan(timeout=timeout, name_filter=name_filter)
    return devices[0] if devices else None
