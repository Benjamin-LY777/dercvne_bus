"""Climate platform for Dercvne Bus integration.

Supports:
- VRV Controller (CoolMaster) indoor units
- X1-29-S Thermostat Panel — AC and FH sub-functions
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEVICE_TYPE_VRV_INDOOR, DEVICE_TYPE_THERMOSTAT
from .config_flow import _migrate_data
from .entities.climate import VRVIndoorUnit, ThermostatACEntity, ThermostatFHEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities (VRV indoor units + Thermostat AC/FH)."""
    _, devices = _migrate_data(dict(entry.data))
    entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
    vrv_controllers = entry_data.get("vrv_controllers", {})

    entities = []

    for device_config in devices:
        device_type = device_config.get("device_type", "")

        # ── VRV indoor units ──
        if device_type in (DEVICE_TYPE_VRV_INDOOR, "vrv_indoor"):
            parent_id = device_config.get("parent_id", "")
            vrv_data = vrv_controllers.get(parent_id)
            if vrv_data is None:
                _LOGGER.warning(
                    "VRV indoor unit '%s' references unknown parent '%s', skipping",
                    device_config.get("name"), parent_id,
                )
                continue

            controller = vrv_data.get("controller")
            if controller is None:
                _LOGGER.warning("VRV controller '%s' not connected, skipping", parent_id)
                continue

            entity = VRVIndoorUnit(
                controller=controller,
                vrv_id=parent_id,
                unit_config=device_config,
                entry_id=entry.entry_id,
                conn_id=parent_id,
            )
            entities.append(entity)
            # Register in the VRV controller's entity list for polling updates
            vrv_data.setdefault("entities", []).append(entity)
            continue

        # ── Thermostat panel AC / FH ──
        if device_type == DEVICE_TYPE_THERMOSTAT:
            ac_cfg = device_config.get("ac", {})
            fh_cfg = device_config.get("floor_heating", {})

            conn_id = device_config.get("connection_id", "")
            connections_data = hass.data[DOMAIN][entry.entry_id]["connections"]
            conn = connections_data.get(conn_id)
            if conn is None:
                _LOGGER.warning(
                    "Thermostat %s: conn %s not found",
                    device_config.get("name"), conn_id,
                )
                continue

            transport = conn.get("transport")
            if transport is None:
                continue

            # Look up or create thermostat device wrapper
            th_data = hass.data[DOMAIN][entry.entry_id].setdefault("thermostats", {})
            device_id = device_config.get("id", "")
            if device_id not in th_data:
                from .device.thermostat import ThermostatDevice
                th_data[device_id] = ThermostatDevice(device_config, transport)

            thermostat = th_data[device_id]

            # AC entity
            if ac_cfg.get("enabled"):
                entity = ThermostatACEntity(
                    thermostat, entry.entry_id, device_id, device_config, conn_id,
                )
                entities.append(entity)

            # FH entity
            if fh_cfg.get("enabled"):
                entity = ThermostatFHEntity(
                    thermostat, entry.entry_id, device_id, device_config, conn_id,
                )
                entities.append(entity)

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d climate entities", len(entities))
    else:
        _LOGGER.debug("No climate entities to add")


__all__ = ["async_setup_entry"]
