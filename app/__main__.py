from __future__ import annotations

import argparse
import json
import sys

from .configuration import DEFAULT_SETTINGS, write_config
from .server import run_server
from .tooling import bootstrap, run_platformio, status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ergonomouse",
        description="Guided setup, build and flashing for ErgonoMouse firmware.",
    )
    subparsers = parser.add_subparsers(dest="command")

    start = subparsers.add_parser("start", help="open the local guided setup")
    start.add_argument("--host", default="127.0.0.1")
    start.add_argument("--port", type=int, default=8765)
    start.add_argument("--no-browser", action="store_true", help="do not open a browser automatically")

    subparsers.add_parser("doctor", help="check the local toolchain and connected device")
    subparsers.add_parser("bootstrap", help="install the pinned local PlatformIO toolchain")
    subparsers.add_parser("configure", help="generate the verified ErgonoMouse configuration")
    subparsers.add_parser("build", help="compile the firmware")
    subparsers.add_parser("flash", help="compile and upload to a connected Pro Micro")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "start"

    if command == "start":
        run_server(
            getattr(args, "host", "127.0.0.1"),
            getattr(args, "port", 8765),
            not getattr(args, "no_browser", False),
        )
        return 0
    if command == "doctor":
        print(json.dumps(status(), indent=2))
        return 0
    if command == "bootstrap":
        result = bootstrap()
    elif command == "configure":
        path = write_config(DEFAULT_SETTINGS)
        print(f"Generated {path}")
        return 0
    elif command in ("build", "flash"):
        result = run_platformio(command)
    else:
        parser.error(f"Unknown command: {command}")

    print(result["output"])
    return 0 if result["ok"] else int(result["exit_code"] or 1)


if __name__ == "__main__":
    sys.exit(main())
