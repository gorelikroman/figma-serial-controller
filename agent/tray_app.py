#!/usr/bin/env python3
"""
Figma Serial Controller — Menubar App
macOS tray (menubar) с полным управлением агентом.

Иконка в menubar:
  🟢 — Arduino + Plugin подключены
  🟡 — агент работает, что-то не подключено
  🔴 — агент остановлен

Меню:
  • Статус Device / WebSocket / Plugin
  • Open Config Editor (index.html в браузере)
  • Reconnect / Quit
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from collections import defaultdict
from pathlib import Path
from typing import Optional

import rumps
import serial
import serial.tools.list_ports
import websockets

try:
    from websockets.asyncio.server import serve  # websockets >= 14
except ImportError:
    from websockets.server import serve  # websockets < 14

# ─── Paths ───────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    CONFIG_PATH = BUNDLE_DIR / "config.json"
    if not CONFIG_PATH.exists():
        CONFIG_PATH = Path(sys.executable).parent / "config.json"
    # index.html inside bundle
    INDEX_HTML = BUNDLE_DIR / "index.html"
else:
    SCRIPT_DIR = Path(__file__).parent
    CONFIG_PATH = SCRIPT_DIR / "config.json"
    INDEX_HTML = SCRIPT_DIR.parent / "index.html"

# ─── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tray")


# ═══════════════════════════════════════════════════════════════
#  Config
# ═══════════════════════════════════════════════════════════════

def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

CFG: dict = load_config()

WS_HOST = CFG["websocket"]["host"]
WS_PORT = CFG["websocket"]["port"]
SERIAL_BAUD = CFG["serial"]["baud"]
SERIAL_PATTERNS = CFG["serial"]["port_patterns"]

ACCEL_CFG = CFG["acceleration"]
ACCEL_X2 = ACCEL_CFG["thresholds"]["x2"]
ACCEL_X4 = ACCEL_CFG["thresholds"]["x4"]
ACCEL_X6 = ACCEL_CFG["thresholds"]["x6"]
ACCEL_WINDOW = ACCEL_CFG["window_sec"]

BATCH_INTERVAL = 0.033
PLUGIN_OPEN_TIMEOUT = 4.0
RECONNECT_SERIAL = 2.0

PLUGIN_NAME = CFG["plugin"]["name"]
PLUGIN_MENU = CFG["plugin"]["menu_path"]


# ═══════════════════════════════════════════════════════════════
#  Agent State (shared with tray)
# ═══════════════════════════════════════════════════════════════

ws_clients: set = set()
encoder_accum: dict[tuple[str, str], int] = defaultdict(int)
event_buffer: list = []
buffer_start: float = 0
plugin_opening: bool = False
enc_tick_times: dict[str, list[float]] = defaultdict(list)

# Hold layers
active_layer_order: list[str] = []
active_layer_sources: dict[str, set[str]] = defaultdict(set)

# Status for tray
serial_port_name: str = ""
serial_connected: bool = False
agent_running: bool = False


# ═══════════════════════════════════════════════════════════════
#  Config helpers (from agent.py)
# ═══════════════════════════════════════════════════════════════

def get_encoder_cfg(enc_id: str) -> dict:
    return CFG["encoders"].get(enc_id, {})

def get_layer_cfg(layer_name: str) -> dict:
    return CFG.get("layers", {}).get(layer_name, {})

def get_effective_encoder_cfg(enc_id: str) -> dict:
    base_cfg = dict(get_encoder_cfg(enc_id))
    if not base_cfg:
        return {}
    for layer_name in active_layer_order:
        if layer_name not in active_layer_sources:
            continue
        override = get_layer_cfg(layer_name).get("encoders", {}).get(enc_id)
        if isinstance(override, dict):
            base_cfg.update(override)
    return base_cfg

def get_button_cfg(btn_id: str) -> dict:
    return CFG["buttons"].get(btn_id, {"type": "none"})

def get_effective_button_cfg(btn_id: str) -> dict:
    base_cfg = dict(get_button_cfg(btn_id))
    if base_cfg.get("type") == "layer_hold":
        return base_cfg
    for layer_name in active_layer_order:
        if layer_name not in active_layer_sources:
            continue
        override = get_layer_cfg(layer_name).get("buttons", {}).get(btn_id)
        if isinstance(override, dict):
            base_cfg.update(override)
    return base_cfg

def activate_hold_layer(layer_name: str, source: str):
    if not layer_name:
        return
    sources = active_layer_sources[layer_name]
    was_active = bool(sources)
    sources.add(source)
    if not was_active:
        active_layer_order.append(layer_name)
        log.info(f"🟢 LAYER ON: [{layer_name}]")

def deactivate_hold_layer(layer_name: str, source: str):
    if not layer_name:
        return
    sources = active_layer_sources.get(layer_name)
    if not sources:
        return
    sources.discard(source)
    if sources:
        return
    active_layer_sources.pop(layer_name, None)
    if layer_name in active_layer_order:
        active_layer_order.remove(layer_name)
    log.info(f"🔴 LAYER OFF: [{layer_name}]")

def clear_hold_layers():
    active_layer_order.clear()
    active_layer_sources.clear()

def save_config(new_config: dict) -> bool:
    global CFG
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(new_config, f, indent=2)
        CFG = new_config
        log.info("Config saved")
        return True
    except Exception as e:
        log.error(f"Config save failed: {e}")
        return False

def reload_config():
    global CFG
    try:
        CFG = load_config()
        clear_hold_layers()
        log.info("Config reloaded")
    except Exception as e:
        log.error(f"Config reload failed: {e}")


# ═══════════════════════════════════════════════════════════════
#  macOS helpers (from agent.py)
# ═══════════════════════════════════════════════════════════════

def is_figma_frontmost() -> bool:
    try:
        r = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=2,
        )
        return "Figma" in r.stdout.strip()
    except Exception:
        return False

def press_hotkey(keys: list[str]):
    if not is_figma_frontmost():
        log.warning("Figma not frontmost — skipping hotkey")
        return
    modifiers = []
    main_key = None
    for k in keys:
        kl = k.lower()
        if kl in ("ctrl", "control"):
            modifiers.append("control down")
        elif kl in ("option", "alt"):
            modifiers.append("option down")
        elif kl in ("command", "cmd"):
            modifiers.append("command down")
        elif kl in ("shift",):
            modifiers.append("shift down")
        else:
            main_key = k
    if not main_key:
        return
    mod_str = ", ".join(modifiers)
    using = f" using {{{mod_str}}}" if modifiers else ""
    script = f'''
    tell application "System Events"
        tell process "Figma"
            keystroke "{main_key}"{using}
        end tell
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3)
        log.info(f"Hotkey: {'+'.join(keys)}")
    except Exception as e:
        log.error(f"Hotkey failed: {e}")

def _apple_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')

def _run_osascript(script: str, timeout: float = 5.0) -> tuple[bool, str]:
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
        msg = (r.stderr or r.stdout or "").strip()
        return (r.returncode == 0, msg)
    except Exception as e:
        return (False, str(e))

def _build_menu_click_script(parts: list[str]) -> str:
    escaped = [_apple_escape(p) for p in parts if p]
    ref = f'menu item "{escaped[-1]}" of menu 1'
    for parent in reversed(escaped[1:-1]):
        ref += f' of menu item "{parent}" of menu 1'
    ref += f' of menu bar item "{escaped[0]}" of menu bar 1'
    return f'''
    tell application "System Events"
        tell process "Figma"
            click {ref}
        end tell
    end tell
    '''

def _build_first_command_script(menu_bar: str, dev_item: str, plugin_item: str) -> str:
    mb = _apple_escape(menu_bar)
    dev = _apple_escape(dev_item)
    plugin = _apple_escape(plugin_item)
    return f'''
    tell application "System Events"
        tell process "Figma"
            click menu item 1 of menu 1 of menu item "{plugin}" of menu 1 of menu item "{dev}" of menu 1 of menu bar item "{mb}" of menu bar 1
        end tell
    end tell
    '''

def open_plugin_menu() -> bool:
    if not is_figma_frontmost():
        try:
            subprocess.run(["osascript", "-e", 'tell application "Figma" to activate'],
                         capture_output=True, timeout=3)
            time.sleep(0.3)
        except Exception:
            return False

    parts = [p.strip() for p in PLUGIN_MENU.split(">") if p.strip()]
    attempts = []
    if len(parts) >= 2:
        attempts.append(("menu path", _build_menu_click_script(parts)))
    menu_bar = parts[0] if parts else "Plugins"
    dev_item = parts[1] if len(parts) > 1 else "Development"
    plugin_item = parts[2] if len(parts) > 2 else PLUGIN_NAME
    attempts.append(("first command", _build_first_command_script(menu_bar, dev_item, plugin_item)))
    attempts.append(("run last plugin", '''
    tell application "System Events"
        tell process "Figma"
            keystroke "p" using {option down, command down}
        end tell
    end tell
    '''))
    for label, script in attempts:
        ok, msg = _run_osascript(script, timeout=5)
        if ok:
            log.info(f"Opened plugin ({label})")
            return True
    return False


# ═══════════════════════════════════════════════════════════════
#  Acceleration
# ═══════════════════════════════════════════════════════════════

def calc_multiplier(enc_id: str) -> int:
    now = time.time()
    ticks = enc_tick_times[enc_id]
    ticks.append(now)
    cutoff = now - ACCEL_WINDOW
    while ticks and ticks[0] < cutoff:
        ticks.pop(0)
    if len(ticks) >= 2:
        span = ticks[-1] - ticks[0]
        rate = (len(ticks) - 1) / span if span > 0 else 0
    else:
        rate = 0
    if rate >= ACCEL_X6:
        return 6
    elif rate >= ACCEL_X4:
        return 4
    elif rate >= ACCEL_X2:
        return 2
    return 1


# ═══════════════════════════════════════════════════════════════
#  WebSocket
# ═══════════════════════════════════════════════════════════════

async def ws_handler(websocket):
    global plugin_opening
    ws_clients.add(websocket)
    plugin_opening = False
    log.info(f"Plugin connected ({len(ws_clients)} clients)")

    # Flush buffer
    if event_buffer:
        buf_enc: dict[tuple[str, str], int] = defaultdict(int)
        buf_other: list = []
        for evt in event_buffer:
            if evt["t"] == "enc":
                key = (evt["id"], evt.get("action", "unknown"))
                buf_enc[key] += evt["delta"]
            else:
                buf_other.append(evt)
        for (enc_id, action), delta in buf_enc.items():
            if delta != 0:
                await websocket.send(json.dumps({"t": "enc", "id": enc_id, "delta": delta, "action": action}))
        for evt in buf_other:
            await websocket.send(json.dumps(evt))
        event_buffer.clear()

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("t") == "ping":
                    await websocket.send(json.dumps({"t": "pong"}))
                elif data.get("t") == "reload":
                    reload_config()
                    await websocket.send(json.dumps({"t": "config_reloaded"}))
                elif data.get("t") == "get_config":
                    await websocket.send(json.dumps({"t": "config", "config": CFG}))
                elif data.get("t") == "set_config":
                    new_config = data.get("config")
                    if new_config and save_config(new_config):
                        await websocket.send(json.dumps({"t": "config_saved"}))
                    else:
                        await websocket.send(json.dumps({"t": "error", "msg": "Save failed"}))
                elif data.get("t") == "reset_config":
                    reload_config()
                    await websocket.send(json.dumps({"t": "config", "config": CFG}))
            except json.JSONDecodeError:
                pass
    except websockets.ConnectionClosed:
        pass
    finally:
        ws_clients.discard(websocket)
        log.info(f"Plugin disconnected ({len(ws_clients)} clients)")

async def ws_broadcast(msg: dict):
    if not ws_clients:
        return
    data = json.dumps(msg)
    await asyncio.gather(*[c.send(data) for c in ws_clients], return_exceptions=True)

def queue_plugin_event(evt: dict, reason: str):
    global plugin_opening, buffer_start
    now = time.time()
    if plugin_opening and (now - buffer_start) > PLUGIN_OPEN_TIMEOUT:
        event_buffer.clear()
        plugin_opening = False
    if not plugin_opening:
        plugin_opening = True
        buffer_start = now
        log.info(f"No plugin — auto-opening ({reason})...")
        def _open(tag):
            global plugin_opening
            ok = open_plugin_menu()
            if not ok:
                plugin_opening = False
        asyncio.get_event_loop().run_in_executor(None, _open, reason)
    event_buffer.append(evt)


# ═══════════════════════════════════════════════════════════════
#  Event Processing
# ═══════════════════════════════════════════════════════════════

async def handle_line(line: str):
    global plugin_opening, buffer_start
    line = line.strip()
    if not line or line.startswith("READY") or line.startswith("MCP:") or line.startswith("JOY:"):
        return
    log.info(f"Serial: [{line}]")
    if ":" not in line:
        return
    ident, value = line.split(":", 1)

    # Encoder rotation
    if ident.startswith("E") and value in ("+1", "-1"):
        delta = int(value)
        enc_cfg = get_effective_encoder_cfg(ident)
        if not enc_cfg:
            return
        step = enc_cfg.get("step", 1)
        accel = enc_cfg.get("accelerate", True)
        invert = enc_cfg.get("invert", False)
        action = enc_cfg.get("action", "unknown")
        multiplier = calc_multiplier(ident) if accel else 1
        final_delta = delta * step * multiplier
        if invert:
            final_delta = -final_delta
        if ws_clients:
            encoder_accum[(ident, action)] += final_delta
        else:
            queue_plugin_event({"t": "enc", "id": ident, "delta": final_delta, "action": action}, reason="encoder")
        return

    # Button / Joystick / Matrix
    event_is_release = False
    if ident.startswith("E") and value == "sw":
        btn_key = f"{ident}:sw"
    elif ident == "JX":
        btn_key = f"JX:{value}"
    elif ident.startswith("M") and value in ("down", "up"):
        btn_key = ident
        event_is_release = (value == "up")
    else:
        return

    btn_cfg = get_effective_button_cfg(btn_key)
    btn_type = btn_cfg.get("type", "none")

    if btn_type == "layer_hold":
        layer_name = btn_cfg.get("layer", "")
        if event_is_release:
            deactivate_hold_layer(layer_name, btn_key)
        else:
            activate_hold_layer(layer_name, btn_key)
        return

    if event_is_release:
        return
    if btn_type == "none":
        return

    if btn_type == "hotkey":
        keys = btn_cfg.get("keys", [])
        if keys:
            asyncio.get_event_loop().run_in_executor(None, press_hotkey, keys)
        return

    if btn_type == "plugin":
        command = btn_cfg.get("command", "")
        if not command:
            return
        evt = {"t": "cmd", "command": command}
        if ws_clients:
            await ws_broadcast(evt)
        else:
            queue_plugin_event(evt, reason=f"button:{btn_key}")
        return


async def batch_flush_loop():
    while True:
        await asyncio.sleep(BATCH_INTERVAL)
        if not ws_clients or not encoder_accum:
            continue
        for (enc_id, action), delta in list(encoder_accum.items()):
            if delta != 0:
                await ws_broadcast({"t": "enc", "id": enc_id, "delta": delta, "action": action})
        encoder_accum.clear()


# ═══════════════════════════════════════════════════════════════
#  Serial
# ═══════════════════════════════════════════════════════════════

def find_serial_port() -> Optional[str]:
    for p in serial.tools.list_ports.comports():
        for pattern in SERIAL_PATTERNS:
            if pattern in p.device:
                return p.device
    return None

async def serial_task():
    global serial_port_name, serial_connected, plugin_opening
    loop = asyncio.get_event_loop()
    while True:
        port = find_serial_port()
        if not port:
            serial_connected = False
            serial_port_name = ""
            await asyncio.sleep(RECONNECT_SERIAL)
            continue
        log.info(f"Connecting to {port}")
        try:
            ser = serial.Serial(port, SERIAL_BAUD, timeout=0.1)
            serial_port_name = port
            serial_connected = True
            plugin_opening = False
            clear_hold_layers()
            log.info(f"Connected to {port}")
            while True:
                raw = await loop.run_in_executor(None, ser.readline)
                if raw:
                    try:
                        line = raw.decode("utf-8", errors="replace").strip()
                        if line:
                            await handle_line(line)
                    except Exception as e:
                        log.error(f"Parse error: {e}")
        except serial.SerialException as e:
            log.error(f"Serial error: {e}")
        except Exception as e:
            log.error(f"Unexpected: {e}")
        serial_connected = False
        serial_port_name = ""
        await asyncio.sleep(RECONNECT_SERIAL)


# ═══════════════════════════════════════════════════════════════
#  Async Agent Runner
# ═══════════════════════════════════════════════════════════════

_agent_loop: Optional[asyncio.AbstractEventLoop] = None

async def _agent_main():
    global agent_running
    agent_running = True
    log.info("═══ Figma Serial Controller Agent ═══")
    log.info(f"WebSocket: ws://{WS_HOST}:{WS_PORT}")

    ws_server = await serve(ws_handler, WS_HOST, WS_PORT)
    log.info("WebSocket server started")

    asyncio.create_task(batch_flush_loop())
    asyncio.create_task(serial_task())

    await asyncio.Future()  # run forever

def start_agent_thread():
    global _agent_loop
    def run():
        global _agent_loop
        _agent_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_agent_loop)
        try:
            _agent_loop.run_until_complete(_agent_main())
        except Exception as e:
            log.error(f"Agent error: {e}")
        finally:
            global agent_running
            agent_running = False
    t = threading.Thread(target=run, daemon=True, name="agent")
    t.start()


# ═══════════════════════════════════════════════════════════════
#  Menubar App
# ═══════════════════════════════════════════════════════════════

class FigmaSerialApp(rumps.App):
    def __init__(self):
        super().__init__(
            name="Figma Serial",
            title="🟡",
            quit_button=None,
        )

        self.status_device = rumps.MenuItem("⚪ Device: scanning…")
        self.status_ws = rumps.MenuItem("⚪ WebSocket: starting…")
        self.status_plugin = rumps.MenuItem("⚪ Figma Plugin: waiting")

        self.menu = [
            self.status_device,
            self.status_ws,
            self.status_plugin,
            None,
            rumps.MenuItem("⚙️  Open Config Editor", callback=self.open_config),
            rumps.MenuItem("🔄 Reconnect Device", callback=self.do_reconnect),
            None,
            rumps.MenuItem("❌ Quit", callback=self.do_quit),
        ]

    @rumps.timer(2)
    def refresh_status(self, _):
        """Обновляет статусы в меню каждые 2 секунды."""
        # Device
        if serial_connected:
            self.status_device.title = f"🟢 Device: {serial_port_name}"
        else:
            self.status_device.title = "🔴 Device: disconnected"

        # WebSocket
        if agent_running:
            n = len(ws_clients)
            self.status_ws.title = f"🟢 WebSocket: {n} client{'s' if n != 1 else ''}"
        else:
            self.status_ws.title = "🔴 WebSocket: stopped"

        # Figma Plugin
        if len(ws_clients) > 0:
            self.status_plugin.title = "🟢 Figma Plugin: connected"
        else:
            self.status_plugin.title = "⚪ Figma Plugin: waiting"

        # Menubar icon
        if serial_connected and len(ws_clients) > 0:
            self.title = "🟢"
        elif serial_connected or agent_running:
            self.title = "🟡"
        else:
            self.title = "🔴"

    def open_config(self, _):
        """Открывает index.html в браузере."""
        if INDEX_HTML.exists():
            webbrowser.open(f"file://{INDEX_HTML}")
            log.info(f"Opened config: {INDEX_HTML}")
        else:
            rumps.alert(
                title="Config Editor",
                message=f"index.html not found:\n{INDEX_HTML}",
            )

    def do_reconnect(self, _):
        """Уведомление о переподключении (serial_task пересканирует автоматически)."""
        rumps.notification(
            title="Figma Serial Controller",
            subtitle="Reconnecting…",
            message="Scanning for Arduino on USB",
        )

    def do_quit(self, _):
        log.info("Quit requested")
        rumps.quit_application()


# ═══════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    start_agent_thread()
    FigmaSerialApp().run()
