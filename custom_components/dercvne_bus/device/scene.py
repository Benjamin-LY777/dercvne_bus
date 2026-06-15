"""Scene device class for DALI integration."""

import logging

from ..protocol.encoder import DALICommandEncoder
from .dali_device import DALIDevice, DALIDeviceConfig

_LOGGER = logging.getLogger(__name__)


class DALIScene(DALIDevice):
    """DALI scene device."""
    
    def __init__(self, config: DALIDeviceConfig, transport):
        """Initialize DALI scene."""
        super().__init__(config, transport)
        self._encoder = DALICommandEncoder()
        self._scene_num = config.scene_num
    
    @property
    def scene_num(self) -> int:
        """Return scene number."""
        return self._scene_num
    
    async def call_scene(self) -> bool:
        """Call this scene."""
        if self._scene_num is None:
            _LOGGER.error(f"Scene {self.name} has no scene number configured")
            return False
        
        cmd = self._encoder.call_scene(self._scene_num)
        result = await self._transport.send_command(cmd)
        
        if result:
            _LOGGER.info(f"Scene {self.name} (scene {self._scene_num}) called")
        
        return result
    
    async def turn_on(self) -> bool:
        """Alias for call_scene."""
        return await self.call_scene()
    
    async def turn_off(self) -> bool:
        """Scenes cannot be turned off."""
        _LOGGER.warning(f"Scene {self.name} cannot be turned off")
        return False
    
    async def update_state(self) -> None:
        """Scenes don't have state."""
        pass
