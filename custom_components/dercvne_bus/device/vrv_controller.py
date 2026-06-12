"""VRV Controller (CoolMaster) device class for Dercvne Bus integration.

The CoolMaster VRV controller communicates over the shared RS485 bus
(through the same 网转串 TCP connection that relays/lights use).
Commands are sent via the bus transport's send_command() method.
Status responses (stat2 replies) arrive on the same socket and are
detected by the feedback listener, then routed back to this controller
through the handle_response() callback.

Protocol commands (all terminated with \\r\\n):
    stat2               Query status of all indoor units
    on <UID>            Turn on indoor unit
    off <UID>           Turn off indoor unit
    cool <UID>          Set mode to Cool
    heat <UID>          Set mode to Heat
    dry <UID>           Set mode to Dry
    fan <UID>           Set mode to Fan Only
    fspeed <UID> <l|m|h|a>  Set fan speed (Low/Med/High/Auto)
    temp <UID> <value>  Set temperature setpoint

Status response format (one line per indoor unit, > 15 chars):
    UID State SetTemp RoomTemp ? FanSpeed Mode
"""

import asyncio
import logging
import re

_LOGGER = logging.getLogger(__name__)

# ------------------------------------------------------------------ VRV status line detection


# VRV status lines contain: hexadecimal UID + ON/OFF + more fields
# Example: "100 ON 24 26.0 XX Low Cool" or "100 OFF -- 28.5 XX -- --"
#
# Use search (not match) so VRV lines can be detected even when
# mixed with DALI feedback in the same TCP read buffer, e.g.:
#   *V;@1*S,0,0,1A;100 ON 24 26.0 XX Auto Cool\r\n
_VRV_LINE_PATTERN = re.compile(r"[0-9A-Fa-f]+\s+(ON|OFF)\s+")


def is_vrv_response(data: str) -> bool:
    """Check whether raw socket data contains VRV status lines.

    Uses ``re.search`` so that VRV data mixed with DALI feedback
    (different prefixes in the same TCP read) is still detected.
    """
    return bool(_VRV_LINE_PATTERN.search(data))


def extract_vrv_lines(data: str) -> str:
    """Extract VRV status lines from mixed raw socket data.

    When DALI feedback and CoolMaster responses arrive in the same
    TCP read, this function pulls out only the VRV lines so the
    status parser doesn't choke on the non-VRV prefix.

    Returns the concatenated VRV lines, or empty string if none found.
    """
    vrv_lines = []
    for line in data.splitlines():
        line = line.strip()
        if _VRV_LINE_PATTERN.search(line):
            vrv_lines.append(line)
    return "\n".join(vrv_lines)


# ------------------------------------------------------------------ VRVController


class VRVController:
    """CoolMaster VRV空调控制器协议处理器.

    Shares the bus TCP transport with other device types (relays, lights,
    etc.).  Commands are sent via the transport's send_command() method.
    Status responses from ``stat2`` are detected by the feedback listener
    and delivered via ``handle_response()``.
    """

    def __init__(self, transport):
        """Initialize VRV controller.

        Args:
            transport: A TCPTransport (or compatible) instance that is
                       already connected to the 网转串.
        """
        self._transport = transport
        self._last_response: str = ""          # latest raw stat2 response
        self._response_event = asyncio.Event()  # set when new response arrives

    # ------------------------------------------------------------------ properties

    @property
    def is_connected(self) -> bool:
        """Whether the underlying bus transport is connected."""
        if self._transport is None:
            return False
        return self._transport.is_connected

    # ------------------------------------------------------------------ response handler (called by feedback listener)

    def handle_response(self, raw_text: str):
        """Called by the feedback listener when VRV status data arrives.

        Stores the raw response text and signals any waiting coroutine
        (e.g. query_status) that new data is available.

        Args:
            raw_text: Raw text from the stat2 response.
        """
        self._last_response = raw_text
        self._response_event.set()
        _LOGGER.debug("VRV response received (%d chars)", len(raw_text))

    # ------------------------------------------------------------------ send command

    async def _send_command(self, cmd: str) -> bool:
        """Send a command to the CoolMaster device via the shared transport.

        Args:
            cmd: Command string (without line terminator).  \\r\\n is
                 appended by the transport.

        Returns:
            True if sent successfully.
        """
        if self._transport is None:
            _LOGGER.warning("VRV: no transport, cannot send: %s", cmd)
            return False

        if not self._transport.is_connected:
            _LOGGER.warning("VRV: transport disconnected, cannot send: %s", cmd)
            return False

        # Append \r\n — the CoolMaster line terminator.
        # transport.send_command() writes cmd.encode("ascii") followed by
        # drain(), so we pre-format the command with its own terminator.
        result = await self._transport.send_command(cmd + "\r\n")
        if result:
            _LOGGER.debug("VRV sent: %s", cmd)
        return result

    # ------------------------------------------------------------------ device commands

    async def query_status(self, vrv_id: str) -> str:
        """Send stat2 command and wait for the response.

        The response arrives on the shared bus socket and is routed
        back by the feedback listener via handle_response().

        Args:
            vrv_id: The VRV controller UUID (used to guard against
                    stale responses from a previous poll).

        Returns:
            Raw status text, or empty string on timeout / disconnect.
        """
        if not self.is_connected:
            return ""

        self._response_event.clear()

        sent = await self._transport.send_command("stat2\r\n")
        if not sent:
            return ""

        try:
            await asyncio.wait_for(
                self._response_event.wait(),
                timeout=5,
            )
            return self._last_response
        except asyncio.TimeoutError:
            _LOGGER.debug("VRV status query timeout")
            return ""

    async def turn_on(self, unit_id: str) -> bool:
        """Turn on an indoor unit."""
        return await self._send_command(f"on {unit_id}")

    async def turn_off(self, unit_id: str) -> bool:
        """Turn off an indoor unit."""
        return await self._send_command(f"off {unit_id}")

    async def set_mode_cool(self, unit_id: str) -> bool:
        """Set mode to Cool (制冷)."""
        return await self._send_command(f"cool {unit_id}")

    async def set_mode_heat(self, unit_id: str) -> bool:
        """Set mode to Heat (制热)."""
        return await self._send_command(f"heat {unit_id}")

    async def set_mode_dry(self, unit_id: str) -> bool:
        """Set mode to Dry (除湿)."""
        return await self._send_command(f"dry {unit_id}")

    async def set_mode_fan(self, unit_id: str) -> bool:
        """Set mode to Fan Only (送风)."""
        return await self._send_command(f"fan {unit_id}")

    async def set_fan_speed(self, unit_id: str, speed: str) -> bool:
        """Set fan speed.

        Args:
            unit_id: Indoor unit ID.
            speed: 'l' (low), 'm' (medium), 'h' (high), 'a' (auto).
        """
        return await self._send_command(f"fspeed {unit_id} {speed}")

    async def set_temperature(self, unit_id: str, temp: int) -> bool:
        """Set target temperature.

        Args:
            unit_id: Indoor unit ID.
            temp: Target temperature in Celsius.
        """
        return await self._send_command(f"temp {unit_id} {temp}")


# ------------------------------------------------------------------ status parsing


# Regex: ID ON/OFF SetTemp RoomTemp ? FanSpeed Mode
# Example: "00 ON 24 26.0 XX Low Cool" or "01 OFF -- 28.5 XX -- --"
_STATUS_LINE_RE = re.compile(
    r"^(\S+)\s+(ON|OFF)\s+(\S+)\s+(\S+)\s+\S+\s+(\S+)\s+(\S+)$"
)

# Map protocol fan speed strings to HA fan modes
_FAN_SPEED_MAP = {
    "Low": "low",
    "Med": "medium",
    "High": "high",
    "Auto": "auto",
}

# Map protocol mode strings to HA HVAC modes
_MODE_MAP = {
    "Cool": "cool",
    "Heat": "heat",
    "Dry": "dry",
    "Fan": "fan_only",
}


def parse_status_response(raw_text: str) -> dict[str, dict]:
    """Parse a stat2 response into per-unit status dicts.

    Args:
        raw_text: Raw text response from the VRV controller.

    Returns:
        Dict mapping unit ID to status dict, e.g.:
        {"00": {"state": "ON", "mode": "cool", "set_temp": 24,
                "room_temp": 26.0, "fan_speed": "low"}}
    """
    result: dict[str, dict] = {}

    for line in raw_text.splitlines():
        line = line.strip()
        if len(line) <= 15:
            continue

        # Normalize whitespace
        line = re.sub(r"\s+", " ", line)

        match = _STATUS_LINE_RE.match(line)
        if not match:
            _LOGGER.debug("VRV status line parse failed: %s", line)
            continue

        unit_id = match.group(1)
        state = match.group(2)
        set_temp_str = match.group(3)
        room_temp_str = match.group(4)
        fan_speed_str = match.group(5)
        mode_str = match.group(6)

        status: dict = {}

        if state == "OFF":
            status["state"] = "OFF"
            status["mode"] = "off"
            status["fan_speed"] = "auto"
        else:
            status["state"] = "ON"
            status["mode"] = _MODE_MAP.get(mode_str, "cool")
            status["fan_speed"] = _FAN_SPEED_MAP.get(fan_speed_str, "auto")

            try:
                status["set_temp"] = int(set_temp_str)
            except (ValueError, TypeError):
                status["set_temp"] = None

        try:
            status["room_temp"] = float(room_temp_str)
        except (ValueError, TypeError):
            status["room_temp"] = None

        result[unit_id] = status

    return result


def discover_indoor_units(raw_text: str) -> list[str]:
    """Extract indoor unit IDs from a stat2 response.

    Args:
        raw_text: Raw text response from the VRV controller.

    Returns:
        List of unit ID strings found.
    """
    unit_ids = []
    for line in raw_text.splitlines():
        line = line.strip()
        if len(line) <= 15:
            continue
        # ID is the first field
        fields = line.split()
        if fields:
            unit_ids.append(fields[0])
    return unit_ids
