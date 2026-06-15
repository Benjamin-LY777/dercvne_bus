"""Binary sensor platform for Dercvne Bus SH-808R-S occupancy sensor."""

import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN, DEVICE_TYPE_OCCUPANCY
from ..device.occupancy_sensor import DALIOccupancySensor
from ..config_flow import _migrate_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SH-808R-S occupancy binary sensors."""
    _LOGGER.debug("BINARY_SENSOR SETUP START for entry %s", entry.entry_id)

    _, devices = _migrate_data(dict(entry.data))
    _LOGGER.debug("BINARY_SENSOR: migrated data, got %d devices", len(devices))

    connections_data = hass.data[DOMAIN][entry.entry_id]["connections"]
    _LOGGER.debug("BINARY_SENSOR: got %d connections", len(connections_data))

    entities = []
    for device_config in devices:
        if device_config.get("device_type") != DEVICE_TYPE_OCCUPANCY:
            continue

        conn_id = device_config.get("connection_id", "")
        conn = connections_data.get(conn_id)
        if conn is None:
            _LOGGER.warning(
                "Occupancy sensor %s references unknown connection_id=%s, skipping",
                device_config.get("name"), conn_id,
            )
            continue

        transport = conn["transport"]
        entity_registry = conn["entity_registry"]
        device_id = device_config.get("id", device_config.get("address", "??"))

        sensor_device = DALIOccupancySensor(device_config, transport)
        entity = DALIOccupancyBinarySensor(
            sensor_device, entry.entry_id, device_id, entity_registry, conn_id,
        )
        sensor_device.set_entity(entity)
        entities.append(entity)
        _LOGGER.debug(
            "BINARY_SENSOR: created entity for addr=%s name=%s",
            device_config.get("address"), device_config.get("name"),
        )

    _LOGGER.debug("BINARY_SENSOR: adding %d entities", len(entities))
    async_add_entities(entities)
    _LOGGER.debug("BINARY_SENSOR SETUP COMPLETE: %d entities added", len(entities))


class DALIOccupancyBinarySensor(BinarySensorEntity):
    """Representation of an SH-808R-S occupancy sensor as a binary sensor.

    Listens for status frames broadcast on the bus:
        00 00 00 00 00 XX YY TT SS
    The feedback listener in __init__.py decodes these and calls
    async_schedule_update_ha_state() on this entity.
    """

    _attr_should_poll = False
    # has_entity_name must be True for HA to look up entity-level state
    # translations (entity.binary_sensor.sh_808r_s.state.on/off).
    # The entity name is still controlled by _attr_name (set in __init__).
    # We do NOT set a "name" key in translations so each sensor keeps
    # its individual name (e.g. "感应器 1A2B").
    _attr_has_entity_name = True
    _attr_icon = "mdi:motion-sensor"
    _attr_translation_key = "sh_808r_s"

    def __init__(self, sensor_device: DALIOccupancySensor,
                 entry_id: str, device_id: str,
                 entity_registry: dict, conn_id: str):
        self._sensor = sensor_device
        self._entry_id = entry_id
        self._device_id = device_id
        self._entity_registry = entity_registry
        self._conn_id = conn_id
        self._attr_name = sensor_device.name
        self._attr_unique_id = f"{entry_id}_{device_id}"
        self._attr_is_on = False

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, f"{self._entry_id}_{self._device_id}"),
            },
            "name": self._sensor.name,
            "manufacturer": "Dercvne",
            "model": "SH-808R-S 占用感应器",
        }

    @property
    def is_on(self) -> bool:
        """Return true if the sensor detects occupancy."""
        return self._sensor.is_occupied

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Register by address so the feedback listener can find us
        key = ("__occupancy__", self._sensor.address)
        self._entity_registry[key] = self
        _LOGGER.debug(
            "Occupancy sensor registered: addr=%s conn=%s",
            self._sensor.address, self._conn_id,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister from the feedback listener."""
        key = ("__occupancy__", self._sensor.address)
        self._entity_registry.pop(key, None)
        await super().async_will_remove_from_hass()

    def handle_feedback(self) -> None:
        """Called by the sensor device when occupancy state changes."""
        self._attr_is_on = self._sensor.is_occupied
        self.async_schedule_update_ha_state()
