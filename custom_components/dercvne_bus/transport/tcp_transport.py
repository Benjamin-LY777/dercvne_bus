"""TCP transport for DALI communication."""

import logging
import asyncio
from typing import Optional

from .base import DALITransport

_LOGGER = logging.getLogger(__name__)


class TCPTransport(DALITransport):
    """TCP transport for network communication."""
    
    def __init__(
        self,
        host: str,
        port: int = 502,
        timeout: int = 2
    ):
        """Initialize TCP transport."""
        super().__init__(timeout)
        self._host = host
        self._port = port
        self._reader = None
        self._writer = None
        self._read_lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """Connect to TCP server."""
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port
            )
            self._connected = True
            _LOGGER.info(f"Connected to TCP {self._host}:{self._port}")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to connect to TCP {self._host}:{self._port}: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from TCP server."""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None
        self._connected = False
        _LOGGER.info(f"Disconnected from TCP {self._host}:{self._port}")

    def mark_disconnected(self) -> None:
        """Mark as disconnected and clean up stale socket state."""
        self._connected = False
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
        self._reader = None
        self._writer = None
        _LOGGER.warning("TCP %s:%s marked as disconnected", self._host, self._port)
    
    async def send_bytes(self, data: bytes) -> bool:
        """Send raw bytes via TCP."""
        if not self._connected:
            _LOGGER.warning(
                "TCP %s:%s not connected, cannot send bytes",
                self._host, self._port,
            )
            return False
        try:
            self._writer.write(data)
            await self._writer.drain()
            _LOGGER.debug("Sent %d bytes", len(data))
            return True
        except (ConnectionError, OSError) as e:
            _LOGGER.error("Send bytes failed (connection error): %s", e)
            self.mark_disconnected()
            return False
        except Exception as e:
            _LOGGER.error("Failed to send bytes: %s", e)
            return False

    async def send_command(self, command: str) -> bool:
        """Send command via TCP, with auto-reconnect if disconnected."""
        if not self._connected:
            _LOGGER.warning("TCP %s:%s not connected, attempting reconnect...",
                           self._host, self._port)
            if not await self.connect():
                _LOGGER.error("Reconnect failed, command dropped: %s", command)
                return False
        
        try:
            self._writer.write(command.encode("ascii"))
            await self._writer.drain()
            _LOGGER.debug(f"Sent command: {command}")
            return True
        except (ConnectionError, OSError) as e:
            _LOGGER.error("Send failed (connection error): %s", e)
            self.mark_disconnected()
            return False
        except Exception as e:
            _LOGGER.error(f"Failed to send command: {e}")
            return False
    
    async def read(self, n: int = 256) -> Optional[bytes]:
        """Read raw data from the TCP stream (for background listener).

        Returns raw bytes (not decoded).  Callers that need text can
        decode appropriately.  This preserves binary protocol frames
        (e.g. Sicoo) that may contain bytes which decode to
        whitespace in latin-1.

        Returns None when disconnected or on error. Calls mark_disconnected()
        when a connection loss is detected so the listener can trigger reconnect.
        """
        if not self._connected or not self._reader:
            return None

        try:
            async with self._read_lock:
                data = await self._reader.read(n)
            if data:
                return data  # Return raw bytes directly
            # Empty data = remote closed connection
            _LOGGER.warning("TCP %s:%s closed by remote", self._host, self._port)
            self.mark_disconnected()
            return None
        except (ConnectionError, ConnectionResetError, ConnectionAbortedError,
            BrokenPipeError, OSError) as e:
            _LOGGER.warning("TCP %s:%s read error: %s", self._host, self._port, e)
            self.mark_disconnected()
            return None
        except Exception as e:
            _LOGGER.debug("Read error: %s", e)
            return None
    
    async def receive_feedback(self) -> Optional[str]:
        """Receive feedback via TCP (compatibility wrapper).
        
        Prefer using read() directly in the feedback listener.
        """
        if not self._connected or not self._reader:
            return None
        
        try:
            data = await asyncio.wait_for(
                self._reader.read(256),
                timeout=self._timeout
            )
            if data:
                feedback = data.decode("latin-1").strip(" \t\r\n")
                _LOGGER.debug(f"Received feedback: {feedback}")
                return feedback
            return None
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout waiting for feedback")
            return None
        except Exception as e:
            _LOGGER.error(f"Failed to receive feedback: {e}")
            return None
