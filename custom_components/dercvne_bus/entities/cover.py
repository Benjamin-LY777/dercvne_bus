"""Cover platform for Dercvne Bus curtains/blinds."""

import logging

from homeassistant.components.cover import (
    CoverEntity,
    CoverDeviceClass,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from ..device.cover import DALICover
from ..device import DALIDeviceConfig
from ..config_flow import _migrate_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DALI cover entities."""
    _, devices = _migrate_data(dict(entry.data))
    connections_data = hass.data[DOMAIN][entry.entry_id]["connections"]

    entities = []
    for device_config in devices:
        if device_config.get("device_type") != "cover":
            continue

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
        device_id = device_config.get("id", f"{device_config.get('group','?')}_{device_config.get('address','?')}")

        config = DALIDeviceConfig(
            name=device_config.get("name"),
            device_type="cover",
            group=device_config.get("group"),
            address=device_config.get("address"),
        )
        cover = DALICover(config, transport)
        entity = DALICoverEntity(cover, entry.entry_id, device_id, entity_registry, conn_id)
        entities.append(entity)

    async_add_entities(entities)


class DALICoverEntity(CoverEntity):
    """Representation of a DALI cover (curtain/blind)."""

    _attr_should_poll = False
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, cover: DALICover, entry_id: str, device_id: str,
                 entity_registry: dict, conn_id: str):
        self._cover = cover
        self._entry_id = entry_id
        self._entity_registry = entity_registry
        self._conn_id = conn_id
        self._attr_name = cover.name
        self._attr_unique_id = f"{entry_id}_{device_id}"
        self._attr_is_closed = not cover.is_on
        self._attr_current_cover_position = cover.position

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._entry_id}_{self._conn_id}")},
            "name": f"D-Bus Module ({self._conn_id[:6]})",
            "manufacturer": "Dercvne",
            "model": "D-Bus Module",
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        key = (self._cover.group, self._cover.address)
        self._entity_registry[key] = self
        _LOGGER.debug("Cover registered: G=%s A=%s conn=%s",
                      self._cover.group, self._cover.address, self._conn_id)

    async def async_will_remove_from_hass(self) -> None:
        key = (self._cover.group, self._cover.address)
        self._entity_registry.pop(key, None)

    def handle_feedback(self, status: bool, brightness: int = None, color_temp_kelvin: int = None) -> None:
        """Handle feedback from the device.

        For covers:
        - on/off (status) maps to open/closed.
        - brightness (0-255) maps to position (0-100%) when received from *A/*Z feedback.
        """
        if brightness is not None:
            # Map raw 0-255 device value to 0-100 position
            position = round(brightness / 255 * 100)
            self._cover._position = position
            self._cover._is_on = position > 0
            self._attr_is_closed = position == 0
            self._attr_current_cover_position = position
        else:
            self._cover._is_on = status
            self._attr_is_closed = not status
            self._attr_current_cover_position = 100 if status else 0

        self.schedule_update_ha_state()
        _LOGGER.debug(
            "Cover %s feedback: %s pos=%s%%",
            self._cover.name,
            "OPEN" if not self._attr_is_closed else "CLOSED",
            self._attr_current_cover_position,
        )

    async def async_open_cover(self, **kwargs) -> None:
        await self._cover.open_cover()
        self._attr_is_closed = False
        self._attr_current_cover_position = 100
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs) -> None:
        await self._cover.close_cover()
        self._attr_is_closed = True
        self._attr_current_cover_position = 0
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs) -> None:
        """Move the cover to a specific position (0-100)."""
        position = kwargs.get("position", self._cover.position)
        await self._cover.set_position(position)
        self._attr_is_closed = position == 0
        self._attr_current_cover_position = position
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs) -> None:
        await self._cover.stop_cover()
        self.async_write_ha_state()
