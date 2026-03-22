# 🎛 Figma Serial Controller

A hardware controller for Figma.
Arduino Micro sends events over USB Serial, the agent processes them (encoder acceleration + button mapping), and forwards them to the Figma plugin over WebSocket.
All mappings are in `config.json` — no reflashing required.

---

## Table of Contents

**Installation:**
- [Option 1 — Recommended (Python + start_agent.command)](#option-1--recommended-python--start_agentcommand)

**Documentation:**
- [Architecture](#architecture)
- [Hardware](#hardware)
- [Serial Protocol](#serial-protocol)
- [Mapping (config.json)](#mapping-configjson)
- [Remapping](#remapping)
- [Troubleshooting](#troubleshooting)
- [Current Status and TODO](#current-status-and-todo)
- [Dependencies](#dependencies)
- [License](#license)

---

# Option 1 — Recommended (Python + start_agent.command)

> Best option when installing from GitHub.
> Controller firmware is already flashed, so Arduino reflashing is not needed.

## What You Need

- macOS 12+
- Arduino Micro connected by USB
- Figma Desktop
- Python 3 (download: [python.org for macOS](https://www.python.org/downloads/macos/))

> VS Code and Copilot are not required to use the controller.

## Step 1: Download the Project

Open [gorelikroman/figma-serial-controller](https://github.com/gorelikroman/figma-serial-controller)
→ **Code → Download ZIP** → extract it.

## Step 2: Install Python 3

You can use either method.

### Method A (GUI, recommended)

1. Open [python.org for macOS](https://www.python.org/downloads/macos/)
2. Download **Python 3.x macOS 64-bit universal2 installer (.pkg)**
3. Run the `.pkg` installer and finish setup
4. If Python is already installed, skip this step

### Method B (Terminal + Homebrew)

```bash
(command -v brew >/dev/null 2>&1 || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)") && ( test -x /opt/homebrew/bin/brew && eval "$(/opt/homebrew/bin/brew shellenv)" || test -x /usr/local/bin/brew && eval "$(/usr/local/bin/brew shellenv)" ) && brew install python && python3 --version
```

This command:
1. Installs Homebrew (if missing)
2. Adds brew to current shell session
3. Installs Python 3
4. Prints Python version

If Terminal asks questions during install, answer as follows:
- `Press RETURN/ENTER to continue` → press `Enter`
- `[sudo] password for ...` → enter your macOS password and press `Enter`
- `Do you want to install the Command Line Tools` → choose `Install`
- `Proceed? [Y/n]` → press `Y` then `Enter`

## Step 3: Install Agent Dependencies

Double-click `install_requirements.command` in the project root.

If macOS blocks `.command`:
- right-click file → **Open** → confirm once

## Step 4: Start the Agent

Double-click `start_agent.command`.

## Step 5: Install and Run the Figma Plugin

1. Open any file in **Figma Desktop**
2. **Plugins → Development → Import plugin from manifest…**
3. Select `plugin/manifest.json`
4. Run **Plugins → Development → Figma Serial Controller → 🎛 Serial Controller**
5. Plugin window should show **Connected ✓**

## What Security/IT Approval May Ask For

- Access to USB serial device (`/dev/cu.usbmodem*`)
- Local loopback WebSocket (`ws://127.0.0.1:8765`)
- macOS permissions for Terminal/iTerm:
  - **Privacy & Security → Accessibility**
  - **Privacy & Security → Automation** (Terminal/iTerm → Figma)

---

# Documentation

## Architecture

```
┌─────────────────────┐    USB Serial    ┌────────────────┐   WebSocket    ┌────────────────┐
│   Arduino Micro     │  ─────────────►  │  Menubar App   │  ──────────►  │  Figma Plugin  │
│   (ATmega32U4)      │   115200 baud    │  tray_app.py   │  ws://        │   code.js      │
│                     │   "E1:+1\n"      │   config.json  │  127.0.0.1    │                │
│  MCP23017 (I2C)     │   "M3:down\n"    │                │  :8765        │                │
│  6 encoders         │   "JX:tl\n"      │  + AppleScript │               │                │
│  4×4 matrix         │                  │    hotkeys     │               │                │
│  joystick           │                  │  + acceleration│               │                │
└─────────────────────┘                  └────────────────┘               └────────────────┘
```

### Data Flow

1. **Arduino** reads encoders/buttons/joystick and sends text events over Serial
2. **Agent** reads Serial, applies acceleration, maps events from config.json
3. **Encoders** → WebSocket → Plugin (smooth property changes, ~30fps batching)
4. **Buttons** → plugin commands or AppleScript hotkeys (macOS)
5. **Plugin** receives JSON and updates selected nodes in Figma

---

## Hardware

### Microcontroller

- **Arduino Micro** (ATmega32U4, native USB)
- Pure Serial mode, no HID keyboard emulation

### I/O Expander

- **MCP23017** on I2C (address `0x20`)
- SDA = **D2**, SCL = **D3** (fixed on ATmega32U4)
- All 16 pins (Port A + Port B) as INPUT_PULLUP

### Encoders (6x rotary encoders with push)

| # | CLK | DT | SW | Connection |
|---|-----|----|----|------------|
| E1 | MCP A0 | MCP A1 | MCP A2 | MCP23017 |
| E2 | MCP A3 | MCP A4 | MCP A5 | MCP23017 |
| E3 | MCP A6 | MCP A7 | MCP B0 | MCP23017 |
| E4 | MCP B1 | MCP B2 | MCP B3 | MCP23017 |
| E5 | MCP B4 | MCP B5 | MCP B6 | MCP23017 |
| E6 | **MCU D4** | **MCU D5** | MCP B7 | MCU + MCP |

> E6 uses direct MCU pins for CLK/DT because MCP23017 pins are fully occupied.

### Joystick (analog, 2 axes + switch)

| Signal | Arduino Pin |
|--------|-------------|
| VRX | **A3** |
| VRY | **A2** |
| SW  | **A1** |
| VCC | 5V |
| GND | GND |

### 4×4 Button Matrix

| | Col 0 (D6) | Col 1 (D7) | Col 2 (D8) | Col 3 (D9) |
|---|---|---|---|---|
| Row 0 (D15) | M1 | M2 | M3 | M4 |
| Row 1 (D14) | M5 | M6 | M7 | M8 |
| Row 2 (D16) | M9 | M10 | M11 | M12 |
| Row 3 (D10) | M13 | M14 | M15 | M16 |

### MCP23017 Wiring

| MCP Pin | Connect To |
|---------|------------|
| VDD (pin 9) | 5V |
| VSS (pin 10) | GND |
| SDA (pin 13) | Arduino D2 |
| SCL (pin 12) | Arduino D3 |
| A0, A1, A2 (pins 15-17) | GND (address 0x20) |
| RESET (pin 18) | 5V (via 10k resistor or direct) |

> Required: 0.1µF capacitor between VDD and GND near MCP chip.
> Recommended: 4.7k pull-ups on SDA/SCL to 5V for longer I2C wires.

---

## Project Structure

```text
figma_serial_controller/
├── README.md                    <- this file
├── CHANGELOG.md                 <- version history
├── LAUNCHER_README.md           <- quick launch guide
├── figma_serial_controller.ino  <- Arduino firmware
├── build_combo_app.sh           <- standalone app build script
├── setup.command                <- install deps + build app in one command
├── start_agent.command          <- double-click agent start
├── install_requirements.command <- double-click dependency install
├── install_autostart.sh         <- launch-at-login setup
├── index.html                   <- visual config editor
├── agent/
│   ├── tray_app.py              <- menubar app (main)
│   ├── agent.py                 <- headless agent
│   ├── config.json              <- all mappings
│   └── requirements.txt         <- pyserial, websockets
└── plugin/
    ├── code.js                  <- Figma plugin
    └── manifest.json            <- plugin manifest (id: figma-serial-controller-2026)
```

---

## Serial Protocol

Firmware sends text lines with `\n` at **115200 baud**:

| Event | Format | Example |
|------|--------|---------|
| Encoder CW | `E{n}:+1` | `E1:+1` |
| Encoder CCW | `E{n}:-1` | `E3:-1` |
| Encoder switch | `E{n}:sw` | `E2:sw` |
| Joystick direction | `JX:{dir}` | `JX:tl` |
| Joystick button | `JX:sw` | `JX:sw` |
| Matrix press | `M{n}:down` | `M5:down` |
| Matrix release | `M{n}:up` | `M5:up` |
| Init | `READY` | once on startup |
| MCP status | `MCP:OK` / `MCP:FAIL` | |
| Joystick status | `JOY:OK` / `JOY:FAIL` | |

Joystick zones (9 directions): `tl` `tc` `tr` `cl` `cr` `bl` `bc` `br` + `sw`.

---

## Mapping (config.json)

### Encoders → WebSocket → Plugin (with acceleration)

Agent calculates rotation speed and applies multipliers:
- < 4 ticks/sec → ×1
- 4-8 ticks/sec → ×2
- 8-14 ticks/sec → ×4
- > 14 ticks/sec → ×6

| Encoder | Action | Base Step | Fast Rotation |
|---------|--------|-----------|---------------|
| E1 | Gap (itemSpacing) | ±1 | ±6 |
| E2 | Padding Horizontal | ±1 | ±6 |
| E3 | Padding Vertical | ±1 | ±6 |
| E4 | Width | ±2 | ±12 |
| E5 | Height | ±2 | ±12 |
| E6 | Font Size | ±2 | ±12 |

### Encoder push buttons → exact value input dialogs

| Button | Action |
|--------|--------|
| E1 sw | Open Gap input |
| E2 sw | Open Padding H input |
| E3 sw | Open Padding V input |
| E4 sw | Open Width input |
| E5 sw | Open Height input |
| E6 sw | Open Font Size input |

### Joystick → Auto Layout Alignment

```
   ↖ tl    ⬆ tc    ↗ tr
   ⬅ cl    🔘 sw    ➡ cr
   ↙ bl    ⬇ bc    ↘ br
```

### 4×4 Matrix → Commands/Hotkeys

| Button | Action | Type |
|--------|--------|------|
| M1 | Set Padding All (dialog) | plugin |
| M2 | Auto Gap (SPACE_BETWEEN) | plugin |
| M3 | Toggle Auto Layout Direction | plugin |
| M4 | Wrap in Auto Layout | plugin |
| M5 | Hug Width | plugin |
| M6 | Fill Width | plugin |
| M7 | Hug Height | plugin |
| M8 | Fill Height | plugin |
| M9 | ⌥⌘B (Detach Instance) | hotkey |
| M10 | ⌥⌘K (Create Component) | hotkey |
| M11 | Create Multiple Components | plugin |
| M12 | ⌃⌥⌘K (Create Component Set) | hotkey |
| M13 | Hold layer `encoder_alt` (while held) | layer_hold |
| M14 | Align Left Text | plugin |
| M15 | Align Center Text | plugin |
| M16 | Split Text Lines | plugin |

### Hold Layer (while button is pressed)

- On `M13:down`, layer `encoder_alt` is activated
- While active, `E6` switches from `fontSize` to `cornerRadius`
- On `M13:up`, layer is deactivated and `E6` returns to `fontSize`

---

## Remapping

Edit `agent/config.json` and restart the agent (`Ctrl+C` → `python3 tray_app.py`).
No Arduino reflashing needed.

You can also use menubar option:
- ⚙️ Open Config Editor

### Change encoder action

```json
"E4": { "action": "cornerRadius", "step": 1, "accelerate": true }
```

### Change matrix button to hotkey

```json
"M16": { "type": "hotkey", "keys": ["command", "z"] }
```

### Change button to plugin command

```json
"M16": { "type": "plugin", "command": "toggleDirection" }
```

### Make matrix button a hold layer

```json
"M13": { "type": "layer_hold", "layer": "encoder_alt" }
```

### Override encoder only inside layer

```json
"layers": {
  "encoder_alt": {
    "encoders": {
      "E6": { "action": "cornerRadius", "step": 1, "accelerate": true }
    }
  }
}
```

### Disable a button

```json
"M16": { "type": "none" }
```

### Available encoder actions

`gap`, `paddingX`, `paddingY`, `width`, `height`, `fontSize`, `opacity`, `cornerRadius`, `strokeWidth`

### Available plugin commands (`type: "plugin"`)

| Command | Description |
|---------|-------------|
| `toggleDirection` | Toggle H↔V |
| `hugContentWidth` / `hugContentHeight` | Hug axis |
| `fillContentWidth` / `fillContentHeight` | Fill axis |
| `fixedWidth` / `fixedHeight` | Fixed axis |
| `gapAuto` | Gap = Auto (SPACE_BETWEEN) |
| `wrapEachInAutoLayout` | Wrap each node in Auto Layout |
| `alignTopLeft`...`alignBottomRight` | 9 alignment variants |
| `alignHorizontalCenter` / `alignVerticalCenter` | Align by axis |
| `createMultipleComponents` | Create components from selection |
| `createComponentSet` | Combine components into set |
| `splitTextLines` | Split text into lines |
| `alignCenterText` / `alignLeftText` | Text alignment |
| `toggleTextResizing` | Auto text resize |
| `openPadXInput`...`openFontSizeInput` | Value input dialogs |

### Hotkey modifiers

`ctrl` / `control`, `option` / `alt`, `command` / `cmd`, `shift` + any key

### Button types (`buttons.Mx.type`)

`plugin`, `hotkey`, `layer_hold`, `none`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Cannot verify developer" | Right click app → **Open** → **Open** (once) |
| `.command` blocked by Apple | `xattr -dr com.apple.quarantine .` in project folder |
| Permission denied | `chmod +x *.command *.sh` |
| Arduino not found | Reconnect USB, check `arduino-cli board list` |
| Serial port busy | `lsof /dev/cu.usbmodem*` then `kill -9 <PID>` |
| Agent does not see Arduino | Ensure no `screen`/IDE Serial Monitor, check `port_patterns` in config |
| Plugin stuck on "Connecting..." | Ensure agent is running and port 8765 is free |
| Plugin does not react | Select a node in Figma; gap/padding require Auto Layout |
| Encoders affect wrong property | Remove old plugin and re-import `manifest.json` |
| Hotkeys do not work | System Settings → Privacy → Accessibility → add Terminal/iTerm |

---

## Current Status and TODO

### ✅ Done

- [x] Arduino firmware builds and runs (31% Flash, 20% RAM)
- [x] Serial protocol verified, events are stable
- [x] Python agent as Serial → WebSocket bridge
- [x] Encoder acceleration ×1/×2/×4/×6
- [x] ~30fps batching of encoder ticks
- [x] `config.json` with full mapping set
- [x] Figma plugin with WebSocket UI and commands
- [x] Standalone macOS app with menubar status
- [x] Visual config editor

### ⏳ TODO

- [ ] End-to-end test of full pipeline
- [ ] Validate all matrix buttons
- [ ] Verify joystick alignment mapping
- [ ] Test hotkey buttons (M9, M10, M12)
- [ ] Improve in-plugin visual feedback
- [ ] Hot-reload `config.json` without restart
- [ ] Support second MCP23017 (`0x21`)
- [ ] Windows/Linux compatibility

---

## Dependencies

| Component | Version |
|-----------|---------|
| Arduino Micro | ATmega32U4 (`arduino:avr:micro`) |
| Python | 3.9+ |
| pyserial | ≥ 3.5 |
| websockets | ≥ 12.0 |
| rumps | ≥ 0.4.0 |
| Figma | Desktop app (not browser) |
| macOS | 12+ (for AppleScript hotkeys) |

---

## License

Internal project. Free for internal use.
