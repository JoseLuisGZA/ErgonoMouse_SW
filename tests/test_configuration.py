from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.configuration import (
    DEFAULT_SETTINGS,
    ErgonoMouseSettings,
    describe_settings,
    firmware_key,
    load_setup_state,
    mark_setup_complete,
    migrate_settings,
    pin_plan,
    render_config,
)


class ConfigurationTests(unittest.TestCase):
    def test_free_default_matches_simple_model(self) -> None:
        output = render_config(DEFAULT_SETTINGS)
        self.assertIn("#define PINLIST {A1, A0, A3, A2, A7, A6, A9, A8}", output)
        self.assertIn("#define NUMKEYS 0", output)
        self.assertIn("#define ROTARY_AXIS 0", output)
        self.assertIn("wired directly to 5V and GND", output)
        self.assertNotIn("#define LEDpin", output)

    def test_complete_six_key_full_build_with_lighting_matches_published_wiring(self) -> None:
        settings = ErgonoMouseSettings(
            edition="complete",
            controller_style="joystick",
            handedness="left",
            base_variant="six_keys",
            control_variant="full",
            led_ring_enabled=True,
        )
        plan = pin_plan(settings)
        output = render_config(settings)
        self.assertEqual(plan["free_after_configuration"], 0)
        self.assertEqual(plan["assignments"]["base_buttons"], [10, 16, 14, 1, 0, 15])
        self.assertEqual(plan["assignments"]["controller_buttons"], [5, 7])
        self.assertEqual(plan["assignments"]["encoder"], [2, 3])
        self.assertIn("#define NUMKEYS 8", output)
        self.assertIn("#define KEYLIST {10, 16, 14, 1, 0, 15, 5, 7}", output)
        self.assertIn("#define NUMHIDKEYS 6", output)
        self.assertIn("#define NUMKILLKEYS 2", output)
        self.assertIn("#define ENCODER_CLK 3", output)
        self.assertIn("#define ENCODER_DT 2", output)
        self.assertIn("#define ROTARY_AXIS 2", output)

    def test_always_on_lighting_does_not_consume_a_signal_pin(self) -> None:
        settings = ErgonoMouseSettings(
            edition="complete",
            handedness="left",
            base_variant="six_keys",
            control_variant="full",
            led_ring_enabled=True,
        )
        settings.validate()
        plan = pin_plan(settings)
        self.assertNotIn("addressable LEDs", plan["reserved"].values())
        self.assertEqual(plan["assignments"]["lighting"], "5V and GND (no data pin)")

    def test_controller_buttons_can_be_cad_shortcuts(self) -> None:
        settings = ErgonoMouseSettings(
            edition="complete",
            control_variant="buttons",
            controller_buttons_mode="hid",
        )
        output = render_config(settings)
        self.assertIn("#define KEYLIST {5, 7}", output)
        self.assertIn("#define NUMHIDKEYS 2", output)
        self.assertIn("#define BUTTONLIST {SM_3, SM_4}", output)
        self.assertIn("#define NUMKILLKEYS 0", output)

    def test_free_edition_rejects_paid_variant_selection(self) -> None:
        with self.assertRaisesRegex(ValueError, "free model"):
            ErgonoMouseSettings(edition="free", control_variant="wheel").validate()

    def test_symmetric_build_rejects_six_key_base(self) -> None:
        with self.assertRaisesRegex(ValueError, "symmetric base"):
            ErgonoMouseSettings(edition="complete", handedness="symmetric", base_variant="six_keys").validate()

    def test_rejects_unknown_input_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown setting"):
            ErgonoMouseSettings.from_mapping({"edition": "free", "surprise": True})

    def test_v1_settings_are_migrated(self) -> None:
        migrated = migrate_settings(
            {
                "profile": "ergonomouse-mkxx",
                "wheel_enabled": True,
                "wheel_axis": 3,
                "led_ring_enabled": False,
            }
        )
        self.assertEqual(migrated["edition"], "complete")
        self.assertEqual(migrated["control_variant"], "full")
        self.assertEqual(migrated["wheel_axis"], 3)

    def test_description_exposes_physical_build_and_pin_budget(self) -> None:
        description = describe_settings(DEFAULT_SETTINGS)
        self.assertEqual(description["physical_build"]["base"], "simple")
        self.assertEqual(description["pin_plan"]["switches"], 0)

    def test_firmware_key_ignores_purely_physical_choices(self) -> None:
        knob = ErgonoMouseSettings(edition="complete", controller_style="knob", handedness="left")
        joystick = ErgonoMouseSettings(edition="complete", controller_style="joystick", handedness="right")
        self.assertEqual(firmware_key(knob), firmware_key(joystick))

    def test_firmware_key_ignores_direct_power_lighting(self) -> None:
        plain = ErgonoMouseSettings(edition="complete", led_ring_enabled=False)
        lit = ErgonoMouseSettings(edition="complete", led_ring_enabled=True)
        self.assertEqual(firmware_key(plain), firmware_key(lit))

    def test_setup_completion_is_persisted_separately(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "setup-state.json"
            with mock.patch("app.configuration.SETUP_STATE_PATH", state_path):
                self.assertEqual(load_setup_state(), {"completed": False})
                self.assertEqual(mark_setup_complete(), {"completed": True})
                self.assertEqual(load_setup_state(), {"completed": True})
                self.assertEqual(json.loads(state_path.read_text()), {"completed": True})


if __name__ == "__main__":
    unittest.main()
