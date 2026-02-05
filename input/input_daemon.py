#!/usr/bin/env python3
import json
import os
import sys
import time

BASE_DIR = os.path.join(os.path.expanduser("~"), "streamer")
sys.path.append(os.path.join(BASE_DIR, "hardware"))
STATE_PATH = os.path.join(BASE_DIR, "oled", "input_state.json")
CONFIG_PATH = os.path.join(BASE_DIR, "oled", "config.json")

from buttons import Buttons
from mpd import MPDClient


def deep_merge(base, override):
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = deep_merge(base[key], value)
        else:
            merged[key] = value
    return merged


def load_state():
    defaults = {
        "last_activity": time.time(),
        "mode": "volume",
        "menu_index": 0,
        "setting_index": 0
    }
    try:
        with open(STATE_PATH, "r") as f:
            data = json.load(f)
            return deep_merge(defaults, data)
    except Exception:
        return defaults


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f)


def load_config():
    defaults = {
        "oled": {
            "brightness_active": 50,
            "brightness_dim": 10,
            "dim_timeout": 10,
            "off_timeout": 30
        },
        "mpd": {
            "host": "localhost",
            "port": 6600,
            "timeout": 2
        }
    }
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
            return deep_merge(defaults, data)
    except Exception:
        return defaults


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def with_mpd(action, cfg):
    client = MPDClient()
    client.timeout = cfg["mpd"].get("timeout", 2)
    client.idletimeout = None
    try:
        client.connect(cfg["mpd"]["host"], cfg["mpd"]["port"])
        action(client)
    except Exception:
        pass
    finally:
        try:
            client.close()
            client.disconnect()
        except Exception:
            pass


def main():
    print("[input_daemon] start")
    state = load_state()
    cfg = load_config()

    # Callbacki — na razie tylko logi
    def on_rotate(direction):
        nonlocal state, cfg
        state["last_activity"] = time.time()
        if state.get("mode") == "volume":
            step = 2 * direction
            def _set_vol(client):
                status = client.status()
                current = int(status.get("volume", "0"))
                new_vol = max(0, min(100, current + step))
                client.setvol(new_vol)
            with_mpd(_set_vol, cfg)
        elif state.get("mode") == "menu":
            state["menu_index"] = (state.get("menu_index", 0) + direction) % 3
        elif state.get("mode") == "settings":
            settings = ["brightness_active", "brightness_dim", "off_timeout"]
            idx = state.get("setting_index", 0) % len(settings)
            key = settings[idx]
            current = int(cfg["oled"].get(key, 0))
            step_size = 1 if key != "off_timeout" else 5
            new_value = max(0, min(100 if key != "off_timeout" else 120, current + step_size * direction))
            cfg["oled"][key] = new_value
            save_config(cfg)
        save_state(state)

    def on_click():
        nonlocal state
        state["last_activity"] = time.time()
        if state.get("mode") == "volume":
            state["mode"] = "menu"
        elif state.get("mode") == "menu":
            state["mode"] = "volume"
        elif state.get("mode") == "settings":
            state["mode"] = "menu"
        save_state(state)

    def on_long_press():
        nonlocal state
        state["last_activity"] = time.time()
        if state.get("mode") == "settings":
            state["mode"] = "volume"
        else:
            state["mode"] = "settings"
            state["setting_index"] = state.get("menu_index", 0) % 3
        save_state(state)

    # Inicjalizacja hardware
    btn = Buttons(
        on_rotate=on_rotate,
        on_click=on_click,
        on_long_press=on_long_press
    )

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        btn.cleanup()
        print("[input_daemon] stop")


if __name__ == "__main__":
    main()
