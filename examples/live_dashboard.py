#!/usr/bin/env python3
"""DynoForce Live Dashboard — real-time force graph, data display, and CSV logging.

Requirements:
    pip install dynoforce-ble[gui]

Features:
    - Auto-connect to first DynoForce device
    - Real-time force graph (15 second rolling window)
    - Live data display (force, peak, battery, sample rate)
    - CSV logging (start/stop)
    - Tare and Reset Peak buttons
"""

from __future__ import annotations

import csv
import threading
import time
import tkinter as tk
from collections import deque
from datetime import datetime
from pathlib import Path
from tkinter import ttk
from typing import Any

import matplotlib
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

matplotlib.use("TkAgg")

from dynoforce_ble import (  # noqa: E402
    ConnectionState,
    DeviceInfo,
    DynoForceSyncClient,
    Melody,
    StatePacket,
)

# ── Constants ───────────────────────────────────────────────────────

GRAPH_WINDOW_SECONDS = 15
GRAPH_MAX_SAMPLES = GRAPH_WINDOW_SECONDS * 60  # 15s at 60Hz = 900
GRAPH_FPS = 30
UI_THROTTLE_INTERVAL = 0.1  # 10Hz UI updates


# ── Data Buffer ─────────────────────────────────────────────────────

class DataBuffer:
    """Thread-safe ring buffer for force samples."""

    def __init__(self, maxlen: int = GRAPH_MAX_SAMPLES) -> None:
        self.times: deque[float] = deque(maxlen=maxlen)
        self.forces: deque[float] = deque(maxlen=maxlen)
        self.peaks: deque[float] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._start_time: float | None = None
        self._sample_count = 0
        self._rate_start = time.monotonic()
        self._rate_count = 0
        self.hz: float = 0.0

    def append(self, packet: StatePacket) -> None:
        now = time.monotonic()
        with self._lock:
            if self._start_time is None:
                self._start_time = now
            t = now - self._start_time
            self.times.append(t)
            self.forces.append(packet.force)
            self.peaks.append(packet.peak)
            self._sample_count += 1
            self._rate_count += 1

            # Update Hz every second
            elapsed = now - self._rate_start
            if elapsed >= 1.0:
                self.hz = self._rate_count / elapsed
                self._rate_count = 0
                self._rate_start = now

    def get_snapshot(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Get a copy of current data for plotting."""
        with self._lock:
            return (
                np.array(self.times),
                np.array(self.forces),
                np.array(self.peaks),
            )

    @property
    def total_samples(self) -> int:
        return self._sample_count

    def clear(self) -> None:
        with self._lock:
            self.times.clear()
            self.forces.clear()
            self.peaks.clear()
            self._start_time = None
            self._sample_count = 0


# ── CSV Logger ──────────────────────────────────────────────────────

class CSVLogger:
    """Manages CSV file writing for force data."""

    def __init__(self) -> None:
        self._file: Any = None
        self._writer: csv.writer | None = None
        self._count = 0
        self.active = False
        self.filepath: Path | None = None

    def start(self) -> Path:
        filename = f"dynoforce_{datetime.now():%Y%m%d_%H%M%S}.csv"
        self.filepath = Path(filename)
        self._file = open(self.filepath, "w", newline="")
        self._writer = csv.writer(self._file)
        self._writer.writerow([
            "timestamp", "device_t_ms", "force_kg", "peak_kg",
            "slope", "battery_pct", "battery_v",
        ])
        self._count = 0
        self.active = True
        return self.filepath

    def write(self, p: StatePacket) -> None:
        if not self.active or not self._writer:
            return
        self._writer.writerow([
            datetime.now().isoformat(timespec="milliseconds"),
            p.t_ms,
            f"{p.force:.3f}",
            f"{p.peak:.3f}",
            f"{p.slope:.3f}",
            p.battery_percent,
            f"{p.battery_voltage:.3f}" if p.battery_voltage is not None else "",
        ])
        self._count += 1
        if self._count % 60 == 0:
            self._file.flush()

    def stop(self) -> int:
        self.active = False
        count = self._count
        if self._file:
            self._file.close()
            self._file = None
        self._writer = None
        return count

    @property
    def count(self) -> int:
        return self._count


# ── Dashboard App ───────────────────────────────────────────────────

class LiveDashboard:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DynoForce Live Dashboard")
        self.root.geometry("800x900")
        self.root.minsize(700, 750)

        self.data = DataBuffer()
        self.logger = CSVLogger()
        self._last_packet: StatePacket | None = None
        self._last_ui_update = 0.0
        self._anim: FuncAnimation | None = None

        # BLE client
        self.client = DynoForceSyncClient(auto_reconnect=True)

        # UI Variables
        self.conn_var = tk.StringVar(value="Disconnected")
        self.device_var = tk.StringVar(value="No device")
        self.force_var = tk.StringVar(value="Force: --.- kg")
        self.peak_var = tk.StringVar(value="Peak:  --.- kg")
        self.battery_var = tk.StringVar(value="Battery: --%")
        self.rate_var = tk.StringVar(value="Rate: -- Hz")
        self.samples_var = tk.StringVar(value="Samples: 0")
        self.cal_var = tk.StringVar(value="Cal: --")
        self.log_var = tk.StringVar(value="Logging: Off")
        self.status_var = tk.StringVar(value="Starting...")

        self._build_ui()
        self._setup_events()

        # Auto-connect in background
        self.root.after(100, self._auto_connect)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)

        # ── Title ───────────────────────────────────────────────────
        title_frame = ttk.Frame(frame)
        title_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(
            title_frame, text="DynoForce Live Dashboard",
            font=("Helvetica", 18, "bold"),
        ).pack(side="left")

        # ── Connection ──────────────────────────────────────────────
        conn_card = ttk.LabelFrame(frame, text="Connection", padding=8)
        conn_card.pack(fill="x", pady=(0, 8))

        row1 = ttk.Frame(conn_card)
        row1.pack(fill="x")
        ttk.Label(row1, textvariable=self.conn_var, font=("Menlo", 11, "bold")).pack(side="left")
        self.conn_btn = ttk.Button(row1, text="Reconnect", command=self._cmd_reconnect)
        self.conn_btn.pack(side="right")

        row2 = ttk.Frame(conn_card)
        row2.pack(fill="x", pady=(2, 0))
        ttk.Label(row2, textvariable=self.device_var, font=("Menlo", 11)).pack(side="left")

        # ── Live Data ───────────────────────────────────────────────
        data_card = ttk.LabelFrame(frame, text="Live Data", padding=8)
        data_card.pack(fill="x", pady=(0, 8))

        data_grid = ttk.Frame(data_card)
        data_grid.pack(fill="x")

        # Left column
        left = ttk.Frame(data_grid)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, textvariable=self.force_var, font=("Menlo", 14, "bold")).pack(anchor="w")
        ttk.Label(left, textvariable=self.peak_var, font=("Menlo", 14)).pack(anchor="w")

        # Right column
        right = ttk.Frame(data_grid)
        right.pack(side="right", fill="x", expand=True)
        ttk.Label(right, textvariable=self.battery_var, font=("Menlo", 11)).pack(anchor="e")
        ttk.Label(right, textvariable=self.rate_var, font=("Menlo", 11)).pack(anchor="e")
        ttk.Label(right, textvariable=self.samples_var, font=("Menlo", 11)).pack(anchor="e")

        ttk.Label(data_card, textvariable=self.cal_var, font=("Menlo", 10)).pack(anchor="w", pady=(4, 0))

        # ── Graph ───────────────────────────────────────────────────
        graph_card = ttk.LabelFrame(frame, text="Force Graph (15s)", padding=4)
        graph_card.pack(fill="both", expand=True, pady=(0, 8))

        self.fig = Figure(figsize=(7, 3.5), dpi=100, facecolor="#f5f5f5")
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel("Time (s)", fontsize=9)
        self.ax.set_ylabel("Force (kg)", fontsize=9)
        self.ax.set_facecolor("#fafafa")
        self.ax.grid(True, alpha=0.3)
        self.ax.set_ylim(-5, 100)
        self.ax.set_xlim(0, GRAPH_WINDOW_SECONDS)

        (self.line_force,) = self.ax.plot([], [], "b-", linewidth=1.5, label="Force")
        (self.line_peak,) = self.ax.plot([], [], "r--", linewidth=1, alpha=0.6, label="Peak")
        self.ax.legend(loc="upper right", fontsize=8)

        self.fig.tight_layout(pad=1.5)

        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_card)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Start animation
        self._anim = FuncAnimation(
            self.fig,
            self._update_graph,
            interval=1000 // GRAPH_FPS,
            blit=True,
            cache_frame_data=False,
        )

        # ── Controls ────────────────────────────────────────────────
        ctrl_card = ttk.LabelFrame(frame, text="Controls", padding=8)
        ctrl_card.pack(fill="x", pady=(0, 8))

        btn_row = ttk.Frame(ctrl_card)
        btn_row.pack(fill="x")

        ttk.Button(btn_row, text="Tare (Zero)", command=self._cmd_tare).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Reset Peak", command=self._cmd_reset_peak).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Beep", command=self._cmd_beep).pack(side="left", padx=(0, 20))

        self.log_btn = ttk.Button(btn_row, text="Start Log", command=self._cmd_toggle_log)
        self.log_btn.pack(side="left", padx=(0, 8))
        ttk.Label(btn_row, textvariable=self.log_var, font=("Menlo", 10)).pack(side="left")

        # ── Status ──────────────────────────────────────────────────
        status_bar = ttk.Frame(frame)
        status_bar.pack(fill="x")
        ttk.Label(status_bar, textvariable=self.status_var, foreground="#555", wraplength=700).pack(anchor="w")

    def _setup_events(self) -> None:
        self.client.on_state_packet(self._on_state_packet)
        self.client.on_connection_change(self._on_connection_change)
        self.client.on_device_info(self._on_device_info)
        self.client.on_error(self._on_error)

    # ── BLE Callbacks (called from BLE thread) ──────────────────────

    def _on_state_packet(self, packet: StatePacket) -> None:
        self.data.append(packet)
        self._last_packet = packet

        # Log if active
        if self.logger.active:
            self.logger.write(packet)

        # Throttled UI update
        now = time.monotonic()
        if now - self._last_ui_update < UI_THROTTLE_INTERVAL:
            return
        self._last_ui_update = now

        self.root.after(0, self._update_live_data, packet)

    def _on_connection_change(self, state: ConnectionState) -> None:
        self.root.after(0, self._update_connection, state)

    def _on_device_info(self, info: DeviceInfo) -> None:
        self.root.after(0, lambda: self.device_var.set(
            f"{info.product_line}  fw={info.fw_version}  sn={info.serial_number}"
        ))

    def _on_error(self, error: Exception) -> None:
        self.root.after(0, lambda: self.status_var.set(f"Error: {error}"))

    # ── UI Updates (called on main thread) ──────────────────────────

    def _update_live_data(self, p: StatePacket) -> None:
        self.force_var.set(f"Force: {p.force:7.1f} kg")
        self.peak_var.set(f"Peak:  {p.peak:7.1f} kg")
        self.battery_var.set(
            f"Battery: {p.battery_percent}%"
            + (f" ({p.battery_voltage:.2f}V)" if p.battery_voltage else "")
        )
        self.rate_var.set(f"Rate: {self.data.hz:.0f} Hz")
        self.samples_var.set(f"Samples: {self.data.total_samples:,}")

        if p.calibration_status is not None and p.calibration_factor is not None:
            self.cal_var.set(
                f"Cal: {p.calibration_status.name}  "
                f"Factor={p.calibration_factor:.2f}  "
                f"Tare={p.tare_offset}  Raw={p.raw}"
            )

        if self.logger.active:
            self.log_var.set(f"Logging: {self.logger.count:,} samples")

    def _update_connection(self, state: ConnectionState) -> None:
        name = state.value.capitalize()
        self.conn_var.set(name)
        self.status_var.set(f"Connection: {name}")

        if state == ConnectionState.READY:
            self.conn_btn.config(text="Disconnect")
        elif state == ConnectionState.DISCONNECTED:
            self.conn_btn.config(text="Reconnect")

    def _update_graph(self, _frame: int) -> tuple:
        times, forces, peaks = self.data.get_snapshot()

        if len(times) == 0:
            return (self.line_force, self.line_peak)

        self.line_force.set_data(times, forces)
        self.line_peak.set_data(times, peaks)

        # Scroll x-axis
        t_max = times[-1]
        t_min = max(0, t_max - GRAPH_WINDOW_SECONDS)
        self.ax.set_xlim(t_min, t_min + GRAPH_WINDOW_SECONDS)

        # Auto-scale y-axis
        visible = forces[times >= t_min]
        if len(visible) > 0:
            y_min = max(-10, float(np.min(visible)) - 5)
            y_max = max(10, float(np.max(visible)) + 10)
            # Include peak line in range
            visible_peaks = peaks[times >= t_min]
            if len(visible_peaks) > 0:
                y_max = max(y_max, float(np.max(visible_peaks)) + 10)
            self.ax.set_ylim(y_min, y_max)

        return (self.line_force, self.line_peak)

    # ── Commands ────────────────────────────────────────────────────

    def _auto_connect(self) -> None:
        self.status_var.set("Scanning for DynoForce device...")

        def _connect() -> None:
            try:
                self.client.connect_first()
                self.root.after(0, lambda: self.status_var.set("Connected!"))
            except ConnectionError:
                self.root.after(0, lambda: self.status_var.set(
                    "No device found. Click 'Reconnect' to try again."
                ))
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Connection error: {e}"))

        threading.Thread(target=_connect, daemon=True).start()

    def _cmd_reconnect(self) -> None:
        if self.client.is_connected:
            self.status_var.set("Disconnecting...")
            threading.Thread(target=self.client.disconnect, daemon=True).start()
            self.data.clear()
        else:
            self._auto_connect()

    def _cmd_tare(self) -> None:
        if not self.client.is_connected:
            self.status_var.set("Not connected")
            return
        threading.Thread(target=self.client.tare, daemon=True).start()
        self.status_var.set("Tare command sent")

    def _cmd_reset_peak(self) -> None:
        if not self.client.is_connected:
            self.status_var.set("Not connected")
            return
        threading.Thread(target=self.client.reset_peak, daemon=True).start()
        self.status_var.set("Reset Peak sent")

    def _cmd_beep(self) -> None:
        if not self.client.is_connected:
            self.status_var.set("Not connected")
            return
        threading.Thread(
            target=lambda: self.client.play_melody(Melody.BEEP), daemon=True
        ).start()

    def _cmd_toggle_log(self) -> None:
        if self.logger.active:
            count = self.logger.stop()
            self.log_btn.config(text="Start Log")
            self.log_var.set("Logging: Off")
            self.status_var.set(f"Saved {count:,} samples to {self.logger.filepath}")
        else:
            path = self.logger.start()
            self.log_btn.config(text="Stop Log")
            self.log_var.set("Logging: 0 samples")
            self.status_var.set(f"Logging to {path}")

    def _on_close(self) -> None:
        if self.logger.active:
            self.logger.stop()
        if self._anim:
            self._anim.event_source.stop()
        self.client.close()
        self.root.destroy()


# ── Main ────────────────────────────────────────────────────────────

def main() -> None:
    root = tk.Tk()
    LiveDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
