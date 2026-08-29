#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import __version__ as VERSION  # noqa: E402
from tools.build_firmware_matrix import build_fingerprint, build_matrix  # noqa: E402
from tools.stage_avrdude import stage  # noqa: E402


def main() -> int:
    firmware = PROJECT_ROOT / "firmware"
    manifest = firmware / "manifest.json"
    try:
        manifest_fingerprint = json.loads(manifest.read_text(encoding="utf-8")).get("buildFingerprint")
    except (OSError, json.JSONDecodeError):
        manifest_fingerprint = None
    if manifest_fingerprint != build_fingerprint():
        build_matrix(firmware)
    else:
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        manifest_data["firmwareVersion"] = VERSION
        manifest.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")
    stage()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(PROJECT_ROOT / "packaging" / "ErgonoMouse-Setup.spec"),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )

    release_dir = PROJECT_ROOT / "dist" / "ErgonoMouse-Setup"
    for filename in ("LICENSE", "README.md"):
        shutil.copy2(PROJECT_ROOT / filename, release_dir / filename)
    for filename in ("START_HERE.txt", "UNSIGNED_INSTALL.txt"):
        shutil.copy2(PROJECT_ROOT / "packaging" / filename, release_dir / filename)

    artifacts = PROJECT_ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    system = platform.system().lower()
    machine = platform.machine().lower().replace("amd64", "x86_64")
    archive_base = artifacts / f"ErgonoMouse-Setup-{VERSION}-{system}-{machine}"
    archive = Path(shutil.make_archive(str(archive_base), "zip", PROJECT_ROOT / "dist", "ErgonoMouse-Setup"))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(archive)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
