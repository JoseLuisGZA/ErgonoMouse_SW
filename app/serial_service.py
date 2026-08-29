from __future__ import annotations

import re
import threading
import time
from collections import deque
from typing import Any

from .tooling import serial_ports


ALLOWED_MODES = {"0", "1", "4", "6", "8", "9", "11", "20", "30", "40", "99", "ESC"}

CURVE_MODES = {"linear": 0, "precision": 1, "adaptive": 3}
CURVE_PRECISION = {1: 1.0, 2: 1.04, 3: 1.08, 4: 1.12, 5: 1.15, 6: 1.3, 7: 1.55, 8: 2.0, 9: 3.0}
CURVE_BOOST = {1: 0.65, 2: 0.8, 3: 0.95, 4: 1.05, 5: 1.15, 6: 1.25, 7: 1.33, 8: 1.4, 9: 1.46}
TELEMETRY_PATTERN = re.compile(
    r"^@TEL,(-?\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+),(\d+),(-?\d+)$"
)

MOVEMENT_SENSITIVITY = {1: 1.6, 2: 1.42, 3: 1.25, 4: 1.12, 5: 1.0, 6: 0.9, 7: 0.8, 8: 0.72, 9: 0.65}
VERTICAL_SENSITIVITY = {
    1: (3.4, 2.2),
    2: (3.15, 2.0),
    3: (2.9, 1.8),
    4: (2.7, 1.65),
    5: (2.5, 1.5),
    6: (2.25, 1.35),
    7: (2.0, 1.2),
    8: (1.8, 1.05),
    9: (1.6, 0.9),
}
ROTATION_SENSITIVITY = {1: 1.8, 2: 1.6, 3: 1.4, 4: 1.27, 5: 1.15, 6: 1.02, 7: 0.9, 8: 0.8, 9: 0.7}
STABILITY_DEADZONE = {1: 8, 2: 10, 3: 12, 4: 14, 5: 15, 6: 17, 7: 20, 8: 24, 9: 28}


class SerialSession:
    def __init__(self) -> None:
        self._connection: Any = None
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._lines: deque[dict[str, Any]] = deque(maxlen=800)
        self._sequence = 0
        self._telemetry = {
            "translation": [0, 0, 0],
            "rotation": [0, 0, 0],
            "keyMask": 0,
            "keys": [],
            "wheel": 0,
        }
        self.port: str | None = None

    @property
    def available(self) -> bool:
        try:
            import serial  # noqa: F401

            return True
        except ImportError:
            return False

    @property
    def connected(self) -> bool:
        return bool(self._connection and getattr(self._connection, "is_open", False))

    def open(self, port: str) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("Serial support is missing from this installation")
        if port not in serial_ports():
            raise ValueError("The selected serial device is not connected")
        self.close()
        import serial

        self._connection = serial.Serial(port=port, baudrate=115200, timeout=0.15)
        self.port = port
        self._stop.clear()
        self._reader = threading.Thread(target=self._read_loop, name="ergonomouse-serial", daemon=True)
        self._reader.start()
        return self.status()

    def close(self) -> None:
        self._stop.set()
        connection = self._connection
        self._connection = None
        self.port = None
        if connection:
            try:
                connection.close()
            except Exception:
                pass
        reader = self._reader
        if reader and reader is not threading.current_thread():
            reader.join(timeout=1)
        self._reader = None

    def command(self, mode: str) -> None:
        normalized = mode.upper()
        if normalized not in ALLOWED_MODES:
            raise ValueError("Unsupported calibration command")
        if not self.connected:
            raise RuntimeError("Connect to the ErgonoMouse before starting calibration")
        payload = "\x1b" if normalized == "ESC" else f"{normalized}\r\n"
        self._connection.write(payload.encode("ascii"))

    def input(self, value: str) -> None:
        normalized = value.strip()
        if normalized.lower() in {"q", "esc"}:
            payload = "\x1b"
        elif re.fullmatch(r"-?\d+(?:\.\d+)?", normalized):
            payload = f"{normalized}\r\n"
        else:
            raise ValueError("Enter a number, q, or ESC")
        if not self.connected:
            raise RuntimeError("Connect to the ErgonoMouse before sending device input")
        self._connection.write(payload.encode("ascii"))

    def tune(
        self,
        movement: int,
        vertical: int,
        rotation: int,
        stability: int,
        curve_mode: str = "adaptive",
        curve_precision: int = 5,
        curve_boost: int = 5,
    ) -> dict[str, Any]:
        levels = {
            "movement": self._tuning_level("movement", movement),
            "vertical": self._tuning_level("vertical", vertical),
            "rotation": self._tuning_level("rotation", rotation),
            "stability": self._tuning_level("stability", stability),
            "curvePrecision": self._tuning_level("curve precision", curve_precision),
            "curveBoost": self._tuning_level("curve boost", curve_boost),
        }
        if curve_mode not in CURVE_MODES:
            raise ValueError("curve mode must be linear, precision, or adaptive")
        levels["curveMode"] = curve_mode
        if not self.connected:
            raise RuntimeError("Connect to the ErgonoMouse before applying tuning")

        vertical_positive, vertical_negative = VERTICAL_SENSITIVITY[levels["vertical"]]
        movement_value = MOVEMENT_SENSITIVITY[levels["movement"]]
        rotation_value = ROTATION_SENSITIVITY[levels["rotation"]]
        parameters = (
            (1, STABILITY_DEADZONE[levels["stability"]]),
            (2, movement_value),
            (3, movement_value),
            (4, vertical_positive),
            (5, vertical_negative),
            (10, rotation_value),
            (11, rotation_value),
            (12, rotation_value),
            (13, CURVE_MODES[curve_mode]),
            (14, CURVE_PRECISION[levels["curvePrecision"]]),
            (15, CURVE_BOOST[levels["curveBoost"]]),
        )
        for index, value in parameters:
            self._program_command(f">p{index}")
            self._program_command(f">w{value}")
        self._program_command(">s")
        return levels

    def reset_center(self) -> None:
        self.command("11")
        time.sleep(2.4)

    def set_keymap(self, mapping: list[int]) -> list[int]:
        if not self.connected:
            raise RuntimeError("Connect to the ErgonoMouse before changing key assignments")
        if not isinstance(mapping, list) or not 1 <= len(mapping) <= 8:
            raise ValueError("key mapping must contain between one and eight keys")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in mapping):
            raise ValueError("key mapping values must be integers")
        if sorted(mapping) != list(range(1, len(mapping) + 1)):
            raise ValueError("each logical key number must be assigned exactly once")
        for physical_index, logical_number in enumerate(mapping):
            self._program_command(f">k{physical_index * 100 + logical_number - 1}")
        self._program_command(">v")
        return mapping

    def keymap(self) -> list[int]:
        if not self.connected:
            raise RuntimeError("Connect to the ErgonoMouse before reading key assignments")
        with self._lock:
            after = self._sequence
        self._program_command(">b")
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            with self._lock:
                replies = [
                    entry["text"] for entry in self._lines
                    if entry["sequence"] > after and entry["text"].startswith("<b")
                ]
            if replies:
                payload = replies[-1][2:]
                if not payload:
                    return []
                mapping = [int(value) for value in payload.split(",")]
                if sorted(mapping) != list(range(1, len(mapping) + 1)):
                    raise RuntimeError("The controller returned an invalid key assignment")
                return mapping
            time.sleep(0.02)
        raise RuntimeError("The controller did not return its key assignments")

    def reset_keymap(self, count: int) -> list[int]:
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 8:
            raise ValueError("key count must be an integer from 1 to 8")
        if not self.connected:
            raise RuntimeError("Connect to the ErgonoMouse before changing key assignments")
        self._program_command(">u")
        return list(range(1, count + 1))

    @staticmethod
    def _tuning_level(name: str, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value not in range(1, 10):
            raise ValueError(f"{name} tuning must be an integer from 1 to 9")
        return value

    def _program_command(self, command: str) -> None:
        self._connection.write(f"{command}\r\n".encode("ascii"))
        self._connection.flush()
        time.sleep(0.035)

    def output(self, after: int = 0) -> dict[str, Any]:
        with self._lock:
            lines = [entry for entry in self._lines if entry["sequence"] > after]
            sequence = self._sequence
            telemetry = dict(self._telemetry)
        return {"lines": lines, "sequence": sequence, "telemetry": telemetry, **self.status()}

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "connected": self.connected,
            "port": self.port,
            "ports": serial_ports(),
        }

    def _read_loop(self) -> None:
        buffer = bytearray()
        while not self._stop.is_set() and self._connection:
            try:
                chunk = self._connection.read(512)
            except Exception as error:
                self._append(f"Connection lost: {error}", "error")
                break
            if not chunk:
                continue
            buffer.extend(chunk)
            while b"\n" in buffer or b"\r" in buffer:
                indexes = [index for token in (b"\n", b"\r") if (index := buffer.find(token)) >= 0]
                index = min(indexes)
                raw = bytes(buffer[:index])
                del buffer[: index + 1]
                if raw:
                    self._append(raw.decode("utf-8", errors="replace"))
        if buffer:
            self._append(buffer.decode("utf-8", errors="replace"))

    def _append(self, text: str, kind: str = "data") -> None:
        match = TELEMETRY_PATTERN.fullmatch(text.strip())
        with self._lock:
            if match:
                values = [int(value) for value in match.groups()]
                key_mask = values[6]
                self._telemetry = {
                    "translation": values[0:3],
                    "rotation": values[3:6],
                    "keyMask": key_mask,
                    "keys": [index for index in range(16) if key_mask & (1 << index)],
                    "wheel": values[7],
                }
            self._sequence += 1
            self._lines.append(
                {"sequence": self._sequence, "time": round(time.time(), 3), "kind": kind, "text": text}
            )


serial_session = SerialSession()
