"""Occupancy sensor device class for Dercvne Bus integration."""

import logging

_LOGGER = logging.getLogger(__name__)


class DALIOccupancySensor:
    """Dercvne Bus SH-808R-S occupancy sensor device.

    Unlike other D-Bus devices, the occupancy sensor does NOT use the
    standard group/address protocol.  It broadcasts 9-byte status frames
    spontaneously and does not accept commands.

    Protocol:
      - Search command:  FA D4 C1 00 07 00 01 9C AF (9 bytes)
      - Search response: 17-byte frame, address at bytes 11-12 (XX YY)
      - Status frame:    00 00 00 00 00 XX YY TT SS  (9 bytes)
          XX YY = device address (2-byte hex, matches config ``address``)
          TT     = sensor type (0x01 or 0x02)
          SS     = occupancy status (0x01 = occupied, 0x00 = vacant)

    No commands are sent to the sensor; state updates come exclusively
    via status frames parsed by the feedback listener in ``__init__.py``.
    """

    MODEL_NAME = "SH-808R-S"

    def __init__(self, device_config: dict, transport):
        """Initialise occupancy sensor from a raw device-config dict.

        ``device_config`` must contain at least ``"name"`` and ``"address"``
        (the 4-character hex XXYY address string).
        """
        self._config = device_config
        self._transport = transport
        self._name = device_config.get("name", "Unknown Sensor")
        self._address = device_config.get("address", "0000").upper()
        self._is_occupied = False
        self._sensor_type = None   # 0x01 or 0x02, set on first status frame
        self._entity = None        # set by the entity when it attaches

    # -- Public properties ------------------------------------------------

    @property
    def name(self) -> str:
        """Return the user-assigned device name."""
        return self._name

    @property
    def address(self) -> str:
        """Return the sensor address (4-char hex XXYY string)."""
        return self._address

    @property
    def is_occupied(self) -> bool:
        """``True`` when the sensor currently reports occupancy."""
        return self._is_occupied

    @property
    def sensor_type(self) -> int | None:
        """Sensor-type byte (TT) from the most recent status frame, or *None*."""
        return self._sensor_type

    # -- Entity wiring ----------------------------------------------------

    def set_entity(self, entity) -> None:
        """Called by the entity so the device can trigger HA state updates."""
        self._entity = entity

    # -- Status-frame handler ---------------------------------------------

    def handle_status_frame(self, sensor_type: int, status: int) -> None:
        """Decode a status frame that matched this sensor's address.

        Args:
            sensor_type:  TT byte (1 or 2).
            status:       SS byte (1 = occupied, 0 = vacant).
        """
        self._sensor_type = sensor_type
        new_occupied = (status == 0x01)

        if new_occupied != self._is_occupied:
            self._is_occupied = new_occupied
            _LOGGER.debug(
                "Occupancy sensor %s [%s] → %s",
                self._name, self._address,
                "有人" if new_occupied else "无人",
            )
            if self._entity is not None:
                self._entity.handle_feedback()

    # -- No-op (state updates are push-only) ------------------------------

    async def update_state(self) -> None:
        """No-op — state updates come exclusively from status frames."""
        pass
