"""Keypad panel device class for Dercvne Bus integration.

A 485 keypad panel has:
  - panel_address (00-FF): unique hardware address for button events
  - 3 independent function addresses (each with group + address):
      * child lock:    *S / *C  (same protocol as relay)
      * sleep:         *S / *C  (same protocol as relay)
      * backlight:     *A + *Z (same protocol as dimmer brightness)
  - 8 physical buttons, each with short-press (group 0-7) and long-press (group 8-F)
"""

import logging

from ..protocol.encoder import DALICommandEncoder
from .dali_device import DALIDevice
from ..const import DEVICE_TYPE_KEYPAD, KEYPAD_BUTTON_COUNT

_LOGGER = logging.getLogger(__name__)


class DALIKeypad:
    """DALI keypad panel device.

    Unlike other device types, the keypad is not a single actuator but a
    composite device: 3 function controls + 16 button event sources.

    The 3 function controls reuse DALIRelay (lock / sleep) and DALILight
    (backlight) internally.  Button events are handled by the feedback
    listener in __init__.py and dispatched to the sensor entity.
    """

    def __init__(self, config: dict, transport):
        """Initialize keypad from a device-config dict.

        Args:
            config: dict with keys:
                name, panel_address, lock_group, lock_address,
                sleep_group, sleep_address, backlight_group, backlight_address
            transport: a DALITransport instance
        """
        self._name = config.get("name", "Keypad")
        self._panel_address = config.get("panel_address", "").upper()
        self._transport = transport
        self._encoder = DALICommandEncoder()

        self._lock_group = config.get("lock_group", "").upper()
        self._lock_address = config.get("lock_address", "").upper()
        self._sleep_group = config.get("sleep_group", "").upper()
        self._sleep_address = config.get("sleep_address", "").upper()
        self._backlight_group = config.get("backlight_group", "").upper()
        self._backlight_address = config.get("backlight_address", "").upper()

        # State
        self._lock_on = False
        self._sleep_on = False
        self._backlight_brightness = 255  # default full brightness
        self._last_button = ""  # e.g. "key_1_short"

    # ------------------------------------------------------------------ properties

    @property
    def name(self) -> str:
        return self._name

    @property
    def panel_address(self) -> str:
        return self._panel_address

    @property
    def lock_group(self) -> str:
        return self._lock_group

    @property
    def lock_address(self) -> str:
        return self._lock_address

    @property
    def lock_state(self) -> bool:
        return self._lock_on

    @property
    def sleep_group(self) -> str:
        return self._sleep_group

    @property
    def sleep_address(self) -> str:
        return self._sleep_address

    @property
    def sleep_state(self) -> bool:
        return self._sleep_on

    @property
    def backlight_group(self) -> str:
        return self._backlight_group

    @property
    def backlight_address(self) -> str:
        return self._backlight_address

    @property
    def backlight_brightness(self) -> int:
        return self._backlight_brightness

    @property
    def last_button(self) -> str:
        return self._last_button

    # ------------------------------------------------------------------ child lock

    async def lock(self) -> bool:
        """Enable child lock (panel buttons disabled)."""
        cmd = self._encoder.turn_on(self._lock_group, self._lock_address)
        result = await self._transport.send_command(cmd)
        if result:
            self._lock_on = True
            _LOGGER.debug("Keypad %s lock ON (G=%s A=%s)",
                         self._name, self._lock_group, self._lock_address)
        return result

    async def unlock(self) -> bool:
        """Disable child lock (panel buttons enabled)."""
        cmd = self._encoder.turn_off(self._lock_group, self._lock_address)
        result = await self._transport.send_command(cmd)
        if result:
            self._lock_on = False
            _LOGGER.debug("Keypad %s lock OFF (G=%s A=%s)",
                         self._name, self._lock_group, self._lock_address)
        return result

    # ------------------------------------------------------------------ sleep

    async def sleep_on(self) -> bool:
        """Enter sleep mode."""
        cmd = self._encoder.turn_on(self._sleep_group, self._sleep_address)
        result = await self._transport.send_command(cmd)
        if result:
            self._sleep_on = True
            _LOGGER.debug("Keypad %s sleep ON (G=%s A=%s)",
                         self._name, self._sleep_group, self._sleep_address)
        return result

    async def sleep_off(self) -> bool:
        """Exit sleep mode."""
        cmd = self._encoder.turn_off(self._sleep_group, self._sleep_address)
        result = await self._transport.send_command(cmd)
        if result:
            self._sleep_on = False
            _LOGGER.debug("Keypad %s sleep OFF (G=%s A=%s)",
                         self._name, self._sleep_group, self._sleep_address)
        return result

    # ------------------------------------------------------------------ backlight

    async def set_backlight(self, brightness: int) -> bool:
        """Set backlight brightness 0-255."""
        brightness = max(0, min(255, int(brightness)))
        cmd = self._encoder.set_brightness(
            self._backlight_group, self._backlight_address, brightness
        )
        result = await self._transport.send_command(cmd)
        if result:
            self._backlight_brightness = brightness
            _LOGGER.debug("Keypad %s backlight=%d (G=%s A=%s)",
                         self._name, brightness,
                         self._backlight_group, self._backlight_address)
        return result

    # ------------------------------------------------------------------ button events

    def handle_button_event(self, group_value: int) -> str:
        """Parse a keypad button event from the group value in feedback.

        Args:
            group_value: int 0-15  (0-7 = short press on key 1-8,
                                    8-15 = long press on key 1-8)

        Returns:
            A button identifier string, e.g. "key_1_short" or "key_8_long".
        """
        if 0 <= group_value <= 7:
            key_index = group_value + 1  # key 1-8
            action = "short"
        elif 8 <= group_value <= 15:
            key_index = group_value - 7  # key 1-8
            action = "long"
        else:
            return "unknown"

        button_id = f"key_{key_index}_{action}"
        self._last_button = button_id
        _LOGGER.info("Keypad %s button: %s (raw=0x%X)",
                     self._name, button_id, group_value)
        return button_id
