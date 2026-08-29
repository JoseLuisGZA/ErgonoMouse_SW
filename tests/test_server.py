from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

from app.server import SetupHandler


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), SetupHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_home_page_loads(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/", timeout=3) as response:
            body = response.read().decode()
        self.assertEqual(response.status, 200)
        self.assertIn("Let’s set up your", body)
        self.assertEqual(body.count("data-screen="), 8)
        self.assertIn('id="connectContinue"', body)
        self.assertIn('data-go="2" disabled>Continue', body)
        self.assertIn('id="installSuccess"', body)
        self.assertIn('id="stageDots"', body)
        self.assertIn('id="controlChecklist"', body)
        self.assertIn("Hold to isolate motion", body)
        self.assertIn("data-screen=\"6\"", body)
        self.assertIn('id="resumeTuning"', body)
        self.assertIn('id="readyFineTune"', body)
        self.assertIn('id="motionCube"', body)
        self.assertIn('id="resetCenter"', body)
        self.assertIn('id="keyMappingCard"', body)
        self.assertIn('id="curveMode"', body)

    def test_status_is_json(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/api/status", timeout=5) as response:
            body = json.load(response)
        self.assertIn("python", body)
        self.assertIn("platformio", body)
        self.assertIn("device", body)

    def test_model_catalog_is_available(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/api/model", timeout=3) as response:
            body = json.load(response)
        self.assertEqual(body["source"], "MakerWorld model 1062479")
        self.assertIn("free", body["editions"])

    def test_setup_state_is_available(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/api/setup/state", timeout=3) as response:
            body = json.load(response)
        self.assertIsInstance(body["completed"], bool)

    def test_setup_can_be_marked_complete(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/setup/complete",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=b"{}",
        )
        with mock.patch("app.server.mark_setup_complete", return_value={"completed": True}):
            with urllib.request.urlopen(request, timeout=3) as response:
                body = json.load(response)
        self.assertEqual(body, {"ok": True, "completed": True})

    def test_serial_status_is_available_without_hardware(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/api/serial/status", timeout=3) as response:
            body = json.load(response)
        self.assertIn("available", body)
        self.assertFalse(body["connected"])

    def test_rejects_unknown_configuration_fields(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/configure",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"profile": "ergonomouse-mkxx", "unknown": True}).encode(),
        )
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(context.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
