"""Device triggers for Dercvne Bus keypad, IO module, and VRV indoor units.

Each keypad panel exposes **16 pure-event triggers** (8 buttons x short/long).
Each IO module exposes **8 pure-event triggers** (4 channels x short/long).
Each VRV indoor unit exposes **6 state-change triggers** (on/off + 4 modes).

Subtype strings are Chinese labels directly (e.g. "按键1-短按"), so no
translation file lookups are needed. The labels themselves serve as both
the subtype identifier and the display text.
"""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, KEYPAD_BUTTON_COUNT, IO_MODULE_CHANNEL_COUNT

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event names fired by __init__._feedback_listener on each keypad / IO press
# ---------------------------------------------------------------------------
EVENT_KEYPAD_PRESSED = f"{DOMAIN}_keypad_pressed"
EVENT_IO_MODULE_PRESSED = f"{DOMAIN}_io_module_pressed"
EVENT_VRV_STATE_CHANGED = f"{DOMAIN}_vrv_state_changed"

# Single trigger type -- everything is distinguished by subtype
TRIGGER_TYPE_KEYPAD = "keypad_button_pressed"
TRIGGER_TYPE_IO_MODULE = "io_module_triggered"
TRIGGER_TYPE_VRV = "vrv_state_changed"

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In([TRIGGER_TYPE_KEYPAD, TRIGGER_TYPE_IO_MODULE, TRIGGER_TYPE_VRV]),
        vol.Required("subtype"): str,
    }
)

# ---------------------------------------------------------------------------
# Keypad subtype strings as Chinese labels
# ---------------------------------------------------------------------------
_ACTIONS = [("短按", "short"), ("长按", "long")]

_KEYPAD_SUBTYPE_MAP: dict[str, tuple[int, str]] = {}
_KEYPAD_SUBTYPE_LIST: list[str] = []

for _btn in range(1, KEYPAD_BUTTON_COUNT + 1):
    for _cn, _en in _ACTIONS:
        _subtype = f"按键{_btn}-{_cn}"
        _KEYPAD_SUBTYPE_LIST.append(_subtype)
        _KEYPAD_SUBTYPE_MAP[_subtype] = (_btn, _en)

# ---------------------------------------------------------------------------
# IO Module subtype strings as Chinese labels
# ---------------------------------------------------------------------------
_IO_ACTIONS = [("短触", "short"), ("长触", "long")]

_IO_SUBTYPE_MAP: dict[str, tuple[int, str]] = {}
_IO_SUBTYPE_LIST: list[str] = []

for _ch in range(1, IO_MODULE_CHANNEL_COUNT + 1):
    for _cn, _en in _IO_ACTIONS:
        _subtype = f"输入{_ch}-{_cn}"
        _IO_SUBTYPE_LIST.append(_subtype)
        _IO_SUBTYPE_MAP[_subtype] = (_ch, _en)

# ---------------------------------------------------------------------------
# VRV Indoor Unit subtype strings as Chinese labels
# ---------------------------------------------------------------------------
_VRV_SUBTYPE_LIST = [
    "内机开机",
    "内机关闭",
    "切换制冷",
    "切换制热",
    "切换除湿",
    "切换送风",
]
_VRV_SUBTYPE_MAP = {
    "内机开机": "unit_on",
    "内机关闭": "unit_off",
    "切换制冷": "mode_cool",
    "切换制热": "mode_heat",
    "切换除湿": "mode_dry",
    "切换送风": "mode_fan",
}


def _parse_subtype(subtype: str) -> tuple[int, str] | None:
    """Parse subtype like '按键1-短按' -> (1, 'short'), or None on failure."""
    # Try keypad subtypes first
    result = _KEYPAD_SUBTYPE_MAP.get(subtype)
    if result is not None:
        return result
    # Try IO module subtypes
    result = _IO_SUBTYPE_MAP.get(subtype)
    if result is not None:
        return result
    return None


def _parse_vrv_subtype(subtype: str) -> str | None:
    """Parse VRV subtype label -> event key, or None."""
    return _VRV_SUBTYPE_MAP.get(subtype)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """Return all keypad / IO module triggers for a Dercvne Bus device."""
    registry = dr.async_get(hass)
    device = registry.async_get(device_id)
    if device is None:
        return []

    # Only return triggers for our keypad / IO module devices
    if not any(ident[0] == DOMAIN for ident in device.identifiers):
        return []

    model = device.model or ""

    # Keypad: 16 button triggers
    if model == "485 Keypad Panel":
        return [
            {
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: TRIGGER_TYPE_KEYPAD,
                "subtype": subtype,
            }
            for subtype in _KEYPAD_SUBTYPE_LIST
        ]

    # IO Module: 8 channel triggers (4 channels x short/long)
    if model == "4路 IO模块":
        return [
            {
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: TRIGGER_TYPE_IO_MODULE,
                "subtype": subtype,
            }
            for subtype in _IO_SUBTYPE_LIST
        ]

    # VRV Indoor Unit: 6 state-change triggers
    if model == "CoolMaster VRV Controller":
        # Check if it's an indoor unit device (has sw_version in identifiers)
        # The indoor unit device uses the same model name as the controller
        # We use a different identifier to distinguish: controller uses vrv_id, unit uses vrv_id_unit_id
        for ident in device.identifiers:
            if len(ident) == 2 and "_" in ident[1]:
                return [
                    {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: TRIGGER_TYPE_VRV,
                        "subtype": subtype,
                    }
                    for subtype in _VRV_SUBTYPE_LIST
                ]

    return []


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: callable,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Listen for keypad / IO module / VRV events.

    Keypad subtypes: e.g. "按键1-短按" or "按键8-长按"
    IO module subtypes: e.g. "输入1-短触" or "输入4-长触"
    VRV subtypes: e.g. "内机开机" or "切换制冷"
    """
    trigger_subtype: str = config["subtype"]
    trigger_type: str = config[CONF_TYPE]
    trigger_device_id = config[CONF_DEVICE_ID]

    # ── VRV triggers ──
    if trigger_type == TRIGGER_TYPE_VRV:
        vrv_key = _parse_vrv_subtype(trigger_subtype)
        if vrv_key is None:
            _LOGGER.warning("Unrecognized VRV trigger subtype: %s", trigger_subtype)
            return lambda: None

        @callback
        def _on_vrv_event(event):
            event_data = event.data
            if event_data.get("device_id") != trigger_device_id:
                return
            if event_data.get("change") != vrv_key:
                return
            hass.async_create_task(
                action({
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: trigger_device_id,
                        CONF_TYPE: trigger_type,
                        "subtype": trigger_subtype,
                        "description": trigger_subtype,
                    }
                })
            )

        return hass.bus.async_listen(EVENT_VRV_STATE_CHANGED, _on_vrv_event)

    # ── Keypad / IO Module triggers ──
    parsed = _parse_subtype(trigger_subtype)
    if parsed is None:
        _LOGGER.warning("Unrecognized trigger subtype: %s", trigger_subtype)
        return lambda: None

    trigger_index, trigger_action = parsed

    # IO Module uses "channel" field, keypad uses "button" field
    is_io = trigger_type == TRIGGER_TYPE_IO_MODULE
    index_field = "channel" if is_io else "button"
    event_name = EVENT_IO_MODULE_PRESSED if is_io else EVENT_KEYPAD_PRESSED

    @callback
    def _on_event(event):
        event_data = event.data
        if event_data.get("device_id") != trigger_device_id:
            return
        if event_data.get(index_field) != trigger_index:
            return
        if event_data.get("action") != trigger_action:
            return

        hass.async_create_task(
            action(
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: trigger_device_id,
                        CONF_TYPE: trigger_type,
                        "subtype": trigger_subtype,
                        "description": trigger_subtype,
                    }
                }
            )
        )

    return hass.bus.async_listen(event_name, _on_event)


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, Any]:
    """No extra configuration fields needed for button-press triggers."""
    return {"extra_fields": vol.Schema({})}
