"""Light platform for Dercvne Bus lights and keypad backlight."""

import logging

from homeassistant.components.light import (
    LightEntity,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ColorMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN, COLOR_TEMP_MIN_K, COLOR_TEMP_MAX_K, DEVICE_TYPE_KEYPAD
from ..const import DEVICE_TYPE_LIGHT_RGBCW, DEVICE_TYPE_DM2_SINGLE, DEVICE_TYPE_DM2_CCT
from ..device.light import DALILight
from ..device.light_rgbcw import DALIRGBCWLight
from ..device.light_dm2 import DALIDM2CCTLight, DALIDM2SingleLight
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

        elif dtype == DEVICE_TYPE_DM2_SINGLE:
            # DM2 single CT: same protocol as DALI single (Class=0 only)
            device_id = device_config.get("id", f"{device_config.get('group','?')}_{device_config.get('address','?')}")
            config = DALIDeviceConfig(
                name=device_config.get("name"),
                device_type=dtype,
                group=device_config.get("group"),
                address=device_config.get("address"),
            )
            light = DALIDM2SingleLight(config, transport)
            entity = DALILightEntity(light, entry.entry_id, device_id,
                                     entity_registry, conn_id, is_dm2=True)
            entities.append(entity)

        elif dtype == DEVICE_TYPE_DM2_CCT:
            # DM2 dual CT: uses Class=1 for color temp (standard DM2 protocol)
            device_id = device_config.get("id", f"{device_config.get('group','?')}_{device_config.get('address','?')}")
            config = DALIDeviceConfig(
                name=device_config.get("name"),
                device_type=dtype,
                group=device_config.get("group"),
                address=device_config.get("address"),
            )
            light = DALIDM2CCTLight(config, transport)
            entity = DALIDM2CCTLightEntity(light, entry.entry_id, device_id,
                                            entity_registry, conn_id)
            entities.append(entity)

        elif dtype == DEVICE_TYPE_LIGHT_RGBCW:
            device_id = device_config.get("id", f"{device_config.get('group','?')}_{device_config.get('address','?')}")
            config = DALIDeviceConfig(
                name=device_config.get("name"),
                device_type=dtype,
                group=device_config.get("group"),
                address=device_config.get("address"),
            )
            light = DALIRGBCWLight(config, transport)
            entity = DALIRGBCWLightEntity(light, entry.entry_id, device_id,
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
    """Representation of a DALI light.

    Args:
        is_dm2: If True, this entity uses DM2 standard Class parameter protocol.
                Feedback for class_=1 will be treated as color temp (not brightness).
    """

    _attr_should_poll = False
    # Flag for feedback listener: this entity uses DM2 protocol
    uses_dm2_protocol = False

    def __init__(self, light: DALILight, entry_id: str, device_id: str,
                 entity_registry: dict, conn_id: str, is_dm2: bool = False):
        self._light = light
        self._entry_id = entry_id
        self._entity_registry = entity_registry
        self._conn_id = conn_id
        self.uses_dm2_protocol = is_dm2
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


class DALIRGBCWLightEntity(LightEntity):
    """Representation of a DALI RGBCW light (DM2 dimming host)."""

    _attr_should_poll = False
    uses_dm2_protocol = True  # Flag for feedback listener (Class=1 = CT)

    def __init__(self, light: DALIRGBCWLight, entry_id: str, device_id: str,
                 entity_registry: dict, conn_id: str):
        self._light = light
        self._entry_id = entry_id
        self._entity_registry = entity_registry
        self._conn_id = conn_id
        self._attr_name = light.name
        self._attr_unique_id = f"{entry_id}_{device_id}"
        # Supports both COLOR_TEMP and HS color modes
        self._attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
        # Default to COLOR_TEMP mode
        self._attr_color_mode = ColorMode.COLOR_TEMP
        self._attr_min_color_temp_kelvin = COLOR_TEMP_MIN_K
        self._attr_max_color_temp_kelvin = COLOR_TEMP_MAX_K

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._entry_id}_{self._conn_id}")},
            "name": f"D-Bus Module ({self._conn_id[:6]})",
            "manufacturer": "Dercvne",
            "model": "DM2 Dimming Host",
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

    @property
    def hs_color(self) -> tuple:
        return self._light.hs_color

    @property
    def rgb_color(self) -> tuple:
        return self._light.rgb_color

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        key = (self._light.group, self._light.address)
        self._entity_registry[key] = self
        _LOGGER.debug("RGBCW Light registered: G=%s A=%s conn=%s",
                       self._light.group, self._light.address, self._conn_id)

    async def async_will_remove_from_hass(self) -> None:
        key = (self._light.group, self._light.address)
        self._entity_registry.pop(key, None)

    def handle_feedback(self, brightness: int = None, color_temp_kelvin: int = None,
                       color_wheel: int = None, saturation: int = None) -> None:
        """Handle feedback from device."""
        if brightness is not None:
            self._light.handle_brightness_feedback(brightness)
        if color_temp_kelvin is not None:
            self._light.handle_color_temp_feedback(color_temp_kelvin)
        if color_wheel is not None:
            self._light.handle_color_wheel_feedback(color_wheel)
            # Switch to HS mode when color wheel feedback received
            self._attr_color_mode = ColorMode.HS
        if saturation is not None:
            self._light.handle_saturation_feedback(saturation)
        elif color_temp_kelvin is not None:
            # Switch to COLOR_TEMP mode when CT feedback received
            self._attr_color_mode = ColorMode.COLOR_TEMP
        self.schedule_update_ha_state()
        _LOGGER.debug(
            "RGBCW %s feedback: on=%s bright=%s ct=%s K wheel=0x%02X sat=%d",
            self._light.name,
            self._light.is_on,
            brightness,
            color_temp_kelvin,
            self._light._color_wheel if color_wheel is not None else 0,
            self._light._saturation if saturation is not None else 0,
        )

    async def async_turn_on(self, **kwargs) -> None:
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        rgb_color = kwargs.get(ATTR_RGB_COLOR)
        hs_color = kwargs.get(ATTR_HS_COLOR)

        await self._light.turn_on(
            brightness=brightness,
            color_temp_kelvin=color_temp_kelvin,
            rgb_color=rgb_color,
            hs_color=hs_color,
        )
        # Update color mode based on what was set
        if rgb_color is not None or hs_color is not None:
            self._attr_color_mode = ColorMode.HS
        elif color_temp_kelvin is not None:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self._light.turn_off()
        self.async_write_ha_state()


class DALIDM2CCTLightEntity(LightEntity):
    """Representation of a DM2 dual color temperature light.

    Uses DM2 standard Class parameter protocol:
      - Brightness: Class=0
      - Color Temp: Class=1 (NOT group+1 like legacy DALI)
    """

    _attr_should_poll = False
    uses_dm2_protocol = True  # Flag for feedback listener

    def __init__(self, light: DALIDM2CCTLight, entry_id: str, device_id: str,
                 entity_registry: dict, conn_id: str):
        self._light = light
        self._entry_id = entry_id
        self._entity_registry = entity_registry
        self._conn_id = conn_id
        self._attr_name = light.name
        self._attr_unique_id = f"{entry_id}_{device_id}"
        self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
        self._attr_color_mode = ColorMode.COLOR_TEMP
        self._attr_min_color_temp_kelvin = COLOR_TEMP_MIN_K
        self._attr_max_color_temp_kelvin = COLOR_TEMP_MAX_K

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._entry_id}_{self._conn_id}")},
            "name": f"D-Bus Module ({self._conn_id[:6]})",
            "manufacturer": "Dercvne",
            "model": "DM2 Dimming Host",
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
        _LOGGER.debug("DM2 CCT Light registered: G=%s A=%s conn=%s",
                      self._light.group, self._light.address, self._conn_id)

    async def async_will_remove_from_hass(self) -> None:
        key = (self._light.group, self._light.address)
        self._entity_registry.pop(key, None)

    def handle_feedback(self, status: bool = None, brightness: int = None,
                       color_temp_kelvin: int = None) -> None:
        """Handle feedback from device.

        For DM2 CCT, class_=0 feedback → brightness, class_=1 → color temp.
        The feedback listener routes based on class_ value.
        """
        if brightness is not None:
            self._light._brightness = brightness
            self._light._is_on = brightness > 0
        elif status is not None:
            self._light._is_on = status

        if color_temp_kelvin is not None:
            self._light._color_temp_k = color_temp_kelvin

        self.schedule_update_ha_state()
        _LOGGER.debug(
            "DM2 CCT %s feedback: on=%s bright=%s ct=%s K",
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
