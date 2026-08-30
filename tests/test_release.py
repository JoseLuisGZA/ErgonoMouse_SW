from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.configuration import firmware_key
from tools.build_firmware_matrix import build_fingerprint, variants


class ReleaseTests(unittest.TestCase):
    def test_matrix_contains_84_unique_valid_behaviors(self) -> None:
        generated = variants()
        self.assertEqual(len(generated), 84)
        self.assertEqual(len({firmware_key(settings) for settings in generated}), 84)
        for settings in generated:
            settings.validate()

    def test_build_fingerprint_is_stable_sha256(self) -> None:
        first = build_fingerprint()
        self.assertEqual(first, build_fingerprint())
        self.assertEqual(len(first), 64)

    def test_native_package_recipes_are_present(self) -> None:
        project = Path(__file__).resolve().parents[1]
        expected = (
            project / "packaging" / "linux" / "AppRun",
            project / "packaging" / "linux" / "ergonomouse-setup.desktop",
            project / "packaging" / "windows" / "ErgonoMouse-Setup.iss",
            project / "packaging" / "UNSIGNED_INSTALL.txt",
        )
        self.assertTrue(all(path.is_file() for path in expected))

    def test_macos_package_uses_native_signed_bundle(self) -> None:
        project = Path(__file__).resolve().parents[1]
        spec = (project / "packaging" / "ErgonoMouse-Setup.spec").read_text(encoding="utf-8")
        packager = (project / "tools" / "package_native.py").read_text(encoding="utf-8")
        workflow = (project / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("mac_app = BUNDLE(", spec)
        self.assertIn('bundle_identifier="org.ergonomouse.setup"', spec)
        self.assertIn("symlinks=True", packager)
        self.assertNotIn('["codesign", "--force"', packager)
        self.assertIn("codesign --verify --deep --strict", workflow)
        self.assertIn('ditto "$mount_point/ErgonoMouse Setup.app"', workflow)
        self.assertIn('if [[ "$GITHUB_REF_NAME" == *-rc.* ]]', workflow)
        self.assertNotIn('if [[ "$GITHUB_REF_NAME" == *-* ]]', workflow)

    def test_markdown_local_links_resolve(self) -> None:
        project = Path(__file__).resolve().parents[1]
        link_pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
        broken: list[str] = []
        for markdown in project.rglob("*.md"):
            relative = markdown.relative_to(project)
            if relative.parts[0] in {"artifacts", "build", "dist"} or any(
                part.startswith(".") for part in relative.parts
            ):
                continue
            for line_number, line in enumerate(markdown.read_text(encoding="utf-8").splitlines(), 1):
                for raw_target in link_pattern.findall(line):
                    target = raw_target.strip().split()[0].strip("<>")
                    if target.startswith(("http://", "https://", "mailto:", "#")):
                        continue
                    path_target = target.partition("#")[0]
                    if path_target and not (markdown.parent / path_target).resolve().exists():
                        broken.append(f"{relative}:{line_number}: {target}")
        self.assertEqual(broken, [])

    def test_hid_button_chords_preserve_existing_report_bits(self) -> None:
        project = Path(__file__).resolve().parents[1]
        source = (project / "spacemouse-keys" / "SpaceMouseHID.cpp").read_text(encoding="utf-8")
        self.assertIn("keyData[(bitNumber / 8)] |=", source)

    def test_kill_buttons_toggle_dominant_axis_precision_on_double_click(self) -> None:
        project = Path(__file__).resolve().parents[1]
        source = (project / "spacemouse-keys" / "spaceKeys.cpp").read_text(encoding="utf-8")
        loop = (project / "spacemouse-keys" / "spacemouse-keys.ino").read_text(encoding="utf-8")
        markup = (project / "app" / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn("KILL_BUTTON_DOUBLE_CLICK_MS = 500", source)
        self.assertIn("button.dominantOnly = !button.dominantOnly", source)
        self.assertIn("keepDominantAxis(velocity, TRANSX)", source)
        self.assertIn("keepDominantAxis(velocity, ROTX)", source)
        self.assertIn("applyKillButtons(velocity, keyVals);", loop)
        self.assertIn("How the precision buttons work", markup)
        self.assertIn("so only one axis works at a time", markup)
        self.assertIn("It stays on after release; double-click the same button again", markup)

    def test_runtime_key_mapping_is_versioned_and_separate_from_parameter_storage(self) -> None:
        project = Path(__file__).resolve().parents[1]
        source = (project / "spacemouse-keys" / "runtimeSettings.cpp").read_text(encoding="utf-8")
        self.assertIn("KEY_ORDER_VERSION = 1", source)
        self.assertIn("BASE_ADDRESS_PAR + sizeof(ParamStorage)", source)
        self.assertIn("recordIsValid", source)

    def test_runtime_axis_mapping_separates_baseline_from_user_overrides(self) -> None:
        project = Path(__file__).resolve().parents[1]
        source = (project / "spacemouse-keys" / "runtimeSettings.cpp").read_text(encoding="utf-8")
        loop = (project / "spacemouse-keys" / "spacemouse-keys.ino").read_text(encoding="utf-8")
        self.assertIn("AXIS_MAP_VERSION = 2", source)
        self.assertIn("(1U << TRANSX) | (1U << TRANSY) | (1U << ROTZ)", source)
        self.assertIn("DEFAULT_AXIS_MAP_FLAGS = 0", source)
        self.assertLess(
            source.index("BASELINE_AXIS_INVERT_FLAGS &"),
            source.index("if (runtimeAxisFlags & AXIS_SWAP_GROUPS_FLAG)"),
        )
        self.assertIn("AXIS_MAP_ADDRESS = KEY_ORDER_ADDRESS + sizeof(RuntimeKeyOrderRecord)", source)
        self.assertIn("applyRuntimeAxisMapping(velocity);", loop)

    def test_live_visualization_uses_physical_rotation_axes_and_centred_controls(self) -> None:
        project = Path(__file__).resolve().parents[1]
        script = (project / "app" / "static" / "app.js").read_text(encoding="utf-8")
        styles = (project / "app" / "static" / "app.css").read_text(encoding="utf-8")
        markup = (project / "app" / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn("translate3d(${tx * 27}px, ${tz * 25}px, ${ty * 30}px)", script)
        self.assertIn("rotateX(${-18 - rx * 38}deg)", script)
        self.assertIn("rotateY(${28 - rz * 42}deg)", script)
        self.assertIn("rotateZ(${-ry * 40}deg)", script)
        self.assertIn("rotateX(${-rx * 8}deg) rotateY(${-ry * 8}deg) rotateZ(${rz * 8}deg)", script)
        self.assertIn('$("#liveWheelUp").classList.toggle("active", wheelDirection > 0)', script)
        self.assertIn('$("#liveWheelDown").classList.toggle("active", wheelDirection < 0)', script)
        self.assertIn('<div class="axis-guide">', markup)
        self.assertIn('<span class="axis-line axis-x"><b>X</b></span>', markup)
        self.assertIn('<span class="axis-line axis-y"><b>Y</b></span>', markup)
        self.assertIn(".axis-guide { position: absolute; z-index: 3;", styles)
        self.assertIn('<div class="cube-stage" aria-hidden="true">', markup)
        self.assertIn(".cube-stage { position: relative; width: 112px; height: 158px;", styles)
        self.assertIn("top: 152px", styles)
        self.assertIn("background: #11161b", styles)
        self.assertIn("overflow: visible; background: var(--surface-soft);", styles)
        self.assertIn(".axis-y { transform: rotate(-133deg); }", styles)
        self.assertIn(".axis-y b { transform: rotate(133deg); }", styles)
        self.assertIn(".preference-list { overflow: hidden; flex-shrink: 0;", styles)
        self.assertIn("grid-template-columns: minmax(0,3fr) minmax(0,2fr)", styles)
        self.assertIn("padding: 14px 28px 14px 14px", styles)
        self.assertIn("const SERIAL_POLL_INTERVAL_MS = 16;", script)
        self.assertIn("window.setInterval(pollSerialOutput, SERIAL_POLL_INTERVAL_MS)", script)
        self.assertIn("state.installing || !hasDevice || !state.configured", script)
        calibration = (project / "spacemouse-keys" / "calibration.cpp").read_text(encoding="utf-8")
        self.assertIn("#define SETUP_TELEMETRY_INTERVAL_MS 10", calibration)
        self.assertNotIn("Assignments are saved with", markup)
        self.assertNotIn("Changes apply live and are saved with", markup)
        self.assertIn('<button id="applyTuning" class="secondary-button" type="button">Apply</button>', markup)
        self.assertIn("await persistTuningChanges();", script)
        self.assertIn('$("#applyTuning").addEventListener("click", applyTuning);', script)
        self.assertIn(".live-knob { position: absolute; left: 50%;", styles)
        self.assertIn(".live-top-keys, .live-bottom-keys { left: 50%;", styles)


if __name__ == "__main__":
    unittest.main()
