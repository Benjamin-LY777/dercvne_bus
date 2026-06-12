"""Cover (curtain) device class for DALI integration."""

import logging

from ..protocol.encoder import DALICommandEncoder
from .dali_device import DALIDevice, DALIDeviceConfig

_LOGGER = logging.getLogger(__name__)


class DALICover(DALIDevice):
    """DALI cover device (curtain/blind motor).

    Protocol summary
    ----------------
    - Open   (fully open)   : *A,0,G,AA;*Z,0FF;  (brightness = 255)
    - Close  (fully closed) : *A,0,G,AA;*Z,000;  (brightness = 0)
    - Set position p%        : *A,0,G,AA;*Z,0XX;  (brightness = round(p/100*255))
    - Stop                   : re-send current position to halt motion
    """

    def __init__(self, config: DALIDeviceConfig, transport):
        """Initialize DALI cover."""
        super().__init__(config, transport)
        self._encoder = DALICommandEncoder()
        self._position = 100  # 0 = fully closed, 100 = fully open

    @property
    def position(self) -> int:
        """Return current position (0-100)."""
        return self._position

    async def set_position(self, position: int) -> bool:
        """Set cover to a specific position.

        Args:
            position: 0–100 (0 = fully closed, 100 = fully open).
        """
        position = max(0, min(100, int(position)))
        brightness = round(position / 100 * 255)
        cmd = self._encoder.set_brightness(self.group, self.address, brightness)
        result = await self._transport.send_command(cmd)
        if result:
            self._is_on = position > 0
            self._position = position
            _LOGGER.debug("Cover %s set to %d%%", self.name, position)
        return result

    async def open_cover(self) -> bool:
        """Send open command: *A,0,G,AA;*Z,0FF; (brightness = 255)."""
        return await self.set_position(100)

    async def close_cover(self) -> bool:
        """Send close command: *A,0,G,AA;*Z,000; (brightness = 0)."""
        return await self.set_position(0)

    async def stop_cover(self) -> bool:
        """Send stop command by re-sending the current position value."""
        # Re-sending the current position tells most DALI motor controllers to stop.
        current_brightness = round(self._position / 100 * 255)
        cmd = self._encoder.set_brightness(self.group, self.address, current_brightness)
        result = await self._transport.send_command(cmd)
        if result:
            _LOGGER.debug("Cover %s stop command sent (pos=%d%%)", self.name, self._position)
        return result

    async def update_state(self) -> None:
        """No-op: state updates come from background feedback listener."""
        pass
