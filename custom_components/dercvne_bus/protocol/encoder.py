"""DALI command encoder for Dercvne Bus integration."""

import logging

from ..const import (
    CMD_ON,
    CMD_OFF,
    CMD_QUERY,
    CMD_ADJUST,
    CMD_DALI_SCENE,
    CMD_DALI_QUERY_BRIGHTNESS,
    CLASS_BRIGHTNESS,
    CLASS_CT,
    CLASS_SATURATION,
    CLASS_COLOR,
    COLOR_TEMP_MIN_K,
    COLOR_TEMP_MAX_K,
    SICOO_AC,
    SICOO_FA,
    SICOO_FH,
    SICOO_CMD_QUERY,
    SICOO_CMD_SET_POWER,
    SICOO_CMD_SET_TEMP,
    SICOO_CMD_SET_MODE,
    SICOO_CMD_SET_FAN,
    SICOO_MODE_COOL,
    SICOO_MODE_HEAT,
    SICOO_MODE_FAN,
    SICOO_MODE_DEHUM,
    SICOO_FAN_LOW,
    SICOO_FAN_MED,
    SICOO_FAN_HIGH,
    SICOO_FAN_TURBO,
)

_LOGGER = logging.getLogger(__name__)

_SICOO_RESP_LEN = 11  # Sicoo response frame length (F1/F2/F3 + 10 bytes)


class DALICommandEncoder:
    """Encode commands for DALI devices."""

    @staticmethod
    def turn_on(group: str, address: str, class_type: int = CLASS_BRIGHTNESS) -> str:
        """Generate turn on command (*S).

        Used for relay devices only.
        Lights and covers use set_brightness / set_position instead.
        """
        cmd = CMD_ON.format(class_=class_type, group=group, address=address)
        _LOGGER.debug("Turn on command: %s", cmd)
        return cmd

    @staticmethod
    def turn_off(group: str, address: str, class_type: int = CLASS_BRIGHTNESS) -> str:
        """Generate turn off command (*C).

        Used for relay devices only.
        Lights and covers use set_brightness / set_position instead.
        """
        cmd = CMD_OFF.format(class_=class_type, group=group, address=address)
        _LOGGER.debug("Turn off command: %s", cmd)
        return cmd

    @staticmethod
    def set_brightness(group: str, address: str, brightness: int) -> str:
        """Generate brightness command (*A,0,G,AA;*Z,0XX;).

        Used for single/CCT lights and covers (position).

        Args:
            brightness: 0-255  (0 = off / fully closed, 255 = 100% / fully open)
        """
        brightness = max(0, min(255, int(brightness)))
        value = format(brightness, '02X')
        cmd = CMD_ADJUST.format(
            class_=CLASS_BRIGHTNESS, group=group, address=address, value=value
        )
        _LOGGER.debug("Set brightness command: %s", cmd)
        return cmd

    @staticmethod
    def set_color_temp_kelvin(
        group: str, address: str, kelvin: int,
        use_class_param: bool = False,
    ) -> str:
        """Generate color temperature command.

        Two protocol variants:
          - Legacy (use_class_param=False, default):
            Uses class=0 with group+1 trick.
            Command: *A,0,G+1,AA;*Z,0XX;
          - DM2 standard (use_class_param=True):
            Uses class=1 (standard Class parameter).
            Command: *A,1,G,AA;*Z,0XX;

        Kelvin → device value mapping (linear):
          2200 K (warmest) → 0x00
          6500 K (coolest) → 0xFF

        Args:
            group:            Brightness group address (hex string, e.g. "0").
            address:           Device address (hex string, e.g. "02").
            kelvin:           Colour temperature in Kelvin (2200–6500).
            use_class_param:   True = DM2 standard (*A,1,...);
                              False = legacy group+1 trick.
        """
        kelvin = max(COLOR_TEMP_MIN_K, min(COLOR_TEMP_MAX_K, int(kelvin)))
        raw = round((kelvin - COLOR_TEMP_MIN_K) / (COLOR_TEMP_MAX_K - COLOR_TEMP_MIN_K) * 255)
        value = format(raw, '02X')

        if use_class_param:
            # DM2 standard: class=1
            cmd = CMD_ADJUST.format(
                class_=CLASS_CT, group=group, address=address, value=value,
            )
            _LOGGER.debug(
                "Set color temp (DM2): %s (%.0f K → 0x%s)",
                cmd, kelvin, value,
            )
        else:
            # Legacy: class=0, group+1
            ct_group = format(int(group, 16) + 1, 'X')
            cmd = CMD_ADJUST.format(
                class_=CLASS_BRIGHTNESS, group=ct_group, address=address, value=value,
            )
            _LOGGER.debug(
                "Set color temp (legacy): %s (%.0f K → 0x%s, group %s→%s)",
                cmd, kelvin, value, group, ct_group,
            )
        return cmd

    # ------------------------------------------------------------------
    # RGBCW / DM2 protocol methods
    # ------------------------------------------------------------------

    @staticmethod
    def set_rgb(group: str, address: str, r: int, g: int, b: int) -> str:
        """Generate RGB color command (Class=4, multi-byte Z).

        Command format:
            *A,4,G,AA;*Z,1RR;*Z,1GG;*Z,1BB;*Z,000;

        Args:
            group:   Group address (hex string, e.g. "0").
            address: Device address (hex string, e.g. "02").
            r:       Red   (0-255).
            g:       Green (0-255).
            b:       Blue  (0-255).

        Returns:
            Full command string with multi-byte Z segments.
        """
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        cmd = (
            f"*A,{CLASS_COLOR},{group},{address};"
            f"*Z,1{r:02X};"
            f"*Z,1{g:02X};"
            f"*Z,1{b:02X};"
            f"*Z,000;"
        )
        _LOGGER.debug("Set RGB command: %s", cmd)
        return cmd

    @staticmethod
    def set_saturation(group: str, address: str, saturation: int) -> str:
        """Generate saturation command (Class=3).

        Saturation definition (from protocol doc):
          0x00 = more CW (warm white added)
          0xFF = pure color (no white mixed)

        Command format:
            *A,3,G,AA;*Z,0SS;

        Args:
            group:       Group address (hex string, e.g. "0").
            address:     Device address (hex string, e.g. "02").
            saturation:  0-255 (0 = warm white mixed in, 255 = pure color).
        """
        saturation = max(0, min(255, int(saturation)))
        value = format(saturation, '02X')
        cmd = CMD_ADJUST.format(
            class_=CLASS_SATURATION, group=group, address=address, value=value,
        )
        _LOGGER.debug("Set saturation command: %s (sat=%d)", cmd, saturation)
        return cmd

    @staticmethod
    def set_color_wheel(group: str, address: str, wheel_value: int) -> str:
        """Generate color wheel command (Class=2).

        Command format:
            *A,2,G,AA;*Z,0WW;

        Args:
            group:        Group address (hex string, e.g. "0").
            address:      Device address (hex string, e.g. "02").
            wheel_value:   0-255 (color wheel position).
        """
        wheel_value = max(0, min(255, int(wheel_value)))
        value = format(wheel_value, '02X')
        cmd = CMD_ADJUST.format(
            class_=2, group=group, address=address, value=value,
        )
        _LOGGER.debug("Set color wheel command: %s", cmd)
        return cmd

    @staticmethod
    def query_current_status(group: str, address: str) -> str:
        """Generate query current status command (*P,F,...).

        Used to query all current status (brightness + color temp + RGB + ...).

        Command format:
            *P,F,G,AA;

        Response contains current brightness/color/status.
        """
        cmd = CMD_QUERY.format(class_='F', group=group, address=address)
        _LOGGER.debug("Query current status: %s", cmd)
        return cmd

    @staticmethod
    def query_status(group: str, address: str, class_type: int = CLASS_BRIGHTNESS) -> str:
        """Generate query status command (*P)."""
        cmd = CMD_QUERY.format(class_=class_type, group=group, address=address)
        _LOGGER.debug("Query command: %s", cmd)
        return cmd

    @staticmethod
    def call_scene(scene_num: int) -> str:
        """Generate *S-format scene call command (legacy).

        This is the old address=0 workaround.  Prefer call_dali_scene()
        for new dali_scene devices.

        Args:
            scene_num: Scene number (0-15)
        """
        cmd = f"*S,0,{scene_num:01X},0;"
        _LOGGER.debug("Call scene command (legacy): %s", cmd)
        return cmd

    @staticmethod
    def call_dali_scene(port: str, group: str, scene: str) -> str:
        """Generate DALI scene call command via >D pass-through.

        Format: >D,{port},E,0,{group},{scene};

        Args:
            port:  DALI bus port (0-3), e.g. "0"
            group: DALI group (00-15 hex), e.g. "01"
            scene: DALI scene number (09-18 hex), e.g. "09" = scene 1

        Returns:
            Command string, e.g. ">D,0,E,0,01,09;"
        """
        cmd = CMD_DALI_SCENE.format(port=port, group=group, scene=scene)
        _LOGGER.debug(
            "DALI scene call: %s  (port=%s, group=%s, scene=%s)",
            cmd, port, group, scene,
        )
        return cmd

    @staticmethod
    def query_dali_brightness(port: str, dali_addr: str) -> str:
        """Generate DALI brightness query command via >D pass-through.

        Format: >D,{port},E,0,{dali_addr},1E;

        Args:
            port:      DALI bus port (0-3), e.g. "0"
            dali_addr: DALI short address (00-3F hex, 0-63 decimal)

        Returns:
            Command string, e.g. ">D,0,E,0,00,1E;"
        """
        cmd = CMD_DALI_QUERY_BRIGHTNESS.format(
            port=port, dali_addr=dali_addr,
        )
        _LOGGER.debug(
            "DALI brightness query: %s  (port=%s, addr=%s)",
            cmd, port, dali_addr,
        )
        return cmd


# ---------------------------------------------------------------------------
# Sicoo protocol encoder — X1-29-S Thermostat Panel
# ---------------------------------------------------------------------------

SICOO_FUNC_MAP = {"ac": SICOO_AC, "fa": SICOO_FA, "fh": SICOO_FH}


class SicooCommandEncoder:
    """Encode Sicoo protocol binary commands for X1-29-S thermostat panel.

    Frame format (7 bytes):
        Byte 0: Function code  (B1=FA, B2=AC, B3=FH)
        Byte 1: Device ID       (0x01–0x40, decimal 1–64)
        Byte 2: Command         (0x01 query, 0x02 power, 0x03 temp, ...)
        Byte 3: Data high
        Byte 4: Data low
        Byte 5: Checksum high   (sum of bytes 0–4, high byte)
        Byte 6: Checksum low    (sum of bytes 0–4, low byte)
    """

    @staticmethod
    def _build_frame(func_byte: int, dev_id: int, cmd: int,
                     data_high: int = 0, data_low: int = 0) -> bytes:
        """Build a 7-byte Sicoo command frame with checksum."""
        total = func_byte + dev_id + cmd + data_high + data_low
        cs_high = (total >> 8) & 0xFF
        cs_low = total & 0xFF
        frame = bytes([func_byte, dev_id, cmd, data_high, data_low, cs_high, cs_low])
        _LOGGER.debug(
            "Sicoo cmd: %s",
            " ".join(f"{b:02X}" for b in frame),
        )
        return frame

    @staticmethod
    def _func_byte(sub: str) -> int:
        """Map sub-function name to Sicoo function byte (B-prefix for commands)."""
        return int(SICOO_FUNC_MAP[sub], 16)

    # --- Power control ---

    @staticmethod
    def set_power(sub: str, dev_id: int, power_on: bool) -> bytes:
        """Send power on/off command.

        Args:
            sub:      Sub-function ("ac", "fa", "fh")
            dev_id:   Device ID (1-64)
            power_on: True = on, False = off
        """
        return SicooCommandEncoder._build_frame(
            SicooCommandEncoder._func_byte(sub),
            dev_id,
            SICOO_CMD_SET_POWER,
            data_high=0,
            data_low=0x01 if power_on else 0x00,
        )

    # --- Mode control (AC only) ---

    _MODE_MAP = {
        "cool": SICOO_MODE_COOL,
        "heat": SICOO_MODE_HEAT,
        "fan_only": SICOO_MODE_FAN,
        "dry": SICOO_MODE_DEHUM,
    }

    @staticmethod
    def set_mode(sub: str, dev_id: int, mode_str: str) -> bytes:
        """Set AC working mode.

        Args:
            sub:      Sub-function ("ac")
            dev_id:   Device ID (1-64)
            mode_str: "cool" / "heat" / "fan_only" / "dry"
        """
        mode_val = SicooCommandEncoder._MODE_MAP.get(mode_str, SICOO_MODE_COOL)
        return SicooCommandEncoder._build_frame(
            SicooCommandEncoder._func_byte(sub),
            dev_id,
            SICOO_CMD_SET_MODE,
            data_high=0,
            data_low=mode_val,
        )

    # --- Temperature control ---

    @staticmethod
    def set_temperature(sub: str, dev_id: int, temp_c: float) -> bytes:
        """Set target temperature.

        Temperature is sent as °C × 10 (e.g. 26°C → 260 = 0x0104).

        Args:
            sub:     Sub-function ("ac" or "fh")
            dev_id:  Device ID (1-64)
            temp_c:  Target temperature in Celsius (17-30)
        """
        temp_raw = int(round(temp_c * 10))
        data_high = (temp_raw >> 8) & 0xFF
        data_low = temp_raw & 0xFF
        return SicooCommandEncoder._build_frame(
            SicooCommandEncoder._func_byte(sub),
            dev_id,
            SICOO_CMD_SET_TEMP,
            data_high=data_high,
            data_low=data_low,
        )

    # --- Fan speed control ---

    _FAN_MAP = {
        "low": SICOO_FAN_LOW,
        "medium": SICOO_FAN_MED,
        "high": SICOO_FAN_HIGH,
        "turbo": SICOO_FAN_TURBO,
    }

    @staticmethod
    def set_fan_speed(sub: str, dev_id: int, speed_str: str) -> bytes:
        """Set fan speed.

        Args:
            sub:       Sub-function ("ac" for AC fan, "fa" for fresh air)
            dev_id:    Device ID (1-64)
            speed_str: "low" / "medium" / "high" / "turbo"
        """
        speed_val = SicooCommandEncoder._FAN_MAP.get(speed_str, SICOO_FAN_LOW)
        return SicooCommandEncoder._build_frame(
            SicooCommandEncoder._func_byte(sub),
            dev_id,
            SICOO_CMD_SET_FAN,
            data_high=0,
            data_low=speed_val,
        )

    # --- Query status ---

    @staticmethod
    def query_status(sub: str, dev_id: int) -> bytes:
        """Query thermostat status.

        Args:
            sub:    Sub-function ("ac", "fa", "fh")
            dev_id: Device ID (1-64)
        """
        return SicooCommandEncoder._build_frame(
            SicooCommandEncoder._func_byte(sub),
            dev_id,
            SICOO_CMD_QUERY,
            data_high=0,
            data_low=0,
        )

    # --- Response parsing ---

    @staticmethod
    def parse_response(data: bytes) -> dict:
        """Parse an 11-byte Sicoo response frame.

        Returns dict: {
            "sub": "ac"|"fa"|"fh",
            "dev_id": int,
            "power": True|False,
            "valve": 0|1|2,       (AC: 0=off/1=cool/2=heat, FH: 0/1)
            "current_temp": float,  (Celsius)
            "target_temp": float,
            "mode": str,            ("cool"|"heat"|"fan_only"|"dry"|"humidity"),
            "fan_speed": str,       ("low"|"medium"|"high"|"turbo")
        }
        """
        if len(data) < _SICOO_RESP_LEN:
            _LOGGER.warning("Sicoo response too short: %d bytes", len(data))
            return None

        func_byte = data[0]
        dev_id = data[1]
        status_byte = data[2]
        cur_temp_high = data[3]
        cur_temp_low = data[4]
        set_temp_high = data[5]
        set_temp_low = data[6]
        mode_byte = data[7]
        fan_byte = data[8]

        # Map function byte to sub-function name
        func_map = {
            0xF1: "fa", 0xF2: "ac", 0xF3: "fh",
            0xB1: "fa", 0xB2: "ac", 0xB3: "fh",
        }
        sub = func_map.get(func_byte, "ac")

        # Parse status byte
        power = bool(status_byte & 0x0F)
        valve_raw = (status_byte & 0xF0) >> 4

        # Valve mapping
        if sub == "ac":
            valve = {0: 0, 1: 1, 2: 2}.get(valve_raw, 0)  # 0=off, 1=cool, 2=heat
        else:
            valve = 1 if valve_raw else 0

        # Temperature
        current_temp = ((cur_temp_high << 8) | cur_temp_low) / 10.0
        target_temp = ((set_temp_high << 8) | set_temp_low) / 10.0

        # Mode
        _MODE_REV = {0: "dry", 1: "cool", 2: "heat", 3: "fan_only"}
        mode_str = _MODE_REV.get(mode_byte, "cool")
        if sub == "fa":
            mode_str = "fan_only"  # Fresh air always reports humidity in mode byte

        # Fan speed
        _FAN_REV = {0: "low", 1: "medium", 2: "high", 3: "turbo"}
        fan_speed = _FAN_REV.get(fan_byte, "low")

        return {
            "sub": sub,
            "dev_id": dev_id,
            "power": power,
            "valve": valve,
            "current_temp": current_temp,
            "target_temp": target_temp,
            "mode": mode_str,
            "fan_speed": fan_speed,
        }
