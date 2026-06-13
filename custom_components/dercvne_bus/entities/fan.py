"""Fan platform entity for Dercvne Bus thermostat fresh air.

X1-29-S Thermostat Panel fresh air (新风) sub-function is a simple
3-speed fan: low / medium / high.
"""

import logging

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN, DEVICE_TYPE_THERMOSTAT
from ..config_flow import _migrate_data

_LOGGER = logging.getLogger(__name__)

# Preset modes for fresh air fan (3 speeds)
PRESET_MODES = ["低风", "中风", "高风"]
_FAN_SPEED_MAP = {"低风": "low", "中风": "medium", "高风": "high"}
_REVERSE_FAN_MAP = {"low": "低风", "medium": "中风", "high": "高风"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up thermostat fresh air fan entities."""
    _, devices = _migrate_data(dict(entry.data))

    entities = []
    for device_config in devices:
        if device_config.get("device_type") != DEVICE_TYPE_THERMOSTAT:
            continue

        fa_cfg = device_config.get("fresh_air", {})
        if not fa_cfg.get("enabled"):
            continue

        conn_id = device_config.get("connection_id", "")
        connections_data = hass.data[DOMAIN][entry.entry_id]["connections"]
        conn = connections_data.get(conn_id)
        if conn is None:
            _LOGGER.warning("Thermostat FA: conn %s not found", conn_id)
            continue

        device_id = device_config.get("id", "")
        th_data = hass.data[DOMAIN][entry.entry_id].get("thermostats", {})
        thermostat = th_data.get(device_id)
        if thermostat is None:
            _LOGGER.warning("Thermostat FA: thermostat device %s not found", device_id)
            continue

        entity = ThermostatFAFan(
            thermostat, entry.entry_id, device_id, device_config, conn_id,
        )
        entities.append(entity)

    async_add_entities(entities)


class ThermostatFAFan(FanEntity):
    """Representation of thermostat panel fresh air as a fan entity.

    Supports: Off, Low, Medium, High speeds (preset_mode).
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_preset_modes = PRESET_MODES

    def __init__(self, thermostat, entry_id, device_id, device_config, conn_id):
        """Initialize thermostat fresh air fan entity."""
        self._thermostat = thermostat
        self._entry_id = entry_id
        self._device_uuid = device_id
        self._conn_id = conn_id
        self._panel_name = device_config.get("name", "温控面板")

        self._attr_name = f"{self._panel_name} 新风"
        self._attr_unique_id = f"{entry_id}_{device_id}_fa"
        self._attr_is_on = False
        self._attr_preset_mode = None
        # Register this entity so the device can push state updates
        self._thermostat.register_entity("fresh_air", self)

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, f"{self._entry_id}_{self._device_uuid}"),
            },
            "name": self._panel_name,
            "manufacturer": "Dercvne",
            "model": "X1-29-S Thermostat Panel",
        }

    # ------------------------------------------------------------------ update
    # ------------------------------------------------------------------

    def update_status(self, parsed: dict) -> None:
        """Update state from parsed Sicoo response."""
        if not parsed:
            return

        power = parsed.get("power", False)
        if power:
            fan_speed = parsed.get("fan_speed", "low")
            self._attr_preset_mode = _REVERSE_FAN_MAP.get(fan_speed, "低风")
            self._attr_is_on = True
        else:
            self._attr_preset_mode = None
            self._attr_is_on = False

        self.async_write_ha_state()

    # ------------------------------------------------------------------ control
    # ------------------------------------------------------------------

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs) -> None:
        """Turn on fresh air fan."""
        mode = preset_mode or "低风"
        await self._thermostat.set_power("fresh_air", True)
        await self.async_set_preset_mode(mode)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off fresh air fan."""
        await self._thermostat.set_power("fresh_air", False)
        self._attr_is_on = False
        self._attr_preset_mode = None
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set fan speed by preset mode (低风/中风/高风)."""
        if preset_mode not in PRESET_MODES:
            _LOGGER.warning("Invalid preset_mode: %s", preset_mode)
            return

        speed = _FAN_SPEED_MAP.get(preset_mode, "low")
        await self._thermostat.set_fan_speed("fresh_air", speed)
        self._attr_preset_mode = preset_mode
        self._attr_is_on = True
        self.async_write_ha_state()
