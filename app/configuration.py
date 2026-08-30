from __future__ import annotations

import json
import os
import tempfile
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .paths import DATA_ROOT, SOURCE_ROOT

PROJECT_ROOT = SOURCE_ROOT
CONFIG_PATH = (
    DATA_ROOT / "spacemouse-keys" / "config.h"
    if DATA_ROOT != SOURCE_ROOT
    else SOURCE_ROOT / "spacemouse-keys" / "config.h"
)
STATE_PATH = DATA_ROOT / "settings.json" if DATA_ROOT != SOURCE_ROOT else SOURCE_ROOT / ".ergonomouse" / "settings.json"
SETUP_STATE_PATH = STATE_PATH.with_name("setup-state.json")

DIGITAL_PIN_POOL = (0, 1, 2, 3, 5, 7, 10, 14, 15, 16)
PUBLISHED_BASE_BUTTON_PINS = (10, 16, 14, 1, 0, 15)
PUBLISHED_CONTROLLER_BUTTON_PINS = (5, 7)
PUBLISHED_ENCODER_PINS = (2, 3)
BASE_BUTTONS = ("SM_FIT", "SM_T", "SM_R", "SM_F", "SM_1", "SM_2")
CONTROLLER_HID_BUTTONS = ("SM_3", "SM_4")


@dataclass(frozen=True)
class ErgonoMouseSettings:
    """A physical ErgonoMouse build translated into firmware choices."""

    edition: str = "free"
    controller_style: str = "knob"
    handedness: str = "symmetric"
    base_variant: str = "simple"
    control_variant: str = "simple"
    controller_buttons_mode: str = "kill"
    wheel_axis: int = 2
    led_ring_enabled: bool = True
    led_count: int = 24
    progmode_enabled: bool = True
    exclusive_mode: bool = True
    priority_z: bool = True

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ErgonoMouseSettings":
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"Unknown setting(s): {', '.join(unknown)}")
        settings = cls(**value)
        settings.validate()
        return settings

    @property
    def has_wheel(self) -> bool:
        return self.control_variant in {"wheel", "full"}

    @property
    def has_controller_buttons(self) -> bool:
        return self.control_variant in {"buttons", "full"}

    @property
    def base_button_count(self) -> int:
        return 6 if self.base_variant == "six_keys" else 0

    @property
    def controller_button_count(self) -> int:
        return 2 if self.has_controller_buttons else 0

    @property
    def total_switch_count(self) -> int:
        return self.base_button_count + self.controller_button_count

    def validate(self) -> None:
        _choice("edition", self.edition, {"free", "complete"})
        _choice("controller_style", self.controller_style, {"knob", "joystick"})
        _choice("handedness", self.handedness, {"symmetric", "left", "right"})
        _choice("base_variant", self.base_variant, {"simple", "six_keys"})
        _choice("control_variant", self.control_variant, {"simple", "wheel", "buttons", "full"})
        _choice("controller_buttons_mode", self.controller_buttons_mode, {"kill", "hid"})

        if self.edition == "free" and (
            self.base_variant != "simple"
            or self.control_variant != "simple"
            or self.handedness != "symmetric"
        ):
            raise ValueError(
                "The free model contains the symmetric Simple base and Simple controller. "
                "Choose Complete/custom if you printed another variant."
            )
        if self.handedness == "symmetric" and self.base_variant == "six_keys":
            raise ValueError("The symmetric base has no base keys. Choose Left Hand or Right Hand for 6 Base Keys.")
        if isinstance(self.wheel_axis, bool) or not 1 <= self.wheel_axis <= 6:
            raise ValueError("wheel_axis must be an integer from 1 to 6")
        if isinstance(self.led_count, bool) or not 1 <= self.led_count <= 64:
            raise ValueError("led_count must be an integer from 1 to 64")
        pin_plan(self)


def _choice(name: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(sorted(allowed))}")


DEFAULT_SETTINGS = ErgonoMouseSettings()


def migrate_settings(value: dict[str, Any]) -> dict[str, Any]:
    """Translate the V1 fixed-profile state into the V2 physical-build model."""
    if "profile" not in value:
        return value
    wheel_enabled = bool(value.get("wheel_enabled", True))
    return {
        "edition": "complete",
        "controller_style": "knob",
        "handedness": "left",
        "base_variant": "six_keys",
        "control_variant": "full" if wheel_enabled else "buttons",
        "controller_buttons_mode": "kill",
        "wheel_axis": value.get("wheel_axis", 2),
        "led_ring_enabled": value.get("led_ring_enabled", True),
        "led_count": value.get("led_count", 24),
        "progmode_enabled": value.get("progmode_enabled", True),
        "exclusive_mode": value.get("exclusive_mode", True),
        "priority_z": value.get("priority_z", True),
    }


def load_settings() -> ErgonoMouseSettings:
    if not STATE_PATH.exists():
        return DEFAULT_SETTINGS
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return ErgonoMouseSettings.from_mapping(migrate_settings(raw))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return DEFAULT_SETTINGS


def save_settings(settings: ErgonoMouseSettings) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(STATE_PATH, json.dumps(asdict(settings), indent=2) + "\n")


def load_setup_state() -> dict[str, bool]:
    """Return durable setup progress without coupling it to firmware choices."""
    try:
        raw = json.loads(SETUP_STATE_PATH.read_text(encoding="utf-8"))
        return {"completed": raw.get("completed") is True}
    except (OSError, TypeError, json.JSONDecodeError):
        return {"completed": False}


def mark_setup_complete() -> dict[str, bool]:
    state = {"completed": True}
    _atomic_write(SETUP_STATE_PATH, json.dumps(state, indent=2) + "\n")
    return state


def write_config(settings: ErgonoMouseSettings) -> Path:
    settings.validate()
    save_settings(settings)
    _atomic_write(CONFIG_PATH, render_config(settings))
    return CONFIG_PATH


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def pin_plan(settings: ErgonoMouseSettings) -> dict[str, Any]:
    reserved: dict[int, str] = {}
    if settings.has_wheel:
        reserved.update(
            {
                PUBLISHED_ENCODER_PINS[0]: "encoder CLK",
                PUBLISHED_ENCODER_PINS[1]: "encoder DT",
            }
        )

    base_pins = list(PUBLISHED_BASE_BUTTON_PINS) if settings.base_button_count else []
    controller_pins = (
        list(PUBLISHED_CONTROLLER_BUTTON_PINS) if settings.controller_button_count else []
    )
    assigned = base_pins + controller_pins
    used = set(reserved) | set(assigned)
    available = [pin for pin in DIGITAL_PIN_POOL if pin not in used]
    return {
        "total_pins": len(DIGITAL_PIN_POOL),
        "reserved": reserved,
        "available_switch_pins": available,
        "assigned_switch_pins": assigned,
        "assignments": {
            "base_buttons": base_pins,
            "controller_buttons": controller_pins,
            "encoder": list(PUBLISHED_ENCODER_PINS) if settings.has_wheel else [],
            "lighting": "5V and GND (no data pin)" if settings.led_ring_enabled else "disabled",
        },
        "switches": settings.total_switch_count,
        "free_after_configuration": len(available),
    }


def describe_settings(settings: ErgonoMouseSettings) -> dict[str, Any]:
    settings.validate()
    return {
        "edition": settings.edition,
        "physical_build": {
            "controller": settings.controller_style,
            "handedness": settings.handedness,
            "base": settings.base_variant,
            "controls": settings.control_variant,
        },
        "features": {
            "wheel": settings.has_wheel,
            "controller_buttons": settings.controller_button_count,
            "base_buttons": settings.base_button_count,
            "button_behavior": settings.controller_buttons_mode,
            "lighting": settings.led_ring_enabled,
        },
        "pin_plan": pin_plan(settings),
    }


def model_catalog() -> dict[str, Any]:
    return {
        "source": "MakerWorld model 1062479",
        "editions": {
            "free": {
                "label": "Free · Simple",
                "description": "Symmetric Simple base with Simple knob or joystick",
            },
            "complete": {
                "label": "Complete / custom",
                "description": "Six-key, wheel, button and handed variants",
            },
        },
        "controller_styles": ["knob", "joystick"],
        "handedness": ["symmetric", "left", "right"],
        "base_variants": ["simple", "six_keys"],
        "control_variants": ["simple", "wheel", "buttons", "full"],
        "compatibility": {"symmetric_base_variants": ["simple"]},
    }


def firmware_payload(settings: ErgonoMouseSettings) -> dict[str, Any]:
    """Return only choices that change compiled firmware bytes."""
    settings.validate()
    return {
        "base_variant": settings.base_variant,
        "control_variant": settings.control_variant,
        "controller_buttons_mode": settings.controller_buttons_mode if settings.has_controller_buttons else "none",
        "wheel_axis": settings.wheel_axis if settings.has_wheel else 0,
        "progmode_enabled": settings.progmode_enabled,
        "exclusive_mode": settings.exclusive_mode,
        "priority_z": settings.priority_z,
    }


def firmware_key(settings: ErgonoMouseSettings) -> str:
    encoded = json.dumps(firmware_payload(settings), sort_keys=True, separators=(",", ":")).encode()
    return "fw-" + hashlib.sha256(encoded).hexdigest()[:16]


def render_config(settings: ErgonoMouseSettings) -> str:
    settings.validate()
    plan = pin_plan(settings)
    switch_pins = plan["assigned_switch_pins"]
    base_buttons = list(BASE_BUTTONS[: settings.base_button_count])
    controller_hid = (
        list(CONTROLLER_HID_BUTTONS)
        if settings.has_controller_buttons and settings.controller_buttons_mode == "hid"
        else []
    )
    button_list = base_buttons + controller_hid
    kill_count = 2 if settings.has_controller_buttons and settings.controller_buttons_mode == "kill" else 0
    kill_rot = settings.base_button_count if kill_count else 0
    kill_trans = settings.base_button_count + 1 if kill_count else 0
    progmode = "1" if settings.progmode_enabled else "0"
    exclusive = "1" if settings.exclusive_mode else "0"
    priority_z = "1" if settings.priority_z else "0"
    rotary_axis = settings.wheel_axis if settings.has_wheel else 0
    key_list = _c_array(switch_pins)
    hid_button_list = _c_array(button_list)
    led_block = (
        "// Published ErgonoMouse lighting is wired directly to 5V and GND (always on)."
        if settings.led_ring_enabled
        else "// Lighting disabled by ErgonoMouse Setup."
    )
    encoder_block = (
        f"#define ENCODER_CLK 3\n#define ENCODER_DT 2\n#define ROTARY_AXIS {rotary_axis}"
        if settings.has_wheel
        else "// Encoder disabled by ErgonoMouse Setup\n#define ROTARY_AXIS 0"
    )

    return f"""// Generated by ErgonoMouse Setup. Re-run ./ergonomouse to change it.
// Physical build: {settings.edition}, {settings.handedness}-handed {settings.controller_style},
// {settings.base_variant} base, {settings.control_variant} controller controls.

#ifndef CONFIG_h
#define CONFIG_h

#include "release.h"

#define PARAM_IN_EEPROM 1
#define ENABLE_PROGMODE {progmode}
#define STARTDEBUG 0
#undef HALLEFFECT

// Four KY-023 joystick modules: each up/down axis first, then left/right.
// Common modules label those channels Y/X, so each Arduino analog pair is swapped here.
#define PINLIST {{A1, A0, A3, A2, A7, A6, A9, A8}}
#define INVERTLIST {{0, 0, 0, 0, 0, 0, 0, 0}}

// Starting calibration; fine-tune these values on the physical unit.
#define DEADZONE 15
#define MINVALS {{-400, -400, -400, -400, -400, -400, -400, -400}}
#define MAXVALS {{+175, +175, +175, +175, +175, +175, +175, +175}}

#define SENS_TX 0.80
#define SENS_TY 0.99
#define SENS_PTZ 2.5
#define SENS_NTZ 1.5
#define GATE_NTZ 15
#define GATE_RX 15
#define GATE_RY 15
#define GATE_RZ 15
#define SENS_RX 1.2
#define SENS_RY 1.2
#define SENS_RZ 0.90

#define MODFUNC 3
#define MOD_A 1.15
#define MOD_B 1.15

#define INVX 0
#define INVY 1
#define INVZ 1
#define INVRX 0
#define INVRY 1
#define INVRZ 1
#define SWITCHYZ 0
#define SWITCHXY 0

#define COMP_EN 1
#define COMP_NR 50
#define COMP_WAIT 200
#define COMP_MDIFF 4
#define COMP_CDIFF 50

#define EXCLUSIVE {exclusive}
#define EXCL_HYST 5
#define EXCL_PRIOZ {priority_z}

// Pin assignment calculated from the selected physical options.
// ErgonoMouse key order: Key 1..6 use D10,D16,D14,D1,D0,D15; precision buttons D5,D7;
// encoder D2,D3. Buttons close their assigned pin to GND when pressed.
#define NUMKEYS {settings.total_switch_count}
#define KEYLIST {key_list}
#define NUMHIDKEYS {len(button_list)}

#define SM_MENU 0
#define SM_FIT 1
#define SM_T 2
#define SM_R 4
#define SM_F 5
#define SM_RCW 8
#define SM_1 12
#define SM_2 13
#define SM_3 14
#define SM_4 15
#define SM_ESC 22
#define SM_ALT 23
#define SM_SHFT 24
#define SM_CTRL 25
#define SM_ROT 26

#define BUTTONLIST {hid_button_list}
#define NUMKILLKEYS {kill_count}
#define KILLROT {kill_rot}
#define KILLTRANS {kill_trans}
#define DEBOUNCE_KEYS_MS 200

{encoder_block}
#define RAXIS_ECH 200
#define RAXIS_STR 200
#define ROTARY_KEYS 0
#define ROTARY_KEY_IDX_A 0
#define ROTARY_KEY_IDX_B 0
#define ROTARY_KEY_STRENGTH 19

#define VelocityDeadzoneForLED 15
{led_block}
#define LEDclockOffset 2
#define LEDUPDATERATE_MS 150

#define DEBUGDELAY 100
#define DEBUG_LINE_END "\\r"
#define HIDMAXBUTTONS 32

#endif // CONFIG_h
"""


def _c_array(values: list[Any]) -> str:
    return "{" + ", ".join(str(value) for value in values) + "}"
