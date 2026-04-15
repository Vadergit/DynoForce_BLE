#!/usr/bin/env python3
"""Minimal example: connect to a DynoForce device and print force values."""

import asyncio

from dynoforce_ble import DynoForceClient


async def main() -> None:
    async with DynoForceClient() as client:
        print("Scanning for DynoForce devices...")
        await client.connect_first()
        print(f"Connected! Device: {client.device_info}")

        client.on_state_packet(
            lambda p: print(f"Force: {p.force:6.1f} kg  Peak: {p.peak:6.1f} kg  Battery: {p.battery_percent}%")
        )

        print("Streaming data for 30 seconds... (Ctrl+C to stop)")
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass

    print("Disconnected.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
