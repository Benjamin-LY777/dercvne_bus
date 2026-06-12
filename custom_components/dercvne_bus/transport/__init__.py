"""Transport layer for Dercvne Bus integration."""

from .base import DALITransport
from .serial_transport import SerialTransport
from .tcp_transport import TCPTransport


def create_transport(hass, config):
    """Create transport instance based on config."""
    conn_type = config.get("connection_type")
    
    if conn_type == "serial":
        return SerialTransport(
            port=config.get("serial_port"),
            baud_rate=config.get("baudrate", 9600),
            parity=config.get("parity", "N"),
            byteize=config.get("bytesize", 8),
            stopbits=config.get("stopbits", 1),
            timeout=config.get("timeout", 2)
        )
    elif conn_type == "tcp":
        return TCPTransport(
            host=config.get("tcp_host"),
            port=config.get("tcp_port", 502),
            timeout=config.get("timeout", 2)
        )
    else:
        raise ValueError(f"Unsupported connection type: {conn_type}")
