from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from app.serial_service import SerialSession


class SerialServiceTests(unittest.TestCase):
    def test_rejects_arbitrary_device_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "number"):
            SerialSession().input("rm -rf")

    def test_requires_connection_for_numeric_input(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Connect"):
            SerialSession().input("4")

    def test_rejects_unknown_calibration_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            SerialSession().command("42")

    def test_button_and_encoder_diagnostics_are_allowed(self) -> None:
        session = SerialSession()
        for mode in ("6", "8", "9"):
            with self.assertRaisesRegex(RuntimeError, "Connect"):
                session.command(mode)

    def test_continuous_telemetry_is_enabled_once_across_diagnostic_modes(self) -> None:
        session = SerialSession()
        connection = Mock(is_open=True)
        session._connection = connection
        with patch("app.serial_service.time.sleep"):
            session.command("1")
            session.command("20")
        payload = b"".join(call.args[0] for call in connection.write.call_args_list).decode("ascii")
        self.assertEqual(payload.count(">e1\r\n"), 1)
        self.assertTrue(payload.endswith("1\r\n20\r\n"))

    def test_guided_tuning_sends_only_bounded_program_commands(self) -> None:
        session = SerialSession()
        connection = Mock(is_open=True)
        session._connection = connection
        with patch("app.serial_service.time.sleep"):
            levels = session.tune(
                movement=5,
                vertical=7,
                rotation=3,
                stability=9,
                curve_mode="adaptive",
                curve_precision=6,
                curve_boost=4,
            )

        payload = b"".join(call.args[0] for call in connection.write.call_args_list).decode("ascii")
        self.assertEqual(
            levels,
            {
                "movement": 5,
                "vertical": 7,
                "rotation": 3,
                "stability": 9,
                "curveMode": "adaptive",
                "curvePrecision": 6,
                "curveBoost": 4,
            },
        )
        self.assertIn(">p1\r\n>w28\r\n", payload)
        self.assertIn(">p2\r\n>w1.0\r\n", payload)
        self.assertIn(">p4\r\n>w2.0\r\n", payload)
        self.assertIn(">p10\r\n>w1.4\r\n", payload)
        self.assertIn(">p13\r\n>w3\r\n", payload)
        self.assertIn(">p14\r\n>w1.3\r\n", payload)
        self.assertIn(">p15\r\n>w1.05\r\n", payload)
        self.assertTrue(payload.endswith(">s\r\n"))

    def test_guided_tuning_rejects_out_of_range_levels(self) -> None:
        with self.assertRaisesRegex(ValueError, "integer from 1 to 9"):
            SerialSession().tune(movement=0, vertical=5, rotation=5, stability=5)

    def test_live_telemetry_is_parsed_into_structured_values(self) -> None:
        session = SerialSession()
        session._append("@TEL,10,-20,30,40,-50,60,5,18")
        result = session.output()
        self.assertEqual(result["telemetry"]["translation"], [10, -20, 30])
        self.assertEqual(result["telemetry"]["rotation"], [40, -50, 60])
        self.assertEqual(result["telemetry"]["keys"], [0, 2])
        self.assertEqual(result["telemetry"]["wheel"], 18)
        self.assertEqual(result["lines"], [])
        self.assertNotIn("@TEL", "\n".join(line["text"] for line in result["lines"]))

    def test_live_output_does_not_rescan_serial_ports_at_display_cadence(self) -> None:
        session = SerialSession()
        with patch("app.serial_service.serial_ports") as ports:
            result = session.output()
        ports.assert_not_called()
        self.assertFalse(result["connected"])

    def test_wheel_telemetry_reports_direction_without_rotating_a_visual(self) -> None:
        session = SerialSession()
        session._append("@TEL,0,0,0,0,0,0,0,18")
        session._append("@TEL,0,0,0,0,0,0,0,19")
        self.assertEqual(session.output()["telemetry"]["wheelDirection"], 1)
        session._append("@TEL,0,0,0,0,0,0,0,17")
        self.assertEqual(session.output()["telemetry"]["wheelDirection"], -1)

    def test_key_mapping_is_a_bounded_permutation_and_persisted(self) -> None:
        session = SerialSession()
        connection = Mock(is_open=True)
        session._connection = connection
        with patch("app.serial_service.time.sleep"):
            result = session.set_keymap([2, 1, 3])
        self.assertEqual(result, [2, 1, 3])
        payload = b"".join(call.args[0] for call in connection.write.call_args_list).decode("ascii")
        self.assertIn(">k1\r\n", payload)
        self.assertIn(">k100\r\n", payload)
        self.assertTrue(payload.endswith(">v\r\n"))
        with self.assertRaisesRegex(ValueError, "exactly once"):
            session.set_keymap([1, 1, 2])

    def test_axis_mapping_is_bounded_previewed_and_persisted(self) -> None:
        session = SerialSession()
        connection = Mock(is_open=True)
        session._connection = connection
        with patch("app.serial_service.time.sleep"):
            result = session.set_axis_mapping(["TZ", "RZ"], True, save=True)
        self.assertEqual(result, {"inverted": ["TZ", "RZ"], "swapGroups": True})
        payload = b"".join(call.args[0] for call in connection.write.call_args_list).decode("ascii")
        self.assertIn(">a100\r\n", payload)
        self.assertTrue(payload.endswith(">j\r\n"))
        with self.assertRaisesRegex(ValueError, "selected from"):
            session.set_axis_mapping(["BAD"], False)


if __name__ == "__main__":
    unittest.main()
