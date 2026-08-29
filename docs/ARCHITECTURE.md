# ErgonoMouse SW architecture

## Product boundary

ErgonoMouse SW is a thin product layer around the upstream AVR firmware. The firmware core remains readable and mergeable with upstream; onboarding-specific behavior lives outside `spacemouse-keys/` wherever possible.

## Layout

- `spacemouse-keys/` — upstream Arduino firmware.
- `app/configuration.py` — validated ErgonoMouse profiles and `config.h` generation.
- `app/tooling.py` — environment detection and bounded PlatformIO commands.
- `app/installer.py` — manifest verification, bootloader reset and direct flashing.
- `app/serial_service.py` — locked live-device session and bounded calibration commands.
- `app/paths.py` — source/portable resource and per-user state locations.
- `app/server.py` — localhost-only standard-library HTTP server and JSON API.
- `app/static/` — responsive setup interface with no CDN or runtime package dependency.
- `firmware/manifest.json` — generated mapping from compiled behavior to verified firmware images.
- `tools/` — reproducible firmware-matrix, flasher-staging and packaging commands.
- `packaging/` — PyInstaller entry point/specification.
- `tests/` — configuration, installer and HTTP smoke tests.
- `docs/UPSTREAM.md` — original comprehensive upstream documentation.

## Design choices

### Local first

The server binds to `127.0.0.1` by default. It has no analytics, account system, cookies or external API calls. In source mode, hardware settings remain in `.ergonomouse/settings.json`, and generated firmware configuration remains in `spacemouse-keys/config.h`; both are ignored by Git. Portable editions store state in the operating system’s per-user configuration directory. Bundled resources are read-only.

### Reversible configuration

The application generates configuration atomically. A partially written file cannot replace a valid configuration. Input is allow-listed through a typed settings model and rejected if unknown fields are submitted.

### Upstream-friendly firmware

The product layer does not rewrite the firmware’s kinematics, HID or calibration implementation. This keeps future upstream updates reviewable and makes it clear which changes belong to ErgonoMouse UX.

### Two deployment lanes

Source mode keeps PlatformIO and Python in a repository-local virtual environment. Portable mode bundles the Python runtime, static interface, an avrdude binary and precompiled firmware. A SHA-256 manifest is checked again at install time, so damaged or mismatched firmware is rejected before the bootloader is touched.

### Finite firmware matrix

Purely physical labels such as left/right, knob/joystick and directly powered lighting do not change firmware bytes. Compiled behavior is reduced to a canonical payload and content-derived key. The release builder enumerates all 84 valid combinations of keys, controller-button behavior, wheel axis and axis-separation behavior. Every variant uses the published ErgonoMouse pin profile.

## API

- `GET /api/status` — Python, PlatformIO, config and serial-device readiness.
- `GET /api/settings` — current settings plus generated preview.
- `GET /api/model` — physical variant catalog.
- `GET /api/serial/status` — serial capability and active session state.
- `GET /api/serial/output` — incremental live-device output.
- `POST /api/configure` — validate, persist and generate `config.h`.
- `POST /api/build` — compile the `micro` PlatformIO environment.
- `POST /api/flash` — compile and upload to a connected board.
- `POST /api/install` — resolve, verify and install bundled firmware.
- `POST /api/serial/open|close|command|input` — own the selected port, run allow-listed validation modes and answer numeric firmware prompts.

The API binds to loopback by default and accepts a bounded JSON body. Serial commands are allow-listed and one session owns the port, preventing simultaneous flashing and calibration.
