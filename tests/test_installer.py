from __future__ import annotations

import unittest

from app.installer import translate_flash_error


class InstallerTests(unittest.TestCase):
    def test_translates_permission_failure(self) -> None:
        message = translate_flash_error("avrdude: ser_open(): Permission denied")
        self.assertIn("permissions", message)

    def test_translates_bootloader_failure(self) -> None:
        message = translate_flash_error("avrdude: butterfly_recv(): programmer is not responding")
        self.assertIn("Double-tap Reset", message)

    def test_unknown_failure_has_recovery_advice(self) -> None:
        message = translate_flash_error("unexpected status 42")
        self.assertIn("USB data cable", message)


if __name__ == "__main__":
    unittest.main()
