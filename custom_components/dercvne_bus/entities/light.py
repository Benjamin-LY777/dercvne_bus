"""Light platform for Dercvne Bus lights and keypad backlight."""

import logging

from homeassistant.components.light import (
    LightEntity,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN, COLOR_TEMP_MIN_K, COLOR_TEMP_MAX_K, DEVICE_TYPE_KEYPAD
from ..device.light import DALILight
from ..device.keypad import DALIKeypad
from ..device import DALIDeviceConfig
from ..config_flow import _migrate_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DALI lights and keypad backlights."""
    _, devices = _migrate_data(dict(entry.data))
    connections_data = hass.data[DOMAIN][entry.entry_id]["connections"]

    entities = []
    for device_config in devices:
        conn_id = device_config.get("connection_id", "")
        conn = connections_data.get(conn_id)
        if conn is None:
            _LOGGER.warning(
                "Device %s references unknown connection_id=%s, skipping",
                device_config.get("name"), conn_id,
            )
            continue

        transport = conn["transport"]
        entity_registry = conn["entity_registry"]
        dtype = device_config.get("device_type", "")

        if dtype in ["light_single", "light_cct"]:
            device_id = device_config.get("id", f"{device_config.get('group','?')}_{device_config.get('address','?')}")
            config = DALIDeviceConfig(
                name=device_config.get("name"),
                device_type=dtype,
                group=device_config.get("group"),
                address=device_config.get("address"),
            )
            light = DALILight(config, transport)
            entity = DALILightEntity(light, entry.entry_id, device_id,
                                     entity_registry, conn_id)
            entities.append(entity)

        elif dtype == DEVICE_TYPE_KEYPAD:
            keypad = DALIKeypad(device_config, transport)
            device_id = device_config.get("id", device_config.get("panel_address", "??"))

            # Backlight — only if configured
            if keypad.backlight_group and keypad.backlight_address:
                bl_config = DALIDeviceConfig(
                    name=f"{keypad.name} 背光",
                    device_type="light_single",
                    group=keypad.backlight_group,
                    address=keypad.backlight_address,
                )
                bl_device = DALILight(bl_config, transport)
                entity = DALIKeypadBacklight(keypad, bl_device, entry.entry_id,
                                             device_id, entity_registry, conn_id)
                entities.append(entity)
                _LOGGER.debug("Keypad %s backlight entity created (G=%s A=%s)",
                              keypad.name, keypad.backlight_group, keypad.backlight_address)

    async_add_entities(entities)


class DALILightEntity(LightEntity):
    """Representation of a DALI light."""

    _attr_should_poll = False

    def __init__(self, light: DALILight, entry_id: str, device_id: str,
                 entity_registry: dict, conn_id: str):
        self._light = light
        self._entry_id = entry_id
        self._entity_registry = entity_registry
        self._conn_id = conn_id
        self._attr_name = light.name
        self._attr_unique_id = f"{entry_id}_{device_id}"

        if light.supports_color_temp:
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_min_color_temp_kelvin = COLOR_TEMP_MIN_K
            self._attr_max_color_temp_kelvin = COLOR_TEMP_MAX_K
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._entry_id}_{self._conn_id}")},
            "name": f"D-Bus Module ({self._conn_id[:6]})",
            "manufacturer": "Dercvne",
            "model": "D-Bus Module",
        }

    @property
    def is_on(self) -> bool:
        return self._light.is_on

    @property
    def brightness(self) -> int:
        return self._light.brightness

    @property
    def color_temp_kelvin(self) -> int:
        return self._light.color_temp_kelvin

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        key = (self._light.group, self._light.address)
        self._entity_registry[key] = self
        _LOGGER.debug("Light registered: G=%s A=%s conn=%s",
                      self._light.group, self._light.address, self._conn_id)

    async def async_will_remove_from_hass(self) -> None:
        key = (self._light.group, self._light.address)
        self._entity_registry.pop(key, None)

    def handle_feedback(self, status: bool, brightness: int = None, color_temp_kelvin: int = None) -> None:
        if brightness is not None:
            self._light._brightness = brightness
            self._light._is_on = brightness > 0
        else:
            self._light._is_on = status

        if color_temp_kelvin is not None:
            self._light._color_temp_k = color_temp_kelvin

        self.schedule_update_ha_state()
        _LOGGER.debug(
            "Light %s feedback: on=%s bright=%s ct=%s K",
            self._light.name,
            self._light.is_on,
            brightness,
            color_temp_kelvin,
        )

    async def async_turn_on(self, **kwargs) -> None:
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        await self._light.turn_on(brightness=brightness, color_temp_kelvin=color_temp_kelvin)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self._light.turn_off()
        self.async_write_ha_state()


class DALIKeypadBacklight(LightEntity):
    """Keypad backlight entity — brightness-only light.

    Registered under the keypad panel device rather than the DALI module.
    """

    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, keypad: DALIKeypad, light: DALILight,
                 entry_id: str, device_id: str,
                 entity_registry: dict, conn_id: str):
        self._keypad = keypad
        self._light = light
        self._entry_id = entry_id
        self._device_uuid = device_id  # stable UUID, unchanged by address edits
        self._entity_registry = entity_registry
        self._conn_id = conn_id
        self._attr_name = f"{keypad.name} 背光"
        self._attr_unique_id = f"{entry_id}_{device_id}_backlight"

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, f"{self._entry_id}_{self._device_uuid}"),
                (DOMAIN, f"{self._entry_id}_{self._conn_id}_{self._keypad.panel_address}"),
            },
            "name": f"D-Bus Keypad Panel ({self._keypad.panel_address})",
            "manufacturer": "Dercvne",
            "model": "485 Keypad Panel",
        }

    @property
    def is_on(self) -> bool:
        return self._light.is_on

    @property
    def brightness(self) -> int:
        return self._light.brightness

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        key = (self._light.group, self._light.address)
        self._entity_registry[key] = self
        _LOGGER.debug("Keypad backlight registered: G=%s A=%s conn=%s",
                      self._light.group, self._light.address, self._conn_id)

    async def async_will_remove_from_hass(self) -> None:
        key = (self._light.group, self._light.address)
        self._entity_registry.pop(key, None)

    def handle_feedback(self, status: bool, brightness: int = None, color_temp_kelvin: int = None) -> None:
        if brightness is not None:
            self._light._brightness = brightness
            self._light._is_on = brightness > 0
        else:
            self._light._is_on = status
        self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        await self._light.turn_on(brightness=brightness)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self._light.turn_off()
        self.async_write_ha_state()
