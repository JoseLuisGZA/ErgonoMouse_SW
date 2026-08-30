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

    def test_runtime_key_mapping_is_versioned_and_separate_from_parameter_storage(self) -> None:
        project = Path(__file__).resolve().parents[1]
        source = (project / "spacemouse-keys" / "runtimeSettings.cpp").read_text(encoding="utf-8")
        self.assertIn("KEY_ORDER_VERSION = 1", source)
        self.assertIn("BASE_ADDRESS_PAR + sizeof(ParamStorage)", source)
        self.assertIn("recordIsValid", source)

    def test_runtime_axis_mapping_is_versioned_and_corrects_z_directions(self) -> None:
        project = Path(__file__).resolve().parents[1]
        source = (project / "spacemouse-keys" / "runtimeSettings.cpp").read_text(encoding="utf-8")
        loop = (project / "spacemouse-keys" / "spacemouse-keys.ino").read_text(encoding="utf-8")
        self.assertIn("AXIS_MAP_VERSION = 1", source)
        self.assertIn("DEFAULT_AXIS_MAP_FLAGS = (1U << TRANSZ) | (1U << ROTZ)", source)
        self.assertIn("AXIS_MAP_ADDRESS = KEY_ORDER_ADDRESS + sizeof(RuntimeKeyOrderRecord)", source)
        self.assertIn("applyRuntimeAxisMapping(velocity);", loop)


if __name__ == "__main__":
    unittest.main()
