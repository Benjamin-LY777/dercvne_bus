"""RGBCW light device class for DM2 dimming host."""

import logging

from ..protocol.encoder import DALICommandEncoder
from ..const import COLOR_TEMP_MIN_K, COLOR_TEMP_MAX_K
from .dali_device import DALIDevice, DALIDeviceConfig

_LOGGER = logging.getLogger(__name__)


class DALIRGBCWLight(DALIDevice):
    """RGBCW light device (DM2 dimming host).

    Protocol summary
    ----------------
    - Brightness      : *A,0,G,AA;*Z,0XX;     (Class=0)
    - Color temp     : *A,1,G,AA;*Z,0XX;     (Class=1, 2200-6500K)
    - Color wheel    : *A,2,G,AA;*Z,0WW;     (Class=2, 0x00-0xFF = 0-360°)
    - Saturation     : *A,3,G,AA;*Z,0SS;     (Class=3, 0x00=CW mixed in, 0xFF=pure color)
    - RGB color      : *A,4,G,AA;*Z,1RR;*Z,1GG;*Z,1BB;*Z,000;  (Class=4, NOT used by Nice driver)

    NOTE: Nice driver uses Class 2 + Class 3 for color control, NOT Class 4.
          Home Assistant provides hs_color (hue 0-360, saturation 0-100),
          which maps directly to Class 2 + Class 3.
    """

    def __init__(self, config: DALIDeviceConfig, transport):
        """Initialize RGBCW light."""
        super().__init__(config, transport)
        self._encoder = DALICommandEncoder()
        self._brightness = 0         # 0-255
        self._color_temp_k = COLOR_TEMP_MIN_K  # Kelvin
        self._color_wheel = 0        # 0-255 (0x00=red, 0xFF=wraps to red)
        self._saturation = 255      # 0-255 (0=CW mixed in, 255=pure color)

    # --- Properties ----------------------------------------------------------

    @property
    def brightness(self) -> int:
        """Return brightness (0-255)."""
        return self._brightness

    @property
    def color_temp_kelvin(self) -> int:
        """Return colour temperature in Kelvin."""
        return self._color_temp_k

    @property
    def hs_color(self) -> tuple:
        """Return HS colour (hue 0-360, saturation 0-100)."""
        # Convert color wheel to hue
        h = (self._color_wheel / 255.0) * 360.0
        # Convert saturation to 0-100
        s = (self._saturation / 255.0) * 100.0
        return (h, s)

    @property
    def supports_color_temp(self) -> bool:
        """Return True (RGBCW supports colour temperature)."""
        return True

    @property
    def supports_color(self) -> bool:
        """Return True (RGBCW supports color via color wheel + saturation)."""
        return True

    # --- Control methods -----------------------------------------------------

    async def turn_on(
        self,
        brightness: int = None,
        color_temp_kelvin: int = None,
        rgb_color: tuple = None,
        hs_color: tuple = None,
    ) -> bool:
        """Send turn-on command(s).

        Args:
            brightness:       0-255 (None = restore last).
            color_temp_kelvin: 2200-6500 K (None = no change).
            rgb_color:        (R, G, B) each 0-255 (None = no change).
            hs_color:         (hue, saturation) - used for color control.
        """
        success = True

        # --- Brightness ---
        # Only send brightness command when:
        #   1. brightness is explicitly provided, OR
        #   2. no color params (hs_color/rgb_color) → normal on/off
        # When only changing color (hs_color/rgb_color without brightness),
        # do NOT send brightness command (Nice driver doesn't do this either).
        color_only = (hs_color is not None or rgb_color is not None) and brightness is None

        if not color_only:
            if brightness is not None:
                new_brightness = max(1, min(255, int(brightness)))
            elif self._brightness == 0:
                new_brightness = 255
            else:
                new_brightness = self._brightness

            cmd = self._encoder.set_brightness(self.group, self.address, new_brightness)
            result = await self._transport.send_command(cmd)
            if result:
                self._brightness = new_brightness
                self._is_on = True
                _LOGGER.debug("RGBCW %s brightness → %d", self.name, new_brightness)
            else:
                success = False

        # --- Colour temperature (Class=1, DM2 standard) ---
        if color_temp_kelvin is not None and success:
            kelvin = max(COLOR_TEMP_MIN_K, min(COLOR_TEMP_MAX_K, int(color_temp_kelvin)))
            ct_cmd = self._encoder.set_color_temp_kelvin(
                self.group, self.address, kelvin, use_class_param=True,
            )
            ct_result = await self._transport.send_command(ct_cmd)
            if ct_result:
                self._color_temp_k = kelvin
                _LOGGER.debug("RGBCW %s colour temp → %d K", self.name, kelvin)
            else:
                success = False

        # --- Color (use color wheel + saturation, Class 2 + Class 3) ---
        # Nice driver uses Class 2 (color wheel) + Class 3 (saturation)
        # HA provides hs_color (hue 0-360, saturation 0-100)
        #   Hue → Color wheel (0x00-0xFF)
        #   Saturation → Saturation (0x00-0xFF)
        
        actual_hs = None
        if hs_color is not None:
            actual_hs = hs_color
        elif rgb_color is not None:
            # Convert RGB to HS
            r, g, b = rgb_color
            r01, g01, b01 = r / 255.0, g / 255.0, b / 255.0
            max_c = max(r01, g01, b01)
            min_c = min(r01, g01, b01)
            delta = max_c - min_c
            
            if delta == 0:
                h = 0
            elif max_c == r01:
                h = (60 * ((g01 - b01) / delta) + 360) % 360
            elif max_c == g01:
                h = (60 * ((b01 - r01) / delta) + 120) % 360
            else:
                h = (60 * ((r01 - g01) / delta) + 240) % 360
            
            s = 0 if max_c == 0 else (delta / max_c) * 100.0
            actual_hs = (h, s)
            _LOGGER.debug("RGBCW %s: Converted RGB to HS (h=%.1f, s=%.1f)", self.name, h, s)

        if actual_hs is not None and success:
            h, s = actual_hs
            
            # Convert HS to color wheel (Class 2) and saturation (Class 3)
            # Hue 0-360° → Color wheel 0x00-0xFF
            wheel_value = int(h / 360.0 * 255)
            wheel_value = max(0, min(255, wheel_value))
            
            # Saturation 0-100% → 0x00-0xFF
            sat_value = int(s / 100.0 * 255)
            sat_value = max(0, min(255, sat_value))
            
            # Send color wheel command (Class 2)
            wheel_cmd = self._encoder.set_color_wheel(self.group, self.address, wheel_value)
            wheel_result = await self._transport.send_command(wheel_cmd)
            
            # Send saturation command (Class 3)
            sat_cmd = self._encoder.set_saturation(self.group, self.address, sat_value)
            sat_result = await self._transport.send_command(sat_cmd)
            
            if wheel_result and sat_result:
                self._color_wheel = wheel_value
                self._saturation = sat_value
                _LOGGER.debug(
                    "RGBCW %s color wheel → 0x%02X, saturation → %d (h=%.1f, s=%.1f)",
                    self.name, wheel_value, sat_value, h, s,
                )
            else:
                success = False

        return success

    async def turn_off(self) -> bool:
        """Send turn-off command: brightness → 0."""
        cmd = self._encoder.set_brightness(self.group, self.address, 0)
        result = await self._transport.send_command(cmd)
        if result:
            self._brightness = 0
            self._is_on = False
            _LOGGER.debug("RGBCW %s turned off", self.name)
        return result

    # --- Feedback handlers (called by __init__.py listener) --------------------

    def handle_brightness_feedback(self, brightness: int) -> None:
        """Handle brightness feedback from device."""
        self._brightness = max(0, min(255, brightness))
        self._is_on = self._brightness > 0
        _LOGGER.debug("RGBCW %s brightness feedback: %d", self.name, self._brightness)

    def handle_color_temp_feedback(self, kelvin: int) -> None:
        """Handle colour temperature feedback (Kelvin)."""
        self._color_temp_k = max(COLOR_TEMP_MIN_K, min(COLOR_TEMP_MAX_K, int(kelvin)))
        _LOGGER.debug(
            "RGBCW %s CT feedback: %d K",
            self.name, self._color_temp_k,
        )

    def handle_color_wheel_feedback(self, wheel_value: int) -> None:
        """Handle color wheel feedback (Class=2)."""
        self._color_wheel = max(0, min(255, wheel_value))
        _LOGGER.debug("RGBCW %s color wheel feedback: 0x%02X", self.name, wheel_value)

    def handle_saturation_feedback(self, saturation: int) -> None:
        """Handle saturation feedback (Class=3)."""
        self._saturation = max(0, min(255, saturation))
        _LOGGER.debug("RGBCW %s saturation feedback: %d", self.name, saturation)

    async def update_state(self) -> None:
        """No-op: state updates come from background feedback listener."""
        pass
