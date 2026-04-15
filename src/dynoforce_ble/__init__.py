"""dynoforce-ble: Python BLE library for DynoForce fitness devices.

Connect to DynoGrip, DynoPull, DynoLift, and UnityCounter devices
over Bluetooth Low Energy. Stream real-time force/IMU data, send
calibration commands, and monitor battery status.

Quick start (async)::

    import asyncio
    from dynoforce_ble import DynoForceClient

    async def main():
        async with DynoForceClient() as client:
            await client.connect_first()
            client.on_state_packet(lambda p: print(f"{p.force:.1f} kg"))
            await asyncio.sleep(10)

    asyncio.run(main())

Quick start (sync)::

    from dynoforce_ble import DynoForceSyncClient
    import time

    with DynoForceSyncClient() as client:
        client.connect_first()
        client.on_state_packet(lambda p: print(f"{p.force:.1f} kg"))
        time.sleep(10)
"""

from ._version import __version__
from .client import DynoForceClient
from .commands import (
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
from .constants import (
    COMMAND_UUID,
    INFO_UUID,
    PRODUCT_LINE_NAMES,
    SERVICE_UUID,
    STATE_UUID,
    CalibrationStatus,
    Command,
    FlipType,
    Melody,
    ProductLineCode,
    UnityCounterMode,
)
from .events import ConnectionState, EventType
from .models import DeviceInfo, DiscoveredDevice, StatePacket, UnityCounterPacket
from .sync_client import DynoForceSyncClient

__all__ = [
    "__version__",
    # Clients
    "DynoForceClient",
    "DynoForceSyncClient",
    # Models
    "StatePacket",
    "UnityCounterPacket",
    "DeviceInfo",
    "DiscoveredDevice",
    # Events
    "ConnectionState",
    "EventType",
    # Constants
    "Command",
    "CalibrationStatus",
    "ProductLineCode",
    "Melody",
    "UnityCounterMode",
    "FlipType",
    "PRODUCT_LINE_NAMES",
    "SERVICE_UUID",
    "COMMAND_UUID",
    "STATE_UUID",
    "INFO_UUID",
    # Command builders
    "tare",
    "calibrate",
    "set_name",
    "buzzer",
    "buzzer_stop",
    "tone",
    "set_inactivity_timeout",
    "reset_peak",
    "set_tx_power",
]
