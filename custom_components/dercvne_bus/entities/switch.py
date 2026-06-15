"""Switch platform for Dercvne Bus relays and keypad functions."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN, DEVICE_TYPE_RELAY, DEVICE_TYPE_KEYPAD
from ..device.relay import DALIRelay
from ..device.keypad import DALIKeypad
from ..device import DALIDeviceConfig
from ..config_flow import _migrate_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DALI relay switches and keypad function switches."""
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

        if dtype == DEVICE_TYPE_RELAY:
            device_id = device_config.get("id", f"{device_config.get('group','?')}_{device_config.get('address','?')}")
            config = DALIDeviceConfig(
                name=device_config.get("name"),
                device_type=DEVICE_TYPE_RELAY,
                group=device_config.get("group"),
                address=device_config.get("address"),
            )
            relay = DALIRelay(config, transport)
            entity = DALIRelaySwitch(relay, entry.entry_id, device_id,
                                     entity_registry, conn_id)
            entities.append(entity)

        elif dtype == DEVICE_TYPE_KEYPAD:
            keypad = DALIKeypad(device_config, transport)
            device_id = device_config.get("id", device_config.get("panel_address", "??"))

            # --- Child Lock switch (only if configured) ---
            if keypad.lock_group and keypad.lock_address:
                lock_config = DALIDeviceConfig(
                    name=f"{keypad.name} 儿童锁",
                    device_type=DEVICE_TYPE_KEYPAD,
                    group=keypad.lock_group,
                    address=keypad.lock_address,
                )
                lock_relay = DALIRelay(lock_config, transport)
                lock_entity = DALIKeypadLockSwitch(
                    keypad, lock_relay, entry.entry_id, device_id,
                    entity_registry, conn_id,
                )
                entities.append(lock_entity)
                _LOGGER.debug("Keypad %s lock entity created (G=%s A=%s)",
                              keypad.name, keypad.lock_group, keypad.lock_address)

            # --- Sleep switch (only if configured) ---
            if keypad.sleep_group and keypad.sleep_address:
                sleep_config = DALIDeviceConfig(
                    name=f"{keypad.name} 休眠",
                    device_type=DEVICE_TYPE_KEYPAD,
                    group=keypad.sleep_group,
                    address=keypad.sleep_address,
                )
                sleep_relay = DALIRelay(sleep_config, transport)
                sleep_entity = DALIKeypadSleepSwitch(
                    keypad, sleep_relay, entry.entry_id, device_id,
                    entity_registry, conn_id,
                )
                entities.append(sleep_entity)
                _LOGGER.debug("Keypad %s sleep entity created (G=%s A=%s)",
                              keypad.name, keypad.sleep_group, keypad.sleep_address)

    async_add_entities(entities)


class DALIRelaySwitch(SwitchEntity):
    """Representation of a DALI relay as a switch."""

    _attr_should_poll = False

    def __init__(self, relay: DALIRelay, entry_id: str, device_id: str,
                 entity_registry: dict, conn_id: str):
        self._relay = relay
        self._entry_id = entry_id
        self._entity_registry = entity_registry
        self._conn_id = conn_id
        self._attr_name = relay.name
        self._attr_unique_id = f"{entry_id}_{device_id}"
        self._attr_is_on = False

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
        key = (self._relay.group, self._relay.address)
        self._entity_registry[key] = self
        _LOGGER.debug("Switch registered: G=%s A=%s conn=%s",
                      self._relay.group, self._relay.address, self._conn_id)

    async def async_will_remove_from_hass(self) -> None:
        key = (self._relay.group, self._relay.address)
        self._entity_registry.pop(key, None)

    def handle_feedback(self, status: bool, brightness: int = None, color_temp_kelvin: int = None) -> None:
        """Handle feedback from the device (relay only uses on/off status)."""
        self._attr_is_on = status
        self.schedule_update_ha_state()
        _LOGGER.debug("Switch %s feedback: %s", self._relay.name, "ON" if status else "OFF")

    async def async_turn_on(self, **kwargs) -> None:
        result = await self._relay.turn_on()
        if result:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        result = await self._relay.turn_off()
        if result:
            self._attr_is_on = False
            self.async_write_ha_state()


class _BaseKeypadSwitch(SwitchEntity):
    """Base class for keypad function switches (lock / sleep).

    Shares the keypad's device_info so the switches appear under the
    keypad panel device in HA, not under the DALI module.
    """

    _attr_should_poll = False

    def __init__(self, keypad: DALIKeypad, relay: DALIRelay,
                 entry_id: str, device_id: str,
                 entity_registry: dict, conn_id: str):
        self._keypad = keypad
        self._relay = relay
        self._entry_id = entry_id
        self._device_uuid = device_id  # stable UUID, unchanged by address edits
        self._entity_registry = entity_registry
        self._conn_id = conn_id
        self._attr_is_on = False

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
        key = (self._relay.group, self._relay.address)
        self._entity_registry[key] = self
        _LOGGER.debug("Keypad switch registered: G=%s A=%s conn=%s",
                      self._relay.group, self._relay.address, self._conn_id)

    async def async_will_remove_from_hass(self) -> None:
        key = (self._relay.group, self._relay.address)
        self._entity_registry.pop(key, None)

    def handle_feedback(self, status: bool, brightness: int = None, color_temp_kelvin: int = None) -> None:
        """Handle feedback via the relay protocol (*S/*C)."""
        self._attr_is_on = status
        self.schedule_update_ha_state()
        _LOGGER.debug("Keypad switch %s feedback: %s",
                      self._relay.name, "ON" if status else "OFF")

    async def async_turn_on(self, **kwargs) -> None:
        result = await self._relay.turn_on()
        if result:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        result = await self._relay.turn_off()
        if result:
            self._attr_is_on = False
            self.async_write_ha_state()


class DALIKeypadLockSwitch(_BaseKeypadSwitch):
    """Child lock switch for keypad panel."""

    _attr_icon = "mdi:lock"

    def __init__(self, keypad, relay, entry_id, device_id, entity_registry, conn_id):
        super().__init__(keypad, relay, entry_id, device_id, entity_registry, conn_id)
        self._attr_name = f"{keypad.name} 儿童锁"
        self._attr_unique_id = f"{entry_id}_{device_id}_lock"


class DALIKeypadSleepSwitch(_BaseKeypadSwitch):
    """Sleep mode switch for keypad panel."""

    _attr_icon = "mdi:sleep"

    def __init__(self, keypad, relay, entry_id, device_id, entity_registry, conn_id):
        super().__init__(keypad, relay, entry_id, device_id, entity_registry, conn_id)
        self._attr_name = f"{keypad.name} 休眠"
        self._attr_unique_id = f"{entry_id}_{device_id}_sleep"
