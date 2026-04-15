#!/usr/bin/env python3
"""Log DynoForce data to CSV file."""

import csv
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from dynoforce_ble import DynoForceSyncClient, StatePacket

# Generate timestamped filename
filename = f"dynoforce_log_{datetime.now():%Y%m%d_%H%M%S}.csv"
filepath = Path(filename)

running = True


def on_sigint(_sig: int, _frame: object) -> None:
    global running
    running = False


signal.signal(signal.SIGINT, on_sigint)


def main() -> None:
    global running

    print("DynoForce CSV Logger")
    print(f"Output: {filepath.absolute()}")
    print()

    client = DynoForceSyncClient()

    try:
        print("Scanning for DynoForce device...")
        client.connect_first()
        info = client.device_info
        if info:
            print(f"Connected: {info.product_line} fw={info.fw_version} sn={info.serial_number}")
        else:
            print("Connected (device info not available)")
        print()

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "device_t_ms",
                "force_kg",
                "force_n",
                "peak_kg",
                "slope",
                "battery_pct",
                "battery_v",
                "raw_adc",
                "attempt_count",
            ])

            count = 0

            def on_packet(p: StatePacket) -> None:
                nonlocal count
                writer.writerow([
                    datetime.now().isoformat(timespec="milliseconds"),
                    p.t_ms,
                    f"{p.force:.3f}",
                    f"{p.force_n:.1f}",
                    f"{p.peak:.3f}",
                    f"{p.slope:.3f}",
                    p.battery_percent,
                    f"{p.battery_voltage:.3f}" if p.battery_voltage is not None else "",
                    p.raw if p.raw is not None else "",
                    p.attempt_count,
                ])
                count += 1
                if count % 60 == 0:
                    f.flush()
                    print(f"  {count} samples | Force: {p.force:6.1f} kg | Peak: {p.peak:6.1f} kg")

            client.on_state_packet(on_packet)
            print("Logging... (Ctrl+C to stop)")

            while running:
                time.sleep(0.5)

        print(f"\nSaved {count} samples to {filepath}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
