"""Light device class for DALI integration."""

import logging

from ..protocol.encoder import DALICommandEncoder
from ..const import COLOR_TEMP_MIN_K, COLOR_TEMP_MAX_K
from .dali_device import DALIDevice, DALIDeviceConfig

_LOGGER = logging.getLogger(__name__)


class DALILight(DALIDevice):
    """DALI light device (single color or CCT).

    Protocol summary
    ----------------
    - Turn on to brightness X :  *A,0,G,AA;*Z,0XX;   (brightness, class=0, group=G)
    - Turn off                :  *A,0,G,AA;*Z,000;   (brightness = 0)
    - Set color temperature   :  *A,0,G+1,AA;*Z,0XX; (CT channel, class=0, group=G+1)

    For CCT lights the colour-temperature channel uses the same device address
    but increments the group by one.  The class byte in ``*A`` stays 0 for both
    brightness and colour-temperature commands — they are distinguished solely
    by the group digit.

    Only sends commands — feedback is handled by the background listener.
    """

    def __init__(self, config: DALIDeviceConfig, transport):
        """Initialize DALI light."""
        super().__init__(config, transport)
        self._encoder = DALICommandEncoder()
        self._brightness = 0        # 0-255, mirrors device value
        self._color_temp_k = COLOR_TEMP_MIN_K  # Kelvin, mirrors last sent value

    @property
    def brightness(self) -> int:
        """Return brightness (0-255)."""
        return self._brightness

    @property
    def color_temp_kelvin(self) -> int:
        """Return colour temperature in Kelvin."""
        return self._color_temp_k

    @property
    def supports_color_temp(self) -> bool:
        """Return True if this is a CCT (dual colour-temp) light."""
        return self._config.device_type == "light_cct"

    async def turn_on(self, brightness: int = None, color_temp_kelvin: int = None) -> bool:
        """Send turn-on command(s).

        If brightness is provided it is sent as *A,0,G,AA;*Z,0XX;.
        If the device was previously off and no brightness is given,
        restores the last brightness (or 255 if never set).
        For CCT lights, color_temp_kelvin is also sent when provided.
        """
        # Decide brightness value to send
        if brightness is not None:
            new_brightness = max(1, min(255, int(brightness)))
        elif self._brightness == 0:
            new_brightness = 255  # first turn-on: full brightness
        else:
            new_brightness = self._brightness  # restore last level

        # Send brightness command
        cmd = self._encoder.set_brightness(self.group, self.address, new_brightness)
        result = await self._transport.send_command(cmd)
        if result:
            self._brightness = new_brightness
            self._is_on = True
            _LOGGER.debug("Light %s brightness → %d", self.name, new_brightness)

        # Send colour temperature command (CCT lights only)
        if self.supports_color_temp and color_temp_kelvin is not None:
            kelvin = max(COLOR_TEMP_MIN_K, min(COLOR_TEMP_MAX_K, int(color_temp_kelvin)))
            ct_cmd = self._encoder.set_color_temp_kelvin(self.group, self.address, kelvin)
            ct_result = await self._transport.send_command(ct_cmd)
            if ct_result:
                self._color_temp_k = kelvin
                _LOGGER.debug("Light %s colour temp → %d K", self.name, kelvin)

        return result

    async def turn_off(self) -> bool:
        """Send turn-off command: *A,0,G,AA;*Z,000; (brightness = 0)."""
        cmd = self._encoder.set_brightness(self.group, self.address, 0)
        result = await self._transport.send_command(cmd)
        if result:
            self._brightness = 0
            self._is_on = False
            _LOGGER.debug("Light %s turned off", self.name)
        return result

    async def update_state(self) -> None:
        """No-op: state updates come from background feedback listener."""
        pass
