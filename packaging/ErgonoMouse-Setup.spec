import sys
from pathlib import Path

project_root = Path(SPECPATH).parent
sys.path.insert(0, str(project_root))

from app import __version__ as VERSION

analysis = Analysis(
    [str(project_root / "packaging" / "entrypoint.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "app" / "static"), "app/static"),
        (str(project_root / "pictures" / "ergonomouse.webp"), "pictures"),
        (str(project_root / "firmware"), "firmware"),
        (str(project_root / ".bundle-tools" / "avrdude"), "tools/avrdude"),
    ],
    hiddenimports=["serial", "serial.tools.list_ports"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="ErgonoMouse-Setup",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

bundle = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ErgonoMouse-Setup",
)

if sys.platform == "darwin":
    mac_app = BUNDLE(
        bundle,
        name="ErgonoMouse Setup.app",
        icon=None,
        bundle_identifier="org.ergonomouse.setup",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "ErgonoMouse Setup",
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
        },
    )
