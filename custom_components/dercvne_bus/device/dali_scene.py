"""DALI Scene device — direct DALI bus pass-through scene call.

Uses >D command format to send raw DALI scene activation commands
to specific DALI groups on a 4-port DALI module.

Command:  >D,{port},E,0,{group},{scene};
  port:   0-3    (4-way DALI bus port)
  group:  00-15  (DALI group address 1-16)
  scene:  09-18  (DALI scene 1-16, 0x09=scene1 … 0x18=scene16)
"""

import logging

from ..protocol.encoder import DALICommandEncoder

_LOGGER = logging.getLogger(__name__)


class DALISceneDevice:
    """DALI scene device that sends >D pass-through commands."""

    def __init__(
        self,
        name: str,
        port: str,
        group: str,
        scene: str,
        transport,
    ):
        """Initialize DALI scene device.

        Args:
            name:     Human-readable scene name.
            port:     DALI bus port, "0"–"3".
            group:    DALI group,  "00"–"15" (hex string).
            scene:    DALI scene,  "09"–"18" (hex string).
            transport: Async transport for sending commands.
        """
        self._name = name
        self._port = port
        self._group = group
        self._scene = scene
        self._transport = transport
        self._encoder = DALICommandEncoder()

    @property
    def name(self) -> str:
        """Return scene name."""
        return self._name

    @property
    def port(self) -> str:
        """Return DALI bus port."""
        return self._port

    @property
    def group(self) -> str:
        """Return DALI group."""
        return self._group

    @property
    def scene(self) -> str:
        """Return DALI scene address."""
        return self._scene

    async def activate(self) -> bool:
        """Activate this DALI scene.

        Sends >D,{port},E,0,{group},{scene}; to the DALI bus.
        """
        cmd = self._encoder.call_dali_scene(self._port, self._group, self._scene)
        result = await self._transport.send_command(cmd)

        if result:
            _LOGGER.info(
                "DALI scene '%s' activated (port=%s, group=%s, scene=%s)",
                self._name, self._port, self._group, self._scene,
            )
        else:
            _LOGGER.error(
                "Failed to activate DALI scene '%s' (port=%s, group=%s, scene=%s)",
                self._name, self._port, self._group, self._scene,
            )

        return result
