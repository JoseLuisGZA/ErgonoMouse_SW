from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .configuration import ErgonoMouseSettings, firmware_key
from .paths import SOURCE_ROOT, resource_path
from .tooling import serial_ports


def manifest_path() -> Path:
    return resource_path("firmware", "manifest.json")


def load_manifest() -> dict[str, Any] | None:
    path = manifest_path()
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value.get("variants"), dict) else None


def resolve_firmware(settings: ErgonoMouseSettings) -> dict[str, Any] | None:
    manifest = load_manifest()
    if not manifest:
        return None
    key = firmware_key(settings)
    entry = manifest["variants"].get(key)
    if not entry:
        return None
    path = manifest_path().parent / entry["file"]
    if not path.is_file():
        return None
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != entry.get("sha256"):
        return None
    return {"key": key, "path": path, "entry": entry, "manifest": manifest}


def find_avrdude() -> tuple[Path, Path] | None:
    executable_name = "avrdude.exe" if os.name == "nt" else "avrdude"
    candidates = [
        resource_path("tools", "avrdude", "bin", executable_name),
        SOURCE_ROOT / ".bundle-tools" / "avrdude" / "bin" / executable_name,
        Path.home() / ".platformio" / "packages" / "tool-avrdude" / executable_name,
        Path.home() / ".platformio" / "packages" / "tool-avrdude" / "bin" / executable_name,
    ]
    system = shutil.which("avrdude")
    if system:
        candidates.append(Path(system))
    for executable in candidates:
        if not executable.is_file():
            continue
        config_candidates = [
            executable.parent.parent / "etc" / "avrdude.conf",
            executable.parent / "avrdude.conf",
            executable.parent.parent / "avrdude.conf",
        ]
        config = next((path for path in config_candidates if path.is_file()), None)
        if config:
            return executable, config
    return None


def installer_status(settings: ErgonoMouseSettings | None = None) -> dict[str, Any]:
    manifest = load_manifest()
    resolved = resolve_firmware(settings) if settings and manifest else None
    avrdude = find_avrdude()
    return {
        "precompiled": bool(manifest),
        "variantReady": bool(resolved) if settings else None,
        "variantCount": len(manifest["variants"]) if manifest else 0,
        "flasher": bool(avrdude),
        "ready": bool(manifest and avrdude and (resolved if settings else True)),
    }


def install_precompiled(settings: ErgonoMouseSettings, requested_port: str | None = None) -> dict[str, Any]:
    resolved = resolve_firmware(settings)
    if not resolved:
        return _failure("This configuration is not present in the verified firmware bundle.", "variant_missing")
    tools = find_avrdude()
    if not tools:
        return _failure("The packaged flashing tool is missing or damaged. Reinstall ErgonoMouse Setup.", "flasher_missing")
    ports = serial_ports()
    if requested_port and requested_port not in ports:
        return _failure("The selected device is no longer connected. Reconnect it and try again.", "port_missing")
    if not requested_port:
        if not ports:
            return _failure("No Pro Micro was found. Use a USB data cable, then reconnect the controller.", "no_device")
        if len(ports) > 1:
            return _failure("More than one serial device is connected. Select the ErgonoMouse port.", "port_required")
        requested_port = ports[0]

    boot_port = _enter_bootloader(requested_port, ports)
    executable, config = tools
    command = [
        str(executable),
        "-C",
        str(config),
        "-p",
        "atmega32u4",
        "-c",
        "avr109",
        "-P",
        boot_port,
        "-b",
        "57600",
        "-D",
        "-U",
        f"flash:w:{resolved['path']}:i",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    if result.returncode:
        return _failure(translate_flash_error(output), "flash_failed", output, result.returncode)
    return {
        "ok": True,
        "message": "Firmware installed. Keep the controller still for one second while it finds its centre.",
        "port": boot_port,
        "firmware": resolved["key"],
        "output": output,
        "exit_code": 0,
    }


def _enter_bootloader(port: str, previous_ports: list[str]) -> str:
    try:
        import serial

        connection = serial.Serial(port=port, baudrate=1200, timeout=0.3)
        connection.close()
    except Exception:
        return port

    previous = set(previous_ports)
    deadline = time.monotonic() + 8
    original_disappeared = False
    while time.monotonic() < deadline:
        current = set(serial_ports())
        new_ports = current - previous
        if new_ports:
            return sorted(new_ports)[0]
        if port not in current:
            original_disappeared = True
        elif original_disappeared:
            return port
        time.sleep(0.15)
    return port


def translate_flash_error(output: str) -> str:
    lowered = output.lower()
    if "permission denied" in lowered or "ser_open" in lowered:
        return "The serial port could not be opened. Close serial monitors and check USB/serial permissions."
    if "programmer is not responding" in lowered or "butterfly_recv" in lowered:
        return "The bootloader did not answer. Double-tap Reset on the Pro Micro, then retry immediately."
    if "can't open device" in lowered or "no such file" in lowered:
        return "The controller changed ports during reset. Reconnect it and retry."
    if "verification error" in lowered:
        return "Firmware verification failed. Try another USB cable or port, then flash again."
    return "Firmware installation failed. Reconnect the controller with a known USB data cable and retry."


def _failure(message: str, code: str, output: str = "", exit_code: int = 1) -> dict[str, Any]:
    return {"ok": False, "message": message, "code": code, "output": output, "exit_code": exit_code}
