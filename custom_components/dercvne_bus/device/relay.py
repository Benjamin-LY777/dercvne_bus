"""Relay device class for DALI integration."""

import logging

from ..protocol.encoder import DALICommandEncoder
from .dali_device import DALIDevice, DALIDeviceConfig

_LOGGER = logging.getLogger(__name__)


class DALIRelay(DALIDevice):
    """DALI relay device.

    Only sends commands — feedback is handled by the background listener
    in __init__.py which dispatches to entity.handle_feedback().
    """

    def __init__(self, config: DALIDeviceConfig, transport):
        """Initialize DALI relay."""
        super().__init__(config, transport)
        self._encoder = DALICommandEncoder()

    async def turn_on(self) -> bool:
        """Send turn on command."""
        cmd = self._encoder.turn_on(self.group, self.address)
        result = await self._transport.send_command(cmd)
        if result:
            self._is_on = True
            _LOGGER.debug(f"Relay {self.name} turn_on command sent")
        return result

    async def turn_off(self) -> bool:
        """Send turn off command."""
        cmd = self._encoder.turn_off(self.group, self.address)
        result = await self._transport.send_command(cmd)
        if result:
            self._is_on = False
            _LOGGER.debug(f"Relay {self.name} turn_off command sent")
        return result

    async def update_state(self) -> None:
        """No-op: state updates come from background feedback listener."""
        pass
