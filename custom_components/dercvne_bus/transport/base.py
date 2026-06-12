"""Base transport class for DALI communication."""

import logging
from abc import ABC, abstractmethod
from typing import Optional

_LOGGER = logging.getLogger(__name__)


class DALITransport(ABC):
    """Base class for DALI transport."""
    
    def __init__(self, timeout: int = 2):
        """Initialize the transport."""
        self._timeout = timeout
        self._connected = False
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the DALI module."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the DALI module."""
        pass
    
    @abstractmethod
    async def send_command(self, command: str) -> bool:
        """Send command to DALI module."""
        pass
    
    @abstractmethod
    async def receive_feedback(self) -> Optional[str]:
        """Receive feedback from DALI module."""
        pass
    
    @property
    def is_connected(self) -> bool:
        """Return connection status."""
        return self._connected
    
    def mark_disconnected(self) -> None:
        """Mark transport as disconnected so reconnect loop can trigger."""
        self._connected = False
        _LOGGER.warning("Transport marked as disconnected")
    
    async def send_bytes(self, data: bytes) -> bool:
        """Send raw bytes. Override in subclasses for native bytes support.
        
        Default implementation: log a warning and drop.
        Subclasses (TCPTransport, SerialTransport) must override this.
        """
        _LOGGER.warning(
            "send_bytes() not implemented for %s, dropping %d bytes",
            type(self).__name__, len(data),
        )
        return False
    
    async def test_connection(self) -> bool:
        """Test if connection is alive."""
        return self._connected
