# Dercvne Bus

将 Dercvne 智能控制器接入 Home Assistant，支持 RS485 串口和 TCP 网络连接方式。

## 功能特性

- ✅ 支持继电器控制（Switch 实体）
- ✅ 支持单色温灯控制（Light 实体 - 亮度调节）
- ✅ 支持双色温灯控制（Light 实体 - 亮度和色温调节）
- ✅ 支持窗帘控制（Cover 实体）
- ✅ 支持 DALI 场景调用（Scene 实体）
- ✅ 支持 VRV 空调内机（Climate 实体 - CoolMaster 协议）
- ✅ 支持温控面板（Climate/Fan 实体 - Sicoo 协议）
- ✅ 支持 485 面板按键触发（Event 实体）
- ✅ 支持 IO 模块输入触发（Event 实体）
- ✅ 支持占用感应器（Binary Sensor 实体）
- ✅ 支持 485 串口和 TCP 网口双连接方式
- ✅ 支持多连接（可同时添加多个串口/TCP 连接）
- ✅ 通过 UI 界面配置设备，无需编辑配置文件

## 安装方法

### 方法 1：HACS 安装（推荐）

> ⚠️ 首次上架需等待 HACS 审核（约 1-7 天）
>
> 审核期间可通过**自定义仓库**方式安装：

1. 在 Home Assistant 中打开 **HACS**
2. 点击右上角三个点 → **Custom repositories**
3. 填写：
   - **Repository URL**: `https://github.com/Benjamin-LY777/dercvne_bus`
   - **Category**: `Integration`
4. 点击 **ADD**
5. 返回 HACS 主页面，搜索 **Dercvne Bus**，点击安装
6. 重启 Home Assistant

### 方法 2：手动安装

1. 下载本仓库 ZIP 文件并解压
2. 将 `custom_components/dercvne_bus` 文件夹复制到 Home Assistant 的 `custom_components` 目录
   - 默认路径：`/usr/share/hassio/homeassistant/custom_components/`
3. 重启 Home Assistant
4. 在集成页面添加 **Dercvne Bus** 集成

## 配置步骤

### 1. 添加集成

1. 进入 **Home Assistant** → **设置** → **设备与服务** → **添加集成**
2. 搜索 **Dercvne Bus**
3. 选择连接方式：
   - **TCP Network**：通过网络连接控制器
   - **Serial (RS485)**：通过 USB 转 485 连接

### 2. 配置连接参数

**TCP 连接：**
- **IP 地址**：控制器的 IP 地址（如 `192.168.31.245`）
- **端口**：默认 `2300`（网转串）或 `502`（Modbus）

**Serial 连接：**
- **串口**：如 `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`（Linux）或 `COM3`（Windows）
- **波特率**：默认 `9600`
- **校验位**：默认 `N`（无校验）
- **数据位**：默认 `8`
- **停止位**：默认 `1`

### 3. 添加设备

按照向导添加设备：

| 设备类型 | 说明 | 所需参数 |
|---------|------|----------|
| 继电器 (Relay) | 开关控制 | Group (0-F), Address (00-FF) |
| 单色温灯 (Light Single) | 亮度调节 | Group (0-F), Address (00-FF) |
| 双色温灯 (Light CCT) | 亮度+色温 | Group (0-F), Address (00-FF) |
| 窗帘 (Cover) | 开/关/停 | Group (0-F), Address (00-FF) |
| DALI 场景 | 场景调用 | Port (0-3), Group (00-15), Scene (1-16) |
| VRV 空调内机 | 温度/模式控制 | UID (如 110) |
| 温控面板 | 温度/模式/风量 | AC 地址, 地暖地址, 新风地址 |
| 485 面板 | 按键触发 | Panel Address (00-FF) |
| IO 模块 | 输入触发 | Module Address (00-FF) |
| 占用感应器 | 有人/无人 | Device Address (自动搜索) |

可重复添加多个设备。

### 4. 接入米家 App（可选）

1. 在 Home Assistant 安装 **Xiaomi Miot Auto** 集成
2. 配置该集成，连接到米家中枢网关
3. Dercvne 设备将自动同步到米家 App
4. 在米家 App 中控制设备

## 协议说明

### 继电器控制

**开：** `*S,0,G,AA;`  
**关：** `*C,0,G,AA;`  
**反馈：** `*V;@1*S,0,0,1A;` / `*V;@1*C,0,0,1A;`

### 灯光控制

**调光：** `*A,0,G,AA;*Z,0XX;`（XX=亮度 00~FF）  
**关灯：** `*A,0,G,AA;*Z,000;`  
**色温：** `*A,0,G+1,AA;*Z,0XX;`（XX=色温原始值）

### VRV 空调（CoolMaster 协议）

通过 RS485/TCP 发送 `stat2` 命令查询状态，解析回码更新 Climate 实体。

## 自动化示例

### 485 面板按键触发灯光

```yaml
automation:
  - alias: "面板按键1开灯"
    trigger:
      - platform: device
        device_id: <面板设备ID>
        domain: dercvne_bus
        type: keypad_button
        subtype: "按钮1"
    action:
      - service: light.turn_on
        target:
          entity_id: light.living_room
```

### VRV 空调温度控制

```yaml
automation:
  - alias: "卧室温度过高开空调"
    trigger:
      - platform: numeric_state
        entity_id: sensor.bedroom_temperature
        above: 28
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.bedroom_ac
        data:
          temperature: 26
      - service: climate.turn_on
        target:
          entity_id: climate.bedroom_ac
```

## 查看日志

在 Home Assistant 配置中启用调试日志：

```yaml
logger:
  logs:
    custom_components.dercvne_bus: debug
```

## 故障排除

### 无法连接控制器

- 检查连接参数是否正确
- Serial 连接：检查串口号和波特率
- TCP 连接：检查 IP 地址和端口，确保网络连通
- 查看 Home Assistant 日志获取详细错误信息

### 设备无响应

- 确认 Group 和 Address 是否正确
- 使用 Dercvne 调试软件验证指令
- 检查总线是否空闲（无持续 FF 字节）

### Serial 连接持续收到 FF

- 可能是 CH340 芯片兼容性问题
- 建议更换为 FT232 芯片的 USB-RS485 适配器
- 或在 HA OS 中添加 udev 规则

## 技术架构

```
米家 App ←→ 米家中枢网关 ←→ HA (Xiaomi Miot Auto)
                                    ↓
                            Dercvne Bus 集成
                                    ↓
                          ┌─────────┴─────────┐
                       RS485 总线      TCP 网络
                          ↓               ↓
                     Dercvne 控制器 ←→ 智能设备
```

## 开发信息

- **通信协议**：Dercvne 私有协议 / CoolMaster 协议 / Sicoo 协议
- **开发语言**：Python 3
- **HA 集成类型**：Custom Integration
- **支持平台**：switch, light, cover, climate, fan, scene, binary_sensor, device_trigger

## 更新日志

### v1.3.1 (2026-06-11)
- 修复 config_flow.py 大规模语法错误
- 修复连接编辑/添加表单类型切换交互
- 修复添加连接持久化问题
- 优化串口 RS485 传输层

### v1.3.0 (2026-06-05)
- 新增 VRV 空调控制器支持
- 新增温控面板支持
- 新增 485 面板按键触发
- 新增 IO 模块输入触发
- 新增占用感应器支持

### v1.2.0 (2026-05-20)
- 新增 DALI 场景支持
- 支持多连接管理
- 优化设备配置流程

### v1.1.0 (2026-05-01)
- 新增双色温灯支持
- 新增窗帘控制支持
- 修复设备反馈解析

### v1.0.0 (2026-04-15)
- 首次发布
- 支持继电器控制
- 支持单色温灯控制
- 支持 RS485 和 TCP 双连接方式

## 支持与反馈

- **GitHub Issues**: [https://github.com/Benjamin-LY777/dercvne_bus/issues](https://github.com/Benjamin-LY777/dercvne_bus/issues)
- **GitHub Discussions**: [https://github.com/Benjamin-LY777/dercvne_bus/discussions](https://github.com/Benjamin-LY777/dercvne_bus/discussions)

## 许可证

MIT License
