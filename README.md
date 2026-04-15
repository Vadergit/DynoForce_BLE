# DynoForce_BLE

Python BLE library for **DynoForce** fitness devices.

Connect to DynoGrip, DynoPull, DynoLift, and UnityCounter devices over Bluetooth Low Energy.
Stream real-time force and IMU data, calibrate sensors, and monitor battery status.

> **No training logic. No UI logic. No cloud.**
> Just: connection, device control, calibration, raw data streaming, battery status.

---

## Supported Devices

| Device                        | Type           | Data                                        |
| ----------------------------- | -------------- | ------------------------------------------- |
| DynoGrip (V1, Pro, Lite, nRF) | Grip strength  | Force (kg), peak, slope, calibration        |
| DynoPull (T1, nRF)            | Pull force     | Force (kg), peak, slope, calibration        |
| DynoLift S1                   | Vertical force | Force (kg), peak, slope, calibration        |
| UnityCounter                  | IMU sensor     | Angles, flips, holds, altitude, temperature |

## Supported Platforms

| Platform    | BLE Backend   | Notes                |
| ----------- | ------------- | -------------------- |
| **macOS**   | CoreBluetooth | Tested on macOS 14+  |
| **Windows** | WinRT         | Windows 10+          |
| **Linux**   | BlueZ         | Requires BlueZ 5.43+ |

---

## Prerequisites

Before you start, make sure you have:

1. **Python 3.10 or newer** installed ([python.org/downloads](https://www.python.org/downloads/))
2. **A DynoForce device** (DynoGrip, DynoPull, DynoLift, or UnityCounter) powered on
3. **Bluetooth enabled** on your computer
4. **No other app** connected to the device (only one BLE connection at a time!)

### Check your Python version

```bash
python3 --version
# Should print Python 3.10 or higher
```

### Linux only: Bluetooth permissions

On Linux, your user needs access to Bluetooth. Run once:

```bash
sudo usermod -aG bluetooth $USER
# Then log out and back in
```

---

## Installation

### Option A: Install from PyPI (recommended)

```bash
pip install dynoforce-ble
```

### Option B: Install from source

```bash
git clone https://github.com/Vadergit/DynoForce_BLE.git
cd DynoForce_BLE
pip install -e .
```

### Option C: With GUI example dependencies

```bash
pip install dynoforce-ble[gui]
```

> **Tip:** If `pip` doesn't work, try `pip3` or `python3 -m pip` instead.

> **Tip:** On macOS/Linux with system Python, use a virtual environment:
>
> ```bash
> python3 -m venv venv
> source venv/bin/activate   # macOS/Linux
> # or: venv\Scripts\activate  # Windows
> pip install dynoforce-ble
> ```

---

## Quick Start

### 1. Simplest possible script

Create a file `test.py`:

```python
import time
from dynoforce_ble import DynoForceSyncClient

# 1. Create client (auto-reconnect enabled by default)
client = DynoForceSyncClient()

# 2. Connect to first device found
print("Scanning for DynoForce device...")
client.connect_first()
print("Connected!")

# 3. Print force data as it comes in
client.on_state_packet(
    lambda p: print(f"Force: {p.force:.1f} kg | Peak: {p.peak:.1f} kg | Battery: {p.battery_percent}%")
)

# 4. Keep running for 30 seconds
try:
    time.sleep(30)
except KeyboardInterrupt:
    pass

# 5. Clean up
client.close()
print("Done!")
```

Run it:

```bash
python3 test.py
```

Expected output:

```
Scanning for DynoForce device...
Connected!
Force:   0.0 kg | Peak:   0.0 kg | Battery: 87%
Force:   0.1 kg | Peak:   0.1 kg | Battery: 87%
Force:  12.4 kg | Peak:  12.4 kg | Battery: 87%
Force:  45.7 kg | Peak:  45.7 kg | Battery: 87%
...
```

### 2. Using the `with` statement (recommended)

The `with` statement automatically disconnects when done:

```python
import time
from dynoforce_ble import DynoForceSyncClient

with DynoForceSyncClient() as client:
    client.connect_first()
    client.on_state_packet(lambda p: print(f"{p.force:.1f} kg"))
    time.sleep(10)
# Automatically disconnected here
```

### 3. Async API (for advanced users)

```python
import asyncio
from dynoforce_ble import DynoForceClient

async def main():
    async with DynoForceClient() as client:
        await client.connect_first()
        print(f"Connected: {client.device_info}")

        client.on_state_packet(
            lambda p: print(f"Force: {p.force:.1f} kg  Peak: {p.peak:.1f} kg")
        )
        await asyncio.sleep(10)

asyncio.run(main())
```

---

## Common Tasks

### Scan for devices (without connecting)

```python
from dynoforce_ble import DynoForceSyncClient

client = DynoForceSyncClient()
devices = client.scan(timeout=5.0)

print(f"Found {len(devices)} device(s):")
for d in devices:
    print(f"  {d.name} ({d.address}) RSSI={d.rssi} dBm")

client.close()
```

### Connect to a specific device

```python
client.connect("AA:BB:CC:DD:EE:FF")  # Use address from scan
```

### Filter by device type

```python
# Only find DynoGrip devices:
client.connect_first(name_filter="DynoGrip")

# Only find DynoPull devices:
client.connect_first(name_filter="DynoPull")

# Only find UnityCounter devices:
client.connect_first(name_filter="Unity")
```

### Calibrate the sensor

```python
import time
from dynoforce_ble import DynoForceSyncClient

with DynoForceSyncClient() as client:
    client.connect_first()

    # Step 1: Tare (zero) with NO weight on sensor
    client.tare()
    print("Tared! Now hang 20kg weight...")
    time.sleep(5)

    # Step 2: Calibrate with known weight
    client.calibrate(20.0)  # Weight in kg
    print("Calibration done!")
```

### Send device commands

```python
from dynoforce_ble import DynoForceSyncClient, Melody

with DynoForceSyncClient() as client:
    client.connect_first()

    client.tare()                          # Zero the scale
    client.calibrate(20.0)                 # Calibrate with 20kg
    client.play_melody(Melody.SUCCESS)     # Play a sound
    client.reset_peak()                    # Reset peak force
    client.set_tx_power(5)                 # BLE power (0-7)
    client.set_inactivity_timeout(300)     # 5 min alarm (0 = off)
    client.set_name("DynoGrip-Lab")       # Rename (max 20 chars, restarts device!)
```

### Log force data to CSV

```python
import csv
import time
from dynoforce_ble import DynoForceSyncClient

with DynoForceSyncClient() as client:
    client.connect_first()

    with open("force_log.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t_ms", "force_kg", "peak_kg", "battery_%"])

        def log_packet(p):
            writer.writerow([p.t_ms, f"{p.force:.2f}", f"{p.peak:.2f}", p.battery_percent])

        client.on_state_packet(log_packet)
        print("Logging to force_log.csv ... (Ctrl+C to stop)")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    print("Done!")
```

### Monitor connection state

```python
from dynoforce_ble import DynoForceSyncClient, ConnectionState

with DynoForceSyncClient() as client:
    def on_connection(state: ConnectionState):
        print(f"Connection: {state.value}")

    client.on_connection_change(on_connection)
    client.connect_first()
    # Will print: "Connection: scanning", "Connection: connecting", "Connection: ready"
```

### Unsubscribe from events

Every `on_*` method returns a function to stop listening:

```python
unsub = client.on_state_packet(my_callback)
# ... later:
unsub()  # Stop receiving packets in my_callback
```

---

## Live Dashboard (GUI Example)

A complete GUI application with real-time force graph, data display, and CSV logging is included.

### Run from installed package

```bash
pip install dynoforce-ble[gui]
python examples/live_dashboard.py
```

### Run from source

```bash
git clone https://github.com/Vadergit/DynoForce_BLE.git
cd DynoForce_BLE
pip install -e ".[gui]"
python examples/live_dashboard.py
```

Features:

* Auto-connects to first DynoForce device
* Real-time force graph (15 second rolling window at 30fps)
* Live data display: force, peak, battery, sample rate
* CSV logging with start/stop button
* Tare and Reset Peak buttons

---

## API Reference

### `DynoForceClient` (async) / `DynoForceSyncClient` (sync)

Both clients have the same methods. The sync client wraps async calls for convenience.

| Method                                        | Description                                    |
| --------------------------------------------- | ---------------------------------------------- |
| `connect_first(timeout=10, name_filter=None)` | Scan and connect to first device found         |
| `connect(address)`                            | Connect to specific BLE address/UUID           |
| `disconnect()`                                | Disconnect and stop auto-reconnect             |
| `scan(timeout=10, name_filter=None)`          | Scan for devices, returns list                 |
| `send_command(payload)`                       | Send raw command bytes                         |
| `tare()`                                      | Zero the scale at current load                 |
| `calibrate(known_weight_kg)`                  | Calibrate with known weight in kg              |
| `set_name(name)`                              | Rename device (max 20 chars, triggers reboot!) |
| `play_melody(melody_id)`                      | Play a predefined melody on device buzzer      |
| `reset_peak()`                                | Reset peak force display on device             |
| `set_tx_power(level)`                         | Set BLE transmit power 0-7 (5=default)         |
| `set_inactivity_timeout(seconds)`             | Set inactivity alarm (0=off)                   |

| Property           | Type                 | Description                    |
| ------------------ | -------------------- | ------------------------------ |
| `state`            | `ConnectionState`    | Current connection state       |
| `is_connected`     | `bool`               | True when streaming data       |
| `is_unity_counter` | `bool`               | True if device is UnityCounter |
| `device_info`      | `DeviceInfo \| None` | Device info (after connect)    |

### Events

| Method                        | Callback receives    | Rate             |
| ----------------------------- | -------------------- | ---------------- |
| `on_state_packet(cb)`         | `StatePacket`        | ~60 Hz           |
| `on_unity_counter_packet(cb)` | `UnityCounterPacket` | ~10 Hz           |
| `on_connection_change(cb)`    | `ConnectionState`    | On change        |
| `on_device_info(cb)`          | `DeviceInfo`         | Once per connect |
| `on_error(cb)`                | `Exception`          | On error         |

### Data Models

#### `StatePacket` (DynoGrip / DynoPull / DynoLift)

| Field                | Type                        | Description                                    |
| -------------------- | --------------------------- | ---------------------------------------------- |
| `t_ms`               | `int`                       | Device uptime in milliseconds                  |
| `force`              | `float`                     | Current force in kg                            |
| `peak`               | `float`                     | Peak force in current attempt (kg)             |
| `slope`              | `float`                     | Rate of force change                           |
| `attempt_count`      | `int`                       | Number of attempts                             |
| `battery_percent`    | `int`                       | Battery 0-100%                                 |
| `charging`           | `bool`                      | True if USB charging                           |
| `battery_voltage`    | `float \| None`             | Battery voltage (extended packet)              |
| `calibration_factor` | `float \| None`             | Calibration scale factor                       |
| `tare_offset`        | `int \| None`               | Zero-point ADC offset                          |
| `raw`                | `int \| None`               | Raw ADC value                                  |
| `calibration_status` | `CalibrationStatus \| None` | IDLE/TARE_OK/TARE_ERROR/FACTOR_OK/FACTOR_ERROR |
| `force_n`            | `float`                     | Force in Newtons (computed property)           |
| `force_lb`           | `float`                     | Force in pounds (computed property)            |

#### `UnityCounterPacket` (UnityCounter IMU)

| Field             | Type               | Description                                    |
| ----------------- | ------------------ | ---------------------------------------------- |
| `t_ms`            | `int`              | Device uptime in milliseconds                  |
| `angle_x`         | `float`            | Pitch angle in degrees                         |
| `angle_y`         | `float`            | Roll angle in degrees                          |
| `angle_z`         | `float`            | Tilt from vertical (0-180 degrees)             |
| `counter`         | `int`              | Current rep/hold counter                       |
| `duration_ms`     | `int`              | Current hold duration in ms                    |
| `attempts`        | `int`              | Total attempts this session                    |
| `record`          | `int`              | Session best                                   |
| `battery_percent` | `int`              | Battery 0-100%                                 |
| `active_mode`     | `UnityCounterMode` | BOULDER/FLIP/HANDSTAND/FRONT_LEVER/REP_COUNTER |
| `altitude`        | `float`            | Barometric altitude in meters                  |
| `temperature`     | `float`            | Temperature in Celsius                         |
| `holding`         | `bool`             | True if currently in a hold                    |
| `flip_type`       | `FlipType \| None` | FRONT/BACK/SIDE_LEFT/SIDE_RIGHT                |
| `flip_degrees`    | `int \| None`      | Rotation degrees (signed)                      |
| `accel_mag`       | `float \| None`    | Acceleration magnitude in g                    |

#### `DeviceInfo`

| Field               | Type  | Description                       |
| ------------------- | ----- | --------------------------------- |
| `product_line_code` | `int` | Raw product line byte             |
| `product_line`      | `str` | e.g. "DynoGrip-V1", "DynoPull-T1" |
| `hw_revision`       | `str` | e.g. "2.1"                        |
| `fw_version`        | `str` | e.g. "2.7.19"                     |
| `serial_number`     | `str` | 16-char hex string                |

### Constants & Enums

```python
from dynoforce_ble import (
    Command,            # TARE, CALIBRATE, SET_NAME, BUZZER, ...
    CalibrationStatus,  # IDLE, TARE_OK, TARE_ERROR, FACTOR_OK, FACTOR_ERROR
    Melody,             # BEEP, SUCCESS, FAILURE, START, STOP, ...
    ProductLineCode,    # DYNOGRIP_V1, DYNOPULL_T1, UNITY_COUNTER, ...
    UnityCounterMode,   # BOULDER, FLIP, HANDSTAND, FRONT_LEVER, REP_COUNTER
    FlipType,           # FRONT, BACK, SIDE_LEFT, SIDE_RIGHT
    ConnectionState,    # DISCONNECTED, SCANNING, CONNECTING, CONNECTED, READY, ERROR
)
```

---

## Troubleshooting

### "No DynoForce device found"

1. Make sure your device is **powered on** (LED should be on)
2. Make sure **no other app** (DynoForce app, nRF Connect, etc.) is connected to it
3. Move closer to the device (within 2-3 meters)
4. Try increasing the scan timeout: `client.connect_first(timeout=15)`

### "pip: command not found"

Use `pip3` or `python3 -m pip` instead:

```bash
python3 -m pip install dynoforce-ble
```

### "bleak not found" or BLE errors on Linux

Install BlueZ development libraries:

```bash
# Ubuntu/Debian:
sudo apt install bluetooth bluez libbluetooth-dev

# Fedora:
sudo dnf install bluez bluez-libs-devel
```

### Permission denied (Linux)

```bash
sudo usermod -aG bluetooth $USER
# Log out and back in
```

### macOS: Bluetooth permission dialog

On first run, macOS will ask for Bluetooth permission. Click **Allow**.
If you denied it, go to: System Settings > Privacy & Security > Bluetooth > add your Terminal app.

### Device disconnects frequently

The library has built-in auto-reconnect (up to 10 attempts with exponential backoff).
You can also disable it:

```python
client = DynoForceSyncClient(auto_reconnect=False)
```

---

## Examples

| File                                                       | Description                               |
| ---------------------------------------------------------- | ----------------------------------------- |
| [`examples/simple_connect.py`](examples/simple_connect.py) | Minimal: connect and print force values   |
| [`examples/log_to_csv.py`](examples/log_to_csv.py)         | Log force data to timestamped CSV         |
| [`examples/live_dashboard.py`](examples/live_dashboard.py) | Full GUI with real-time graph and logging |

---

## Requirements

* **Python** >= 3.10
* **[bleak](https://github.com/hbldh/bleak)** >= 0.21 (BLE communication)
* **matplotlib** + **numpy** (optional, only for `live_dashboard.py`)

## License

MIT -- see [LICENSE](LICENSE)
