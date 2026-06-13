"""Base device class for DALI devices."""

import logging
from dataclasses import dataclass
from typing import Optional

_LOGGER = logging.getLogger(__name__)


@dataclass
class DALIDeviceConfig:
    """Configuration for DALI device."""
    name: str
    device_type: str
    group: str
    address: str
    # Optional parameters
    channel: Optional[int] = None
    scene_num: Optional[int] = None


class DALIDevice:
    """Base class for DALI devices."""
    
    def __init__(self, config: DALIDeviceConfig, transport):
        """Initialize DALI device."""
        self._config = config
        self._transport = transport
        self._is_on = False
    
    @property
    def name(self) -> str:
        """Return device name."""
        return self._config.name
    
    @property
    def device_type(self) -> str:
        """Return device type."""
        return self._config.device_type
    
    @property
    def group(self) -> str:
        """Return group address."""
        return self._config.group
    
    @property
    def address(self) -> str:
        """Return device address."""
        return self._config.address
    
    @property
    def is_on(self) -> bool:
        """Return device state."""
        return self._is_on
    
    async def turn_on(self) -> bool:
        """Turn on device."""
        raise NotImplementedError
    
    async def turn_off(self) -> bool:
        """Turn off device."""
        raise NotImplementedError
    
    async def update_state(self) -> None:
        """Update device state from feedback."""
        raise NotImplementedError
