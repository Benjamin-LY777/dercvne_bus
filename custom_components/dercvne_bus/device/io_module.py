"""4-channel IO module (dry contact input) device class for Dercvne Bus integration.

A 485 IO module has:
  - module_address (00-FF): unique hardware address
  - 4 input channels, each with short-press (group 0-3) and long-press (group A-D)
  
Protocol examples (address = 33):
  Ch1 short: *S,0,0,33;
  Ch1 long:  *S,0,A,33;
  Ch2 short: *S,0,1,33;
  Ch2 long:  *S,0,B,33;
  Ch3 short: *S,0,2,33;
  Ch3 long:  *S,0,C,33;
  Ch4 short: *S,0,3,33;
  Ch4 long:  *S,0,D,33;
"""

import logging

from ..const import DEVICE_TYPE_IO_MODULE, IO_MODULE_CHANNEL_COUNT

_LOGGER = logging.getLogger(__name__)

# Map group value -> (channel, action)
# Short press: group 0-3 -> channel 1-4, action "short"
# Long press:  group A-D (10-13) -> channel 1-4, action "long"
_GROUP_MAP = {}
for _ch in range(1, IO_MODULE_CHANNEL_COUNT + 1):
    _s = _ch - 1          # short: 0,1,2,3
    _l = _ch - 1 + 0xA  # long:  A,B,C,D (10,11,12,13)
    _GROUP_MAP[_s] = (_ch, "short")
    _GROUP_MAP[_l] = (_ch, "long")


class DALIIOModule:
    """DALI 4-channel IO module device.

    Unlike keypad, the IO module uses a single module_address (00-FF)
    and the group field in *S command indicates the channel + press type.
    """

    def __init__(self, config: dict):
        """Initialize IO module from a device-config dict.

        Args:
            config: dict with keys: name, module_address
        """
        self._name = config.get("name", "IO Module")
        self._module_address = config.get("address", "").upper()
        self._last_button = ""  # e.g. "ch_1_short"

    # ------------------------------------------------------------------ properties

    @property
    def name(self) -> str:
        return self._name

    @property
    def module_address(self) -> str:
        return self._module_address

    # ------------------------------------------------------------------ event handling

    def handle_io_event(self, group_value: int) -> str:
        """Parse an IO module event from the group value in feedback.

        Args:
            group_value: int 0-3 (short) or 10-13 (long, A-D)

        Returns:
            A channel event string, e.g. "ch_1_short" or "ch_4_long".
        """
        result = _GROUP_MAP.get(group_value)
        if result is None:
            _LOGGER.warning(
                "IO Module %s: unrecognized group value 0x%X",
                self._name, group_value,
            )
            return "unknown"

        channel, action = result
        event_id = f"ch_{channel}_{action}"
        self._last_button = event_id
        _LOGGER.info(
            "IO Module %s event: %s (raw=0x%X)",
            self._name, event_id, group_value,
        )
        return event_id
