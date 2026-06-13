"""Sensor platform for Dercvne Bus keypad and IO module events."""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN, DEVICE_TYPE_KEYPAD, DEVICE_TYPE_IO_MODULE
from ..device.keypad import DALIKeypad
from ..device.io_module import DALIIOModule
from ..config_flow import _migrate_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DALI keypad button sensors and IO module sensors."""
    _, devices = _migrate_data(dict(entry.data))
    connections_data = hass.data[DOMAIN][entry.entry_id]["connections"]

    entities = []
    for device_config in devices:
        if device_config.get("device_type") == DEVICE_TYPE_KEYPAD:
            conn_id = device_config.get("connection_id", "")
            conn = connections_data.get(conn_id)
            if conn is None:
                _LOGGER.warning(
                    "Keypad %s references unknown connection_id=%s, skipping",
                    device_config.get("name"), conn_id,
                )
                continue

            transport = conn["transport"]
            entity_registry = conn["entity_registry"]
            device_id = device_config.get("id", device_config.get("panel_address", "??"))

            keypad = DALIKeypad(device_config, transport)
            entity = DALIKeypadSensor(keypad, entry.entry_id, device_id,
                                      entity_registry, conn_id)
            entities.append(entity)

        elif device_config.get("device_type") == DEVICE_TYPE_IO_MODULE:
            conn_id = device_config.get("connection_id", "")
            conn = connections_data.get(conn_id)
            if conn is None:
                _LOGGER.warning(
                    "IO Module %s references unknown connection_id=%s, skipping",
                    device_config.get("name"), conn_id,
                )
                continue

            entity_registry = conn["entity_registry"]
            device_id = device_config.get("id", device_config.get("address", "??"))

            io_module = DALIIOModule(device_config)
            entity = DALIIOModuleSensor(io_module, entry.entry_id, device_id,
                                        entity_registry, conn_id)
            entities.append(entity)

    async_add_entities(entities)


class DALIKeypadSensor(SensorEntity):
    """Representation of a keypad button event as a sensor.

    The sensor state reflects the last button press, formatted as:
      "key_1_short", "key_1_long", ..., "key_8_short", "key_8_long"

    Users can trigger automations by watching this sensor's state change.
    """

    _attr_should_poll = False
    _attr_icon = "mdi:remote"

    def __init__(self, keypad: DALIKeypad, entry_id: str, device_id: str,
                 entity_registry: dict, conn_id: str):
        self._keypad = keypad
        self._entry_id = entry_id
        self._device_uuid = device_id  # stable UUID, unchanged by address edits
        self._entity_registry = entity_registry
        self._conn_id = conn_id
        self._attr_name = f"{keypad.name} 按键"
        self._attr_unique_id = f"{entry_id}_{device_id}_button"
        self._attr_native_value = "none"

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

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Register by panel_address so feedback listener can find us
        key = ("__keypad__", self._keypad.panel_address)
        self._entity_registry[key] = self
        _LOGGER.debug("Keypad sensor registered: PA=%s conn=%s",
                      self._keypad.panel_address, self._conn_id)

    async def async_will_remove_from_hass(self) -> None:
        key = ("__keypad__", self._keypad.panel_address)
        self._entity_registry.pop(key, None)

    def handle_feedback(self, button_id: str) -> None:
        """Handle a button press event from the feedback listener.

        Args:
            button_id: e.g. "key_1_short", "key_8_long"
        """
        self._attr_native_value = button_id
        self.schedule_update_ha_state()
        _LOGGER.debug("Keypad %s sensor updated: %s",
                      self._keypad.name, button_id)


class DALIIOModuleSensor(SensorEntity):
    """Representation of an IO module channel event as a sensor.

    The sensor state reflects the last input trigger, formatted as:
      "ch_1_short", "ch_1_long", ..., "ch_4_short", "ch_4_long"
    """

    _attr_should_poll = False
    _attr_icon = "mdi:connection"

    def __init__(self, io_module: DALIIOModule, entry_id: str, device_id: str,
                 entity_registry: dict, conn_id: str):
        self._io_module = io_module
        self._entry_id = entry_id
        self._device_uuid = device_id  # stable UUID, unchanged by address edits
        self._entity_registry = entity_registry
        self._conn_id = conn_id
        self._attr_name = f"{io_module.name} 输入状态"
        self._attr_unique_id = f"{entry_id}_{device_id}_io"
        self._attr_native_value = "无"

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, f"{self._entry_id}_{self._device_uuid}"),
                (DOMAIN, f"{self._entry_id}_{self._conn_id}_{self._io_module.module_address}"),
            },
            "name": f"D-Bus IO Module ({self._io_module.module_address})",
            "manufacturer": "Dercvne",
            "model": "4路 IO模块",
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Register by module_address so feedback listener can find us
        key = ("__io_module__", self._io_module.module_address)
        self._entity_registry[key] = self
        _LOGGER.debug("IO Module sensor registered: A=%s conn=%s",
                      self._io_module.module_address, self._conn_id)

    async def async_will_remove_from_hass(self) -> None:
        key = ("__io_module__", self._io_module.module_address)
        self._entity_registry.pop(key, None)

    def handle_feedback(self, event_id: str) -> None:
        """Handle an IO module event from the feedback listener.

        Args:
            event_id: e.g. "ch_1_short", "ch_4_long"
        """
        self._attr_native_value = event_id
        self.schedule_update_ha_state()
        _LOGGER.debug("IO Module %s sensor updated: %s",
                      self._io_module.name, event_id)
