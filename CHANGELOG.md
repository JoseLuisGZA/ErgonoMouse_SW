# Changelog

All notable ErgonoMouse SW releases are documented here. Tags use the `ergonomouse-sw-vX.Y.Z` prefix to avoid collisions with upstream firmware tags.

## Unreleased

## 4.4.0-rc.5 — Literal rotation axes and centred controls

- Corrected the live cube so RX, RY and RZ rotate around the displayed X, Y and Z axes respectively.
- Corrected the controller knob so RZ drives its visible twist while RX and RY drive their matching tilts.
- Centred the knob and six base-key controls inside the controller silhouette.
- Moved corrected TZ and RX/RY/RZ signs into the firmware baseline; Tune inversion controls now start clear and represent only user overrides.

## 4.4.0-rc.4 — Runtime axis correction and streamlined acceptance

- Added an EEPROM-backed final output map with corrected TZ/RZ defaults, live translation/rotation group swapping and independent inversion of all six axes.
- Removed raw telemetry frames from the readable live log while preserving structured 25 Hz visualization updates.
- Simplified motion acceptance by removing the redundant raw-input stage and auto-starting key, wheel, precision-button and final 6DOF checks.
- Corrected cube and controller-preview axis semantics, including horizontal/vertical knob movement, push/pull scaling and a fully contained wheel.
- Reflowed Tune into aligned response, centre, key and axis-mapping controls with readable typography and a compact 3 × 2 key grid.
- Removed the redundant header Tune and Need help actions while retaining the welcome and Ready-page fine-tuning routes.

## 4.4.0-rc.3 — ErgonoMouse source-axis correction

- Corrected the ErgonoMouse analog input order so each joystick's up/down channel feeds AX/BX/CX/DX and its left/right channel feeds AY/BY/CY/DY before kinematics are calculated.
- Added a Windows-only release-candidate workflow for faster hardware iteration while retaining the full native workflow for approved releases.

## 4.4.0-rc.2 — Continuous motion feedback and layout refinement

- Kept structured 6DOF, key and wheel telemetry active during every diagnostic check and reduced the end-to-end update interval for immediate visual feedback.
- Separated cube translation from rotation, corrected the displayed axis mapping and replaced transparent faces with a solid orientation model.
- Rebuilt the controller preview around three upper keys, three lower keys, two left-side keys and a split, non-rotating wheel indicator, while hiding controls absent from the configured build.
- Balanced the Test Motion card into equal visualization and instruction columns and compacted Tune controls, key assignments and centre reset.
- Saved validated key assignments with the main “Save and finish” action instead of requiring a separate save button.

## 4.4.0-rc.1 — Live visualization and runtime controls

- Replaced raw six-axis numbers with a live 3D cube plus configuration-aware key and wheel feedback, while retaining numeric telemetry under technical details.
- Added safe runtime response-curve selection and nine-position precision/edge controls backed by the existing EEPROM parameter system.
- Added a one-click resting-position reset to the Tune page.
- Added persistent physical-to-logical key reassignment with a versioned, validated EEPROM record, so swapped wiring can be corrected without reopening or reflashing the controller.

## 4.3.1 — Native macOS bundle repair

- Replaced the hand-built macOS application folder with PyInstaller's native `BUNDLE` target so embedded binaries and the final app receive valid ad-hoc signatures in the correct order.
- Preserved the signed bundle's symbolic-link layout while creating separate Intel and Apple Silicon DMGs.
- Strengthened the macOS smoke test to verify the bundle signature and architecture, copy the app from the mounted DMG, capture startup diagnostics and validate the live packaged status endpoint.

## 4.3.0 — Guided tuning and acceptance polish

- Softened the local setup palette, added build photography, replaced improvised connection drawings with Lucide mouse and monitor icons, and added project credits.
- Simplified model, preference, installation, live-data and completion screens based on physical acceptance feedback.
- Remapped displayed Keys 1–6 to D10/D16/D14/D1/D0/D15 and extended full-travel capture to 30 seconds.
- Moved tuning into its own guided step with named sliders that safely update and save controller parameters.
- Established a consistent minimum desktop height and footer alignment, aligned the progress rail, enlarged configuration icons, and added a persistent shortcut back to live fine-tuning after setup.
- Let the desktop wizard grow beyond a consistent minimum height, filtered incompatible symmetric-base choices, auto-connected motion testing, exposed Tune whenever a configured controller is connected, and expanded each tuning slider to nine positions.

## 4.2.0 — Published-wiring compatibility

- Aligned all generated firmware with the published ErgonoMouse wiring: six base keys on D16/D14/D10/D0/D15/D1, controller buttons on D5/D7 and encoder on D2/D3.
- Corrected lighting from an addressable-ring assumption to the published always-on 5 V strip, freeing the signal pin required by a fully equipped build.
- Fixed simultaneous SpaceMouse button reports so multiple pressed buttons no longer overwrite one another.
- Added duplicate-pin and correct kill-button-index compile-time validation.
- Added automatic per-button detection, wheel verification and plain-language precision-button checks to onboarding.
- Reduced the distributable matrix to 84 unique firmware behaviors by removing purely physical lighting state from compiled firmware.

## 4.1.0 — Native unsigned packages

- Added a per-user Windows installer with Start-menu integration and optional desktop shortcut.
- Added a directly executable Linux AppImage and verified its embedded flasher and 144-variant firmware matrix.
- Added native macOS DMGs for Intel and Apple Silicon with an Applications shortcut.
- Added native install-and-launch smoke tests on clean Windows, Linux and macOS hosted runners.
- Added SHA-256 verification for every native artifact and plain-language unsigned-launch instructions.
- Documented the remaining 3DxWare dependency on Windows/macOS and the open `spacenavd` path on Linux.

## 4.0.0 — First-run setup walkthrough

- Replaced the scrolling configuration dashboard with six focused setup screens and a clear progress rail.
- Added automatic USB discovery, connection gating, retry guidance and plain-language recovery paths.
- Reframed physical configuration as visual questions about the printed model while keeping electrical validation automatic.
- Moved firmware and pin details behind optional disclosures and generated configuration silently during the walkthrough.
- Reduced validation to one motion task at a time with explicit progress and a reassuring completion summary.
- Added keyboard focus, reduced-motion support, responsive touch targets and a persistent mobile action bar.
- Prevented normal launches from bypassing onboarding through internal inspection deep links.

## 3.0.0 — Portable installer and device validation

- Added portable Windows, macOS and Linux packaging with no Python or PlatformIO prerequisite.
- Added a deterministic 144-variant firmware matrix with SHA-256 verification.
- Added one-click Caterina bootloader reset and direct avrdude installation.
- Added human recovery guidance for USB cables, bootloader timing, permissions and changed ports.
- Added cross-platform serial-device discovery and an integrated live validation/tuning flow.
- Added reproducible release tooling, checksums and a three-platform GitHub Actions workflow.
- Fixed the source launcher to consistently use its repository-local Python environment.

## 2.0.0 — Physical-build configurator

- Replaced the fixed V1 profile with the MakerWorld Free/Complete variant model.
- Added base, knob/joystick, handedness, wheel/button and controller-button behavior choices.
- Added deterministic pin allocation and live ten-pin budget feedback.
- Blocked electrically impossible feature combinations before configuration generation.
- Added migration from V1 saved settings and expanded the automated matrix tests.
- Reduced the default Free/Simple firmware from 98.5% to 87.7% flash use.

## 1.0.0 — Guided setup baseline

- Added a local responsive setup application.
- Added a fixed ErgonoMouse MK XX configuration preset.
- Added environment checks, configuration generation, build and flash actions.
- Added command-line equivalents and a pinned PlatformIO bootstrap.
- Verified the generated firmware on Arduino Micro/ATmega32U4.
