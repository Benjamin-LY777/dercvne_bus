"""Constants for Dercvne Bus integration."""

DOMAIN = "dercvne_bus"

# Connection types
CONN_TYPE_SERIAL = "serial"
CONN_TYPE_TCP = "tcp"

# Default values
DEFAULT_PORT = 2300
DEFAULT_BAUDRATE = 9600
DEFAULT_PARITY = "N"
DEFAULT_BYTESIZE = 8
DEFAULT_STOPBITS = 1
DEFAULT_TIMEOUT = 2

# Device types
DEVICE_TYPE_RELAY = "relay"
# DALI module lights (Class=0, CCT uses group+1 trick)
DEVICE_TYPE_LIGHT_SINGLE = "light_single"       # DALI 单色温
DEVICE_TYPE_LIGHT_CCT = "light_cct"              # DALI 双色温
# DM2 dimming host lights (standard Class parameters)
DEVICE_TYPE_DM2_SINGLE = "dm2_single"            # DM2 单色温
DEVICE_TYPE_DM2_CCT = "dm2_cct"                  # DM2 双色温
DEVICE_TYPE_LIGHT_RGBCW = "light_rgbcw"          # DM2 RGBCW
DEVICE_TYPE_SCENE = "scene"
DEVICE_TYPE_DALI_SCENE = "dali_scene"
DEVICE_TYPE_COVER = "cover"
DEVICE_TYPE_KEYPAD = "keypad"
DEVICE_TYPE_OCCUPANCY = "occupancy"
DEVICE_TYPE_IO_MODULE = "io_module"

# IO Module (4-channel dry contact input)
IO_MODULE_CHANNEL_COUNT = 4

# VRV Controller (CoolMaster protocol)
DEVICE_TYPE_VRV_CONTROLLER = "vrv_controller"
DEVICE_TYPE_VRV_INDOOR = "vrv_indoor"
VRV_DEFAULT_PORT = 12345
VRV_POLL_INTERVAL = 5  # seconds
VRV_READ_TIMEOUT = 3   # seconds

# Thermostat panel (X1-29-S) — Sicoo protocol over RS485
DEVICE_TYPE_THERMOSTAT = "thermostat_panel"

# Sicoo protocol function codes (command uses B, response uses F)
SICOO_FA = "B1"   # 新风 Fresh Air
SICOO_AC = "B2"   # 空调 Air Conditioner
SICOO_FH = "B3"   # 地暖 Floor Heating
SICOO_FA_RESP = "F1"
SICOO_AC_RESP = "F2"
SICOO_FH_RESP = "F3"

# Sicoo commands
SICOO_CMD_QUERY = 0x01      # 查询状态
SICOO_CMD_SET_POWER = 0x02  # 设开关
SICOO_CMD_SET_TEMP = 0x03   # 设温度
SICOO_CMD_TEMP_UP = 0x04    # 温度+
SICOO_CMD_TEMP_DOWN = 0x05  # 温度-
SICOO_CMD_SET_MODE = 0x06   # 设工作模式
SICOO_CMD_SET_FAN = 0x07    # 设风量

# Sicoo mode values (AC)
SICOO_MODE_DEHUM = 0x00  # 除湿
SICOO_MODE_COOL = 0x01   # 制冷
SICOO_MODE_HEAT = 0x02   # 制热
SICOO_MODE_FAN = 0x03    # 送风

# Sicoo fan speed values
SICOO_FAN_LOW = 0x00     # 低风
SICOO_FAN_MED = 0x01     # 中风
SICOO_FAN_HIGH = 0x02    # 高风
SICOO_FAN_TURBO = 0x03   # 超高风

# Sicoo address range: 1-64 (0x01-0x40 in hex)
SICOO_ADDR_MIN = 1
SICOO_ADDR_MAX = 64

# Sicoo valve states (upper nibble of status byte 2)
SICOO_VALVE_OFF = 0x00
SICOO_VALVE_COOL = 0x10  # 冷阀开
SICOO_VALVE_HEAT = 0x20  # 热阀开
SICOO_VALVE_FH = 0x10    # 地暖阀开

# Sicoo frame sizes
SICOO_CMD_FRAME_LEN = 7
SICOO_RESP_FRAME_LEN = 11

# Occupancy sensor (SH-808R-S) protocol
SENSOR_MODEL_NAME = "感应器 SH-808R-S"
SENSOR_SEARCH_CMD = bytes([0xFA, 0xD4, 0xC1, 0x00, 0x07, 0x00, 0x01, 0x9C, 0xAF])
# Search response: 17-byte frame, XXYY at bytes 11-12 (0-indexed: 11,12)
SENSOR_SEARCH_RESP_LEN = 17
SENSOR_STATUS_FRAME_LEN = 9
# Status frame: 00 00 00 00 00 XX YY TT SS
# TT = sensor type (0x01 or 0x02), SS = status (0x01=occupied, 0x00=vacant)

# Keypad config
KEYPAD_BUTTON_COUNT = 8
KEYPAD_ACTION_SHORT = "short_press"
KEYPAD_ACTION_LONG = "long_press"

# Group validation: single hex digit 0-F
import re
GROUP_PATTERN = re.compile(r'^[0-9A-Fa-f]$')

# Address validation: two hex digits 00-FF
ADDRESS_PATTERN = re.compile(r'^[0-9A-Fa-f]{2}$')

# DALI Commands
CMD_ON = "*S,{class_},{group},{address};"
CMD_OFF = "*C,{class_},{group},{address};"
CMD_QUERY = "*P,{class_},{group},{address};"
CMD_ADJUST = "*A,{class_},{group},{address};*Z,0{value};"

# Command classes
CLASS_BRIGHTNESS = 0
CLASS_CT = 1
CLASS_SATURATION = 3
CLASS_COLOR = 4

# Color temperature range (Kelvin)
# Maps linearly to device value 0x00 (warmest) – 0xFF (coolest)
COLOR_TEMP_MIN_K = 2200   # warmest (device value 0x00)
COLOR_TEMP_MAX_K = 6500   # coolest (device value 0xFF)

# Feedback identifiers
FEEDBACK_ON = "*S"
FEEDBACK_OFF = "*C"
FEEDBACK_ADJUST = "*A"
FEEDBACK_QUERY = "*P"

# DALI scene commands (direct DALI bus pass-through)
# Format: >D,{port},E,0,{group},{scene};
#   port:  0-3    (4-way DALI bus port)
#   group: 00-15  (DALI group 1-16, displayed as hex 00-15)
#   scene: 09-18  (DALI scene 1-16, 0x09=scene1 ... 0x18=scene16)
CMD_DALI_SCENE = ">D,{port},E,0,{group},{scene};"
# Brightness query: >D,{port},E,0,{dali_addr},1E;
CMD_DALI_QUERY_BRIGHTNESS = ">D,{port},E,0,{dali_addr},1E;"
