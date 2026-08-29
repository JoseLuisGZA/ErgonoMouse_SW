#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def find_platformio_avrdude() -> tuple[Path, Path]:
    executable_name = "avrdude.exe" if os.name == "nt" else "avrdude"
    package = Path.home() / ".platformio" / "packages" / "tool-avrdude"
    executable = next((path for path in (package / executable_name, package / "bin" / executable_name) if path.is_file()), None)
    config = next((path for path in (package / "avrdude.conf", package / "etc" / "avrdude.conf") if path.is_file()), None)
    if not executable or not config:
        raise RuntimeError("PlatformIO avrdude is missing; install platformio/tool-avrdude first")
    return executable, config


def stage() -> Path:
    executable, config = find_platformio_avrdude()
    destination = PROJECT_ROOT / ".bundle-tools" / "avrdude"
    bin_dir = destination / "bin"
    etc_dir = destination / "etc"
    bin_dir.mkdir(parents=True, exist_ok=True)
    etc_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, bin_dir / executable.name)
    shutil.copy2(config, etc_dir / "avrdude.conf")
    strip = shutil.which("strip")
    if strip and sys.platform.startswith("linux"):
        subprocess.run([strip, "--strip-unneeded", str(bin_dir / executable.name)], check=True)
    elif strip and sys.platform == "darwin":
        subprocess.run([strip, "-x", str(bin_dir / executable.name)], check=True)
    return destination


if __name__ == "__main__":
    print(stage())
