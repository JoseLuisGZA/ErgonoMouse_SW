from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .configuration import (
    PROJECT_ROOT,
    ErgonoMouseSettings,
    describe_settings,
    load_setup_state,
    load_settings,
    mark_setup_complete,
    model_catalog,
    render_config,
    write_config,
)
from .installer import install_precompiled, installer_status
from .paths import resource_path
from .serial_service import serial_session
from .tooling import run_platformio, status


STATIC_ROOT = resource_path("app", "static")
MAX_BODY_SIZE = 128 * 1024


class SetupHandler(BaseHTTPRequestHandler):
    server_version = "ErgonoMouseSetup/0.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib HTTP handler API
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/status":
            self._json(status())
            return
        if path == "/api/settings":
            settings = load_settings()
            self._json(
                {
                    "settings": asdict(settings),
                    "preview": render_config(settings),
                    "configuration": describe_settings(settings),
                    "catalog": model_catalog(),
                }
            )
            return
        if path == "/api/setup/state":
            self._json(load_setup_state())
            return
        if path == "/api/model":
            self._json(model_catalog())
            return
        if path == "/api/serial/status":
            self._json(serial_session.status())
            return
        if path == "/api/serial/output":
            try:
                after = int(parse_qs(parsed.query).get("after", ["0"])[0])
            except ValueError:
                after = 0
            self._json(serial_session.output(max(0, after)))
            return
        if path == "/api/serial/keymap":
            try:
                self._json({"ok": True, "mapping": serial_session.keymap(), **serial_session.status()})
            except (ValueError, RuntimeError, OSError) as error:
                self._json({"ok": False, "error": str(error)}, status_code=HTTPStatus.BAD_REQUEST)
            return
        if path == "/assets/ergonomouse.webp":
            self._file(resource_path("pictures", "ergonomouse.webp"))
            return
        if path in ("/", "/index.html"):
            self._file(STATIC_ROOT / "index.html")
            return

        requested = (STATIC_ROOT / path.lstrip("/")).resolve()
        if requested.is_relative_to(STATIC_ROOT.resolve()) and requested.is_file():
            self._file(requested)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802 - stdlib HTTP handler API
        path = urlparse(self.path).path
        try:
            if path == "/api/configure":
                settings = ErgonoMouseSettings.from_mapping(self._request_json())
                output_path = write_config(settings)
                self._json(
                    {
                        "ok": True,
                        "path": _display_path(output_path),
                        "preview": render_config(settings),
                        "configuration": describe_settings(settings),
                        "installer": installer_status(settings),
                    }
                )
                return
            if path == "/api/setup/complete":
                self._json({"ok": True, **mark_setup_complete()})
                return
            if path == "/api/build":
                self._json(run_platformio("build"))
                return
            if path == "/api/flash":
                self._json(run_platformio("flash"))
                return
            if path == "/api/install":
                body = self._request_json()
                serial_session.close()
                self._json(install_precompiled(load_settings(), body.get("port")))
                return
            if path == "/api/serial/open":
                body = self._request_json()
                self._json({"ok": True, **serial_session.open(str(body.get("port", "")))})
                return
            if path == "/api/serial/close":
                serial_session.close()
                self._json({"ok": True, **serial_session.status()})
                return
            if path == "/api/serial/command":
                body = self._request_json()
                serial_session.command(str(body.get("mode", "")))
                self._json({"ok": True, **serial_session.status()})
                return
            if path == "/api/serial/input":
                body = self._request_json()
                serial_session.input(str(body.get("value", "")))
                self._json({"ok": True, **serial_session.status()})
                return
            if path == "/api/serial/tune":
                body = self._request_json()
                levels = serial_session.tune(
                    movement=body.get("movement"),
                    vertical=body.get("vertical"),
                    rotation=body.get("rotation"),
                    stability=body.get("stability"),
                    curve_mode=body.get("curveMode", "adaptive"),
                    curve_precision=body.get("curvePrecision", 5),
                    curve_boost=body.get("curveBoost", 5),
                )
                self._json({"ok": True, "levels": levels, **serial_session.status()})
                return
            if path == "/api/serial/reset-center":
                serial_session.reset_center()
                self._json({"ok": True, **serial_session.status()})
                return
            if path == "/api/serial/keymap":
                body = self._request_json()
                if body.get("reset") is True:
                    mapping = serial_session.reset_keymap(body.get("count"))
                else:
                    mapping = serial_session.set_keymap(body.get("mapping"))
                self._json({"ok": True, "mapping": mapping, **serial_session.status()})
                return
        except (ValueError, RuntimeError, OSError, TypeError, json.JSONDecodeError) as error:
            self._json({"ok": False, "error": str(error)}, status_code=HTTPStatus.BAD_REQUEST)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        # Keep the terminal quiet except for errors and the app's own status messages.
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(format, *args)

    def _request_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid content length") from error
        if length <= 0 or length > MAX_BODY_SIZE:
            raise ValueError("Request body is empty or too large")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object")
        return value

    def _json(self, value: Any, status_code: int = HTTPStatus.OK) -> None:
        body = json.dumps(value).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    server = ThreadingHTTPServer((host, port), SetupHandler)
    url = f"http://{host}:{port}"
    print(f"ErgonoMouse Setup is ready at {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.35, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ErgonoMouse Setup.")
    finally:
        server.server_close()


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)
