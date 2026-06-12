"""Scene platform for Dercvne Bus scenes.

Supports two device types:
  1. "scene"       — legacy *S-format scene (Address=0 workaround)
  2. "dali_scene"   — >D pass-through DALI scene call (port/group/scene)
"""

import logging

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN, DEVICE_TYPE_DALI_SCENE
from ..device.scene import DALIScene
from ..device.dali_scene import DALISceneDevice
from ..device import DALIDeviceConfig
from ..config_flow import _migrate_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DALI scenes."""
    _, devices = _migrate_data(dict(entry.data))
    connections_data = hass.data[DOMAIN][entry.entry_id]["connections"]

    entities = []
    for device_config in devices:
        dt = device_config.get("device_type", "")

        # ── Legacy scene type (*S command) ──
        if dt == "scene":
            conn_id = device_config.get("connection_id", "")
            conn = connections_data.get(conn_id)
            if conn is None:
                _LOGGER.warning(
                    "Scene %s references unknown connection_id=%s, skipping",
                    device_config.get("name"), conn_id,
                )
                continue

            transport = conn["transport"]
            device_id = device_config.get("id", f"scene_{device_config.get('scene_num', '?')}")

            config = DALIDeviceConfig(
                name=device_config.get("name"),
                device_type="scene",
                group=device_config.get("group", "0"),
                address=device_config.get("address", "00"),
                scene_num=device_config.get("scene_num"),
            )
            dev = DALIScene(config, transport)
            entity = DALISceneEntity(
                dev, entry.entry_id, device_id, conn_id, name=dev.name,
            )
            entities.append(entity)
            continue

        # ── New dali_scene type (>D pass-through command) ──
        if dt == DEVICE_TYPE_DALI_SCENE:
            conn_id = device_config.get("connection_id", "")
            conn = connections_data.get(conn_id)
            if conn is None:
                _LOGGER.warning(
                    "DALI scene '%s' references unknown connection_id=%s, skipping",
                    device_config.get("name"), conn_id,
                )
                continue

            transport = conn["transport"]
            device_id = device_config.get("id", f"dali_scene_{device_config.get('name', '?')}")

            dev = DALISceneDevice(
                name=device_config.get("name", "DALI Scene"),
                port=device_config.get("port", "0"),
                group=device_config.get("group", "00"),
                scene=device_config.get("scene", "09"),
                transport=transport,
            )
            entity = DALISceneEntity(
                dev, entry.entry_id, device_id, conn_id, name=dev.name,
            )
            entities.append(entity)

    async_add_entities(entities)


class DALISceneEntity(Scene):
    """Representation of a DALI scene (legacy or new >D type).

    Accepts either DALIScene (legacy) or DALISceneDevice (new)
    as the delegate.  Both expose an `activate()` / `call_scene()`
    method and a `.name` property.
    """

    def __init__(
        self,
        delegate,
        entry_id: str,
        device_id: str,
        conn_id: str,
        name: str = None,
    ):
        self._delegate = delegate
        self._entry_id = entry_id
        self._conn_id = conn_id
        self._attr_name = name or getattr(delegate, "name", "Scene")
        self._attr_unique_id = f"{entry_id}_{device_id}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._entry_id}_{self._conn_id}")},
            "name": f"D-Bus Module ({self._conn_id[:6]})",
            "manufacturer": "Dercvne",
            "model": "D-Bus Module",
        }

    async def async_activate(self, **kwargs) -> None:
        """Activate the scene."""
        # Both DALIScene (legacy) and DALISceneDevice (new) implement
        # either `call_scene()` or `activate()`.
        if hasattr(self._delegate, "activate"):
            await self._delegate.activate()
        elif hasattr(self._delegate, "call_scene"):
            await self._delegate.call_scene()
