#!/usr/bin/env python3
"""
Figma Serial Controller — Agent
USB Serial → WebSocket bridge + AppleScript hotkeys.

Reads raw events from Arduino Micro over Serial,
dispatches encoder events (with acceleration) to Figma plugin via WebSocket,
and button/joystick events either to plugin or as macOS hotkeys.

Config lives in config.json — change mappings without reflashing.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

import serial
import serial.tools.list_ports
import websockets
from websockets.server import serve

# ─── Load Config ───
SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.json"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

CFG = load_config()

# ─── Settings from config ───
WS_HOST = CFG["websocket"]["host"]
WS_PORT = CFG["websocket"]["port"]
SERIAL_BAUD = CFG["serial"]["baud"]
SERIAL_PATTERNS = CFG["serial"]["port_patterns"]

ACCEL_CFG = CFG["acceleration"]
ACCEL_X2 = ACCEL_CFG["thresholds"]["x2"]
ACCEL_X4 = ACCEL_CFG["thresholds"]["x4"]
ACCEL_X6 = ACCEL_CFG["thresholds"]["x6"]
ACCEL_WINDOW = ACCEL_CFG["window_sec"]

BATCH_INTERVAL = 0.033       # ~30fps
PLUGIN_OPEN_TIMEOUT = 4.0    # wait up to 4s for plugin after auto-open
RECONNECT_SERIAL = 2.0       # retry serial every 2s

PLUGIN_NAME = CFG["plugin"]["name"]
PLUGIN_MENU = CFG["plugin"]["menu_path"]

# ─── Logging ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("agent")

# ─── Global State ───
ws_clients: set = set()
encoder_accum: dict[tuple[str, str], int] = defaultdict(int)
event_buffer: list = []
buffer_start: float = 0
plugin_opening: bool = False


# Acceleration tick tracking
enc_tick_times: dict[str, list[float]] = defaultdict(list)

# Hold-layer state (activated by matrix button down/up)
active_layer_order: list[str] = []
active_layer_sources: dict[str, set[str]] = defaultdict(set)


# ═══════════════════════════════════════════════════════════════
#  Config helpers
# ═══════════════════════════════════════════════════════════════

def get_encoder_cfg(enc_id: str) -> dict:
    return CFG["encoders"].get(enc_id, {})

def get_layer_cfg(layer_name: str) -> dict:
    return CFG.get("layers", {}).get(layer_name, {})

def get_effective_encoder_cfg(enc_id: str) -> dict:
    """Resolve encoder config with all active hold-layers applied."""
    base_cfg = dict(get_encoder_cfg(enc_id))
    if not base_cfg:
        return {}

    for layer_name in active_layer_order:
        if layer_name not in active_layer_sources:
            continue
        override = get_layer_cfg(layer_name).get("encoders", {}).get(enc_id)
        if isinstance(override, dict):
            base_cfg.update(override)
            log.info(f"  🎛 Layer override: {enc_id} via [{layer_name}] → action={base_cfg.get('action')}")

    return base_cfg

def get_button_cfg(btn_id: str) -> dict:
    return CFG["buttons"].get(btn_id, {"type": "none"})

def get_effective_button_cfg(btn_id: str) -> dict:
    """Resolve button config with active hold-layers applied.

    Base layer_hold mapping is never overridden to guarantee proper on/off
    handling on down/up events.
    """
    base_cfg = dict(get_button_cfg(btn_id))
    if base_cfg.get("type") == "layer_hold":
        return base_cfg

    for layer_name in active_layer_order:
        if layer_name not in active_layer_sources:
            continue
        layer_btns = get_layer_cfg(layer_name).get("buttons", {})
        override = layer_btns.get(btn_id)
        if isinstance(override, dict):
            base_cfg.update(override)
            log.info(f"  🎛 Layer override: {btn_id} via [{layer_name}] → type={base_cfg.get('type')}")

    return base_cfg

def activate_hold_layer(layer_name: str, source: str):
    if not layer_name:
        return
    sources = active_layer_sources[layer_name]
    was_active = bool(sources)
    sources.add(source)
    if not was_active:
        active_layer_order.append(layer_name)
        log.info(f"🟢 LAYER ON:  [{layer_name}] (from {source})")
        # Show what's overridden
        layer_enc = get_layer_cfg(layer_name).get("encoders", {})
        for eid, ecfg in layer_enc.items():
            log.info(f"   {eid}: {get_encoder_cfg(eid).get('action','?')} → {ecfg.get('action','?')}")

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
    log.info(f"🔴 LAYER OFF: [{layer_name}] (from {source})")

def clear_hold_layers():
    active_layer_order.clear()
    active_layer_sources.clear()

def save_config(new_config: dict):
    """Save config to disk."""
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
    """Hot-reload config.json."""
    global CFG
    try:
        CFG = load_config()
        clear_hold_layers()
        log.info("Config reloaded")
    except Exception as e:
        log.error(f"Config reload failed: {e}")


# ═══════════════════════════════════════════════════════════════
#  macOS Helpers
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
    """Press a hotkey combo via AppleScript. keys = ['ctrl','option','command','k']."""
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
        log.error(f"No main key in hotkey: {keys}")
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
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
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


def _build_run_last_plugin_script() -> str:
    return '''
    tell application "System Events"
        tell process "Figma"
            keystroke "p" using {option down, command down}
        end tell
    end tell
    '''


def open_plugin_menu():
    """Open the Figma plugin via menu navigation with fallbacks."""
    # First, activate Figma if not frontmost
    if not is_figma_frontmost():
        log.info("Activating Figma...")
        try:
            subprocess.run(["osascript", "-e", 'tell application "Figma" to activate'],
                         capture_output=True, timeout=3)
            time.sleep(0.3)  # Wait for activation
        except Exception as e:
            log.error(f"Failed to activate Figma: {e}")
            return False

    # Parse menu path like "Plugins > Development > Figma Serial Controller > 🎛 Serial Controller"
    parts = [p.strip() for p in PLUGIN_MENU.split(">") if p.strip()]
    attempts: list[tuple[str, str]] = []

    if len(parts) >= 2:
        attempts.append(("configured menu path", _build_menu_click_script(parts)))

    # Fallback for environments where emoji title in menu item is unavailable.
    if parts:
        last_ascii = parts[-1].encode("ascii", "ignore").decode().strip()
        if last_ascii and last_ascii != parts[-1]:
            alt = parts.copy()
            alt[-1] = last_ascii
            attempts.append(("menu path without emoji", _build_menu_click_script(alt)))

    menu_bar = parts[0] if len(parts) > 0 else "Plugins"
    dev_item = parts[1] if len(parts) > 1 else "Development"
    plugin_item = parts[2] if len(parts) > 2 else PLUGIN_NAME

    # Open first command inside plugin submenu regardless of command title.
    attempts.append((
        "first command in configured submenu",
        _build_first_command_script(menu_bar, dev_item, plugin_item),
    ))

    # Language-independent fallback in many Figma setups.
    attempts.append(("run last plugin shortcut", _build_run_last_plugin_script()))

    for label, script in attempts:
        ok, msg = _run_osascript(script, timeout=5)
        if ok:
            log.info(f"Opened plugin ({label})")
            return True
        if msg:
            log.warning(f"Open attempt failed ({label}): {msg}")

    return False


# ═══════════════════════════════════════════════════════════════
#  WebSocket Server
# ═══════════════════════════════════════════════════════════════

async def ws_handler(websocket):
    global plugin_opening
    ws_clients.add(websocket)
    plugin_opening = False
    log.info(f"Plugin connected (clients: {len(ws_clients)})")

    # Flush buffered events
    if event_buffer:
        log.info(f"Flushing {len(event_buffer)} buffered events")
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
                await websocket.send(json.dumps({
                    "t": "enc",
                    "id": enc_id,
                    "delta": delta,
                    "action": action
                }))
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
                    # Just reload from disk (assumes user has backup)
                    reload_config()
                    await websocket.send(json.dumps({"t": "config", "config": CFG}))
                else:
                    log.debug(f"Plugin: {data}")
            except json.JSONDecodeError:
                pass
    except websockets.ConnectionClosed:
        pass
    finally:
        ws_clients.discard(websocket)
        log.info(f"Plugin disconnected (clients: {len(ws_clients)})")


async def ws_broadcast(msg: dict):
    if not ws_clients:
        return
    data = json.dumps(msg)
    await asyncio.gather(
        *[c.send(data) for c in ws_clients],
        return_exceptions=True,
    )


def queue_plugin_event(evt: dict, reason: str):
    """Buffer plugin event and ensure auto-open attempt is active.

    If previous auto-open attempt has timed out, clear stale state and retry
    immediately on the current event.
    """
    global plugin_opening, buffer_start

    now = time.time()
    if plugin_opening and (now - buffer_start) > PLUGIN_OPEN_TIMEOUT:
        log.warning("Auto-open timeout — retrying plugin launch")
        event_buffer.clear()
        plugin_opening = False

    if not plugin_opening:
        plugin_opening = True
        buffer_start = now
        log.info(f"No plugin — auto-opening ({reason})...")

        def _open_with_retry_reset(tag: str):
            global plugin_opening
            ok = open_plugin_menu()
            if not ok:
                plugin_opening = False
                log.warning(f"Auto-open failed ({tag}) — will retry on next event")

        asyncio.get_event_loop().run_in_executor(None, _open_with_retry_reset, reason)

    event_buffer.append(evt)


# ═══════════════════════════════════════════════════════════════
#  Acceleration
# ═══════════════════════════════════════════════════════════════

def calc_multiplier(enc_id: str) -> int:
    now = time.time()
    ticks = enc_tick_times[enc_id]
    ticks.append(now)
    # Trim window
    cutoff = now - ACCEL_WINDOW
    while ticks and ticks[0] < cutoff:
        ticks.pop(0)
    # Tick rate
    if len(ticks) >= 2:
        span = ticks[-1] - ticks[0]
        rate = (len(ticks) - 1) / span if span > 0 else 0
    else:
        rate = 0
    # Multiplier
    if rate >= ACCEL_X6:
        return 6
    elif rate >= ACCEL_X4:
        return 4
    elif rate >= ACCEL_X2:
        return 2
    return 1


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

    # ── Encoder rotation ──
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

        if multiplier > 1:
            log.info(f"  ⚡ {ident}: ×{multiplier} → {final_delta:+d}")

        if ws_clients:
            encoder_accum[(ident, action)] += final_delta
        else:
            queue_plugin_event({
                "t": "enc",
                "id": ident,
                "delta": final_delta,
                "action": action,
            }, reason="encoder")
        return

    # ── Encoder SW / Joystick / Matrix ──
    # Build button key for config lookup
    event_is_release = False
    if ident.startswith("E") and value == "sw":
        btn_key = f"{ident}:sw"
    elif ident == "JX":
        btn_key = f"JX:{value}"
    elif ident.startswith("M") and value in ("down", "up"):
        btn_key = ident
        event_is_release = (value == "up")
    else:
        log.debug(f"Unknown event: {line}")
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

    # Only hold-layer uses release events. Other bindings trigger on press.
    if event_is_release:
        return

    if btn_type == "none":
        log.debug(f"Button {btn_key} not mapped")
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
    """Flush accumulated encoder deltas at ~30fps."""
    while True:
        await asyncio.sleep(BATCH_INTERVAL)
        if not ws_clients or not encoder_accum:
            continue
        for (enc_id, action), delta in list(encoder_accum.items()):
            if delta != 0:
                msg = {"t": "enc", "id": enc_id, "delta": delta, "action": action}
                log.info(f"→ Plugin: {enc_id} {action} delta={delta:+d}")
                await ws_broadcast(msg)
        encoder_accum.clear()


# ═══════════════════════════════════════════════════════════════
#  Serial Reader
# ═══════════════════════════════════════════════════════════════

def find_serial_port() -> Optional[str]:
    """Find Arduino Micro serial port by pattern."""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        for pattern in SERIAL_PATTERNS:
            if pattern in p.device:
                return p.device
    return None


async def serial_task():
    """Read serial lines from Arduino and process events."""
    global plugin_opening
    loop = asyncio.get_event_loop()

    while True:
        port = find_serial_port()
        if not port:
            log.info("Arduino not found, scanning...")
            await asyncio.sleep(RECONNECT_SERIAL)
            continue

        log.info(f"Connecting to {port} @ {SERIAL_BAUD}")
        try:
            ser = serial.Serial(port, SERIAL_BAUD, timeout=0.1)
            log.info(f"Connected to {port}")
            plugin_opening = False
            clear_hold_layers()

            while True:
                # Read in executor to not block event loop
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

        await asyncio.sleep(RECONNECT_SERIAL)


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════

async def main():
    log.info("═══ Figma Serial Controller Agent ═══")
    log.info(f"Config: {CONFIG_PATH}")
    log.info(f"WebSocket: ws://{WS_HOST}:{WS_PORT}")
    log.info(f"Serial patterns: {SERIAL_PATTERNS}")
    log.info(f"Plugin: {PLUGIN_NAME}")
    log.info("")

    # Encoders summary
    for eid, ecfg in CFG["encoders"].items():
        log.info(f"  {eid}: {ecfg['action']} (step={ecfg['step']}, accel={ecfg['accelerate']})")
    log.info("")

    # Buttons summary
    btn_count = sum(1 for b in CFG["buttons"].values() if b.get("type") != "none")
    log.info(f"  Buttons mapped: {btn_count}")
    layer_count = len(CFG.get("layers", {}))
    if layer_count:
        log.info(f"  Hold layers available: {layer_count}")
        for lname, lcfg in CFG.get("layers", {}).items():
            enc_n = len(lcfg.get("encoders", {})) if isinstance(lcfg, dict) else 0
            btn_n = len(lcfg.get("buttons", {})) if isinstance(lcfg, dict) else 0
            log.info(f"    [{lname}] encoders={enc_n}, buttons={btn_n}")
    log.info("")

    ws_server = await serve(ws_handler, WS_HOST, WS_PORT)
    log.info(f"WebSocket server started")

    asyncio.create_task(batch_flush_loop())
    asyncio.create_task(serial_task())

    await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Agent stopped")
