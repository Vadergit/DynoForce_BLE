"""Event/callback system for DynoForce BLE streaming."""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, Callable


class EventType(Enum):
    """Events emitted by DynoForceClient."""

    STATE_PACKET = auto()
    UNITY_COUNTER_PACKET = auto()
    DEVICE_INFO = auto()
    CONNECTION_CHANGE = auto()
    DEVICE_DISCOVERED = auto()
    ERROR = auto()


class ConnectionState(Enum):
    """Client connection state machine."""

    DISCONNECTED = "disconnected"
    SCANNING = "scanning"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCOVERING_SERVICES = "discovering"
    READY = "ready"
    ERROR = "error"


class EventEmitter:
    """Simple typed event emitter for BLE events."""

    def __init__(self) -> None:
        self._listeners: dict[EventType, list[Callable[..., Any]]] = {
            et: [] for et in EventType
        }

    def on(self, event: EventType, callback: Callable[..., Any]) -> Callable[[], None]:
        """Subscribe to an event. Returns an unsubscribe function."""
        self._listeners[event].append(callback)

        def unsubscribe() -> None:
            try:
                self._listeners[event].remove(callback)
            except ValueError:
                pass

        return unsubscribe

    def emit(self, event: EventType, *args: Any) -> None:
        """Emit an event to all listeners."""
        for cb in self._listeners[event]:
            try:
                cb(*args)
            except Exception:
                pass  # Listener errors must not crash the BLE loop

    def clear(self) -> None:
        """Remove all listeners."""
        for et in EventType:
            self._listeners[et].clear()
