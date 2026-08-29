#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import __version__ as VERSION

RELEASE_DIR = PROJECT_ROOT / "dist" / "ErgonoMouse-Setup"
MACOS_APP = PROJECT_ROOT / "dist" / "ErgonoMouse Setup.app"
ARTIFACTS = PROJECT_ROOT / "artifacts"
BUILD_DIR = PROJECT_ROOT / "build" / "native-packages"
APPIMAGETOOL_BASE = "https://github.com/AppImage/AppImageKit/releases/download/continuous"
APPIMAGETOOL_SHA256 = {
    "x86_64": "b90f4a8b18967545fda78a445b27680a1642f1ef9488ced28b65398f2be7add2",
}


def machine_name() -> str:
    machine = platform.machine().lower()
    if machine in {"amd64", "x86_64"}:
        return "x86_64"
    if machine in {"aarch64", "arm64"}:
        return "arm64"
    return machine


def write_checksum(artifact: Path) -> Path:
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    checksum = artifact.with_suffix(artifact.suffix + ".sha256")
    checksum.write_text(f"{digest}  {artifact.name}\n", encoding="utf-8")
    return checksum


def require_portable_release() -> None:
    if not (RELEASE_DIR / ("ErgonoMouse-Setup.exe" if os.name == "nt" else "ErgonoMouse-Setup")).is_file():
        raise RuntimeError("Portable release is missing; run python tools/package_release.py first")


def appimagetool() -> Path:
    architecture = machine_name()
    if architecture not in APPIMAGETOOL_SHA256:
        raise RuntimeError(f"AppImage packaging is not configured for {architecture}")
    tool = PROJECT_ROOT / ".bundle-tools" / f"appimagetool-{architecture}.AppImage"
    if not tool.is_file():
        tool.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(f"{APPIMAGETOOL_BASE}/appimagetool-{architecture}.AppImage", tool)
    digest = hashlib.sha256(tool.read_bytes()).hexdigest()
    if digest != APPIMAGETOOL_SHA256[architecture]:
        tool.unlink(missing_ok=True)
        raise RuntimeError("Downloaded appimagetool did not match its pinned SHA-256 checksum")
    tool.chmod(0o755)
    return tool


def build_appimage() -> Path:
    if platform.system() != "Linux":
        raise RuntimeError("AppImage packages must be built on Linux")
    require_portable_release()
    appdir = BUILD_DIR / "ErgonoMouse_Setup.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    binary_dir = appdir / "usr" / "bin" / "ErgonoMouse-Setup"
    shutil.copytree(RELEASE_DIR, binary_dir)
    shutil.copy2(PROJECT_ROOT / "packaging" / "linux" / "AppRun", appdir / "AppRun")
    (appdir / "AppRun").chmod(0o755)
    desktop = PROJECT_ROOT / "packaging" / "linux" / "ergonomouse-setup.desktop"
    shutil.copy2(desktop, appdir / desktop.name)
    applications = appdir / "usr" / "share" / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    shutil.copy2(desktop, applications / desktop.name)
    icon = PROJECT_ROOT / "app" / "static" / "favicon.svg"
    shutil.copy2(icon, appdir / "ergonomouse-setup.svg")
    icons = appdir / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps"
    icons.mkdir(parents=True, exist_ok=True)
    shutil.copy2(icon, icons / "ergonomouse-setup.svg")

    ARTIFACTS.mkdir(exist_ok=True)
    artifact = ARTIFACTS / f"ErgonoMouse-Setup-{VERSION}-linux-{machine_name()}.AppImage"
    artifact.unlink(missing_ok=True)
    env = {**os.environ, "ARCH": machine_name(), "APPIMAGE_EXTRACT_AND_RUN": "1"}
    subprocess.run([str(appimagetool()), "--no-appstream", str(appdir), str(artifact)], check=True, env=env)
    artifact.chmod(0o755)
    write_checksum(artifact)
    return artifact


def find_iscc() -> Path:
    candidates = [
        shutil.which("ISCC"),
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise RuntimeError("Inno Setup 6 is missing; install it before building the Windows installer")


def build_windows_installer() -> Path:
    if platform.system() != "Windows":
        raise RuntimeError("Windows installers must be built on Windows")
    require_portable_release()
    ARTIFACTS.mkdir(exist_ok=True)
    script = PROJECT_ROOT / "packaging" / "windows" / "ErgonoMouse-Setup.iss"
    subprocess.run(
        [
            str(find_iscc()),
            f"/DAppVersion={VERSION}",
            f"/DSourceDir={RELEASE_DIR}",
            f"/DOutputDir={ARTIFACTS}",
            str(script),
        ],
        check=True,
    )
    artifact = ARTIFACTS / f"ErgonoMouse-Setup-{VERSION}-windows-x86_64-setup.exe"
    if not artifact.is_file():
        raise RuntimeError(f"Inno Setup did not create {artifact}")
    write_checksum(artifact)
    return artifact


def build_macos_dmg() -> Path:
    if platform.system() != "Darwin":
        raise RuntimeError("DMG packages must be built on macOS")
    require_portable_release()
    if not MACOS_APP.is_dir():
        raise RuntimeError("Native macOS app bundle is missing; rebuild the portable release on macOS")
    subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(MACOS_APP)],
        check=True,
    )

    dmg_root = BUILD_DIR / "dmg-root"
    shutil.rmtree(dmg_root, ignore_errors=True)
    dmg_root.mkdir(parents=True)
    staged_app = dmg_root / MACOS_APP.name
    shutil.copytree(MACOS_APP, staged_app, symlinks=True)
    subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(staged_app)],
        check=True,
    )
    (dmg_root / "Applications").symlink_to("/Applications")
    shutil.copy2(PROJECT_ROOT / "packaging" / "UNSIGNED_INSTALL.txt", dmg_root / "READ_ME_FIRST.txt")

    ARTIFACTS.mkdir(exist_ok=True)
    artifact = ARTIFACTS / f"ErgonoMouse-Setup-{VERSION}-macos-{machine_name()}.dmg"
    artifact.unlink(missing_ok=True)
    subprocess.run(
        ["hdiutil", "create", "-volname", "ErgonoMouse Setup", "-srcfolder", str(dmg_root), "-ov", "-format", "UDZO", str(artifact)],
        check=True,
    )
    write_checksum(artifact)
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the native package for this operating system")
    parser.add_argument("--format", choices=("auto", "appimage", "windows", "dmg"), default="auto")
    args = parser.parse_args()
    selected = args.format
    if selected == "auto":
        selected = {"Linux": "appimage", "Windows": "windows", "Darwin": "dmg"}.get(platform.system(), "")
    builders = {"appimage": build_appimage, "windows": build_windows_installer, "dmg": build_macos_dmg}
    if selected not in builders:
        raise RuntimeError(f"No native package is configured for {platform.system()}")
    artifact = builders[selected]()
    print(artifact)
    print(artifact.with_suffix(artifact.suffix + ".sha256"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
