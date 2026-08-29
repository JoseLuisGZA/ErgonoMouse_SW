from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .configuration import CONFIG_PATH, PROJECT_ROOT
from .paths import IS_FROZEN


def find_pio() -> str | None:
    local = PROJECT_ROOT / ".venv" / "bin" / "pio"
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    return shutil.which("pio") or shutil.which("platformio")


def serial_ports() -> list[str]:
    try:
        from serial.tools import list_ports

        discovered = sorted(
            {
                port.device
                for port in list_ports.comports()
                if port.device
                and (
                    port.vid is not None
                    or re.search(r"(?:ttyACM|ttyUSB|cu\.usbmodem|cu\.usbserial)", port.device)
                    or (sys.platform == "win32" and re.fullmatch(r"COM\d+", port.device, re.IGNORECASE))
                )
            }
        )
        if discovered or sys.platform in {"win32", "darwin"}:
            return discovered
    except ImportError:
        pass
    patterns = ("/dev/ttyACM*", "/dev/ttyUSB*", "/dev/cu.usbmodem*", "/dev/cu.usbserial*")
    return sorted({port for pattern in patterns for port in glob.glob(pattern)})


def status() -> dict[str, Any]:
    pio = find_pio()
    pio_version = None
    if pio:
        result = subprocess.run(
            [pio, "--version"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        pio_version = (result.stdout or result.stderr).strip()

    ports = serial_ports()
    from .configuration import load_settings
    from .installer import installer_status
    from .serial_service import serial_session

    packaged = installer_status(load_settings())
    return {
        "mode": "portable" if IS_FROZEN else "source",
        "python": {"ok": sys.version_info >= (3, 10), "version": sys.version.split()[0]},
        "platformio": {"ok": bool(pio), "version": pio_version},
        "installer": packaged,
        "serial": serial_session.status(),
        "config": {"ok": CONFIG_PATH.exists(), "path": _display_path(CONFIG_PATH)},
        "device": {"ok": bool(ports), "ports": ports},
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def run_platformio(target: str = "build", timeout: int = 300) -> dict[str, Any]:
    if IS_FROZEN:
        return {
            "ok": False,
            "exit_code": 2,
            "output": "Portable editions use verified precompiled firmware; choose Install firmware in the app.",
        }
    pio = find_pio()
    if not pio:
        return {
            "ok": False,
            "exit_code": 127,
            "output": "PlatformIO is not installed. Run ./ergonomouse bootstrap first.",
        }
    if not CONFIG_PATH.exists():
        return {
            "ok": False,
            "exit_code": 2,
            "output": "Firmware configuration is missing. Generate it before building.",
        }

    command = [pio, "run", "-e", "micro"]
    if target == "flash":
        command.extend(["-t", "upload"])
    elif target != "build":
        raise ValueError(f"Unsupported PlatformIO target: {target}")

    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "PLATFORMIO_SETTING_ENABLE_TELEMETRY": "No"},
        )
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or "") + (error.stderr or "")
        return {"ok": False, "exit_code": 124, "output": f"{output}\nOperation timed out.".strip()}

    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    return {"ok": result.returncode == 0, "exit_code": result.returncode, "output": output}


def bootstrap() -> dict[str, Any]:
    venv = PROJECT_ROOT / ".venv"
    python = venv / "bin" / "python"
    commands = []
    if not python.exists():
        commands.append([sys.executable, "-m", "venv", str(venv)])
    commands.append([str(python), "-m", "pip", "install", "-r", "requirements-dev.txt"])

    output: list[str] = []
    for command in commands:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        output.extend(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        if result.returncode:
            return {"ok": False, "exit_code": result.returncode, "output": "\n".join(output)}
    return {"ok": True, "exit_code": 0, "output": "\n".join(output)}
