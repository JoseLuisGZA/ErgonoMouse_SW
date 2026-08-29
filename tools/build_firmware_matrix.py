#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from itertools import product
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import __version__ as FIRMWARE_VERSION  # noqa: E402
from app.configuration import (  # noqa: E402
    CONFIG_PATH,
    ErgonoMouseSettings,
    firmware_key,
    firmware_payload,
    write_config,
)
from app.tooling import find_pio  # noqa: E402


def build_fingerprint() -> str:
    """Fingerprint every input that can change compiled firmware bytes."""
    candidates = [PROJECT_ROOT / "app" / "configuration.py", PROJECT_ROOT / "platformio.ini", PROJECT_ROOT / "requirements-dev.txt"]
    candidates.extend(
        path
        for path in (PROJECT_ROOT / "spacemouse-keys").rglob("*")
        if path.is_file()
        and path.suffix in {".h", ".cpp", ".ino"}
        and path.name != "config.h"
        and not path.name.endswith(".ino.cpp")
    )
    digest = hashlib.sha256()
    for path in sorted(candidates):
        digest.update(str(path.relative_to(PROJECT_ROOT)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def variants() -> list[ErgonoMouseSettings]:
    results: dict[str, ErgonoMouseSettings] = {}
    for base, controls, exclusive in product(
        ("simple", "six_keys"),
        ("simple", "wheel", "buttons", "full"),
        (False, True),
    ):
        modes = ("kill", "hid") if controls in {"buttons", "full"} else ("kill",)
        axes = range(1, 7) if controls in {"wheel", "full"} else (2,)
        for mode, axis in product(modes, axes):
            settings = ErgonoMouseSettings(
                edition="complete",
                controller_style="knob",
                handedness="left" if base == "six_keys" else "symmetric",
                base_variant=base,
                control_variant=controls,
                controller_buttons_mode=mode,
                wheel_axis=axis,
                # Published lighting is powered directly and does not change firmware bytes.
                led_ring_enabled=True,
                exclusive_mode=exclusive,
                priority_z=exclusive,
            )
            try:
                settings.validate()
            except ValueError:
                continue
            results[firmware_key(settings)] = settings
    return [results[key] for key in sorted(results)]


def build_matrix(output_dir: Path, limit: int | None = None) -> dict[str, object]:
    pio = find_pio()
    if not pio:
        raise RuntimeError("PlatformIO is missing; run ./ergonomouse bootstrap")
    output_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = build_fingerprint()
    previous_manifest: dict[str, object] = {}
    manifest_path = output_dir / "manifest.json"
    if manifest_path.is_file():
        try:
            previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous_manifest = {}
    cache_valid = previous_manifest.get("buildFingerprint") == fingerprint
    previous_entries = previous_manifest.get("variants", {}) if cache_valid else {}
    original_config = CONFIG_PATH.read_bytes() if CONFIG_PATH.exists() else None
    entries: dict[str, object] = {}

    try:
        selected = variants()[:limit] if limit else variants()
        for index, settings in enumerate(selected, start=1):
            key = firmware_key(settings)
            destination = output_dir / f"{key}.hex"
            previous_entry = previous_entries.get(key, {}) if isinstance(previous_entries, dict) else {}
            if destination.is_file() and previous_entry:
                payload = destination.read_bytes()
                digest = hashlib.sha256(payload).hexdigest()
                if digest != previous_entry.get("sha256"):
                    destination.unlink()
                else:
                    entries[key] = {
                        "file": destination.name,
                        "sha256": digest,
                        "bytes": len(payload),
                        "configuration": firmware_payload(settings),
                    }
                    print(f"[{index:03}/{len(selected):03}] {key} {len(payload)} bytes (cached)")
                    continue
            write_config(settings)
            result = subprocess.run(
                [pio, "run", "-e", "micro"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
                env={**os.environ, "PLATFORMIO_SETTING_ENABLE_TELEMETRY": "No"},
            )
            if result.returncode:
                raise RuntimeError(f"Build {index}/{len(selected)} failed for {key}:\n{result.stdout}\n{result.stderr}")
            source = PROJECT_ROOT / ".pio" / "build" / "micro" / "firmware.hex"
            shutil.copy2(source, destination)
            payload = destination.read_bytes()
            entries[key] = {
                "file": destination.name,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "configuration": firmware_payload(settings),
            }
            print(f"[{index:03}/{len(selected):03}] {key} {len(payload)} bytes")
    finally:
        if original_config is None:
            CONFIG_PATH.unlink(missing_ok=True)
        else:
            CONFIG_PATH.write_bytes(original_config)

    manifest = {
        "schema": 2,
        "product": "ErgonoMouse SW",
        "firmwareVersion": FIRMWARE_VERSION,
        "board": "Arduino Pro Micro 5V/16MHz (ATmega32U4)",
        "buildFingerprint": fingerprint,
        "variants": entries,
    }
    referenced = {entry["file"] for entry in entries.values()}
    for stale_image in output_dir.glob("fw-*.hex"):
        if stale_image.name not in referenced:
            stale_image.unlink()
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the distributable ErgonoMouse firmware matrix")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "firmware")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    manifest = build_matrix(args.output, args.limit)
    print(f"Built {len(manifest['variants'])} unique firmware variants in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
