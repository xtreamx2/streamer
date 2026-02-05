#!/usr/bin/env python3
import os
import time
import json
import board, busio
from mpd import MPDClient
from adafruit_ssd1306 import SSD1306_I2C
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.join(os.path.expanduser("~"), "streamer")
CONFIG_PATH = os.path.join(BASE_DIR, "oled", "config.json")
GPIO_MAP_PATH = os.path.join(BASE_DIR, "config", "gpio.json")
GRAPHICS_DIR = os.path.join(BASE_DIR, "oled", "graphics")
INPUT_STATE_PATH = os.path.join(BASE_DIR, "oled", "input_state.json")

# -------------------------------
# CONFIG LOADERS
# -------------------------------

def deep_merge(base, override):
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = deep_merge(base[key], value)
        else:
            merged[key] = value
    return merged


def load_runtime_config():
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


def load_gpio_map():
    defaults = {
        "oled": {
            "type": "ssd1306",
            "width": 128,
            "height": 64,
            "address": "0x3C",
            "rotation": "0"
        }
    }
    try:
        with open(GPIO_MAP_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return defaults


def load_input_state():
    defaults = {
        "last_activity": time.time(),
        "mode": "volume",
        "menu_index": 0,
        "setting_index": 0
    }
    try:
        with open(INPUT_STATE_PATH, "r") as f:
            data = json.load(f)
            return deep_merge(defaults, data)
    except Exception:
        return defaults

# -------------------------------
# OLED
# -------------------------------

def init_display(oled_cfg):
    i2c = busio.I2C(board.SCL, board.SDA)
    disp = SSD1306_I2C(
        oled_cfg["width"],
        oled_cfg["height"],
        i2c,
        addr=int(oled_cfg["address"], 16)
    )
    disp.fill(0)
    disp.show()
    return disp


def load_pbm(name):
    path = os.path.join(GRAPHICS_DIR, name)
    return Image.open(path).convert("1")


def show_logo(display):
    try:
        frames = []
        anim_dir = os.path.join(GRAPHICS_DIR, "anim")

        if os.path.isdir(anim_dir):
            for fname in sorted(os.listdir(anim_dir)):
                if fname.lower().endswith(".pbm"):
                    frames.append(load_pbm(os.path.join("anim", fname)))

        if not frames:
            frames = [load_pbm("logo.pbm")]

        for _ in range(2):
            for frame in frames:
                display.image(frame)
                display.show()
                time.sleep(0.1)

        display.fill(0)
        display.show()
        time.sleep(1)

    except Exception as e:
        print("Logo/anim error:", e)

# -------------------------------
# MPD
# -------------------------------

def connect_mpd(host, port):
    client = MPDClient()
    client.timeout = 2
    client.idletimeout = None
    try:
        client.connect(host, port)
        return client
    except Exception:
        return None


def get_mpd_status(client):
    try:
        status = client.status()
        song = client.currentsong()

        station = (
            song.get("name")
            or song.get("title")
            or song.get("file")
            or "Brak danych"
        )

        return {
            "station": station,
            "volume": status.get("volume", "0"),
            "state": status.get("state", "stop"),
            "bitrate": status.get("bitrate", ""),
            "samplerate": song.get("samplerate", ""),
            "bits": song.get("bitdepth", "")
        }
    except Exception:
        return {
            "station": "Brak połączenia",
            "volume": "0",
            "state": "stop",
            "bitrate": "",
            "samplerate": "",
            "bits": ""
        }

# -------------------------------
# OLED STATUS SCREEN
# -------------------------------

def sanitize_text(text):
    return text.encode("ascii", "replace").decode("ascii")


def draw_menu_bar(draw, font, width, mode):
    menu_items = ["VOL", "MENU", "SET"]
    bar_height = 12
    draw.rectangle((0, 0, width, bar_height), fill=255)

    x = 2
    for item in menu_items:
        active = (mode == "volume" and item == "VOL") or (mode == "menu" and item == "MENU") or (mode == "settings" and item == "SET")
        bbox = draw.textbbox((0, 0), item, font=font)
        text_width = bbox[2] - bbox[0]
        if active:
            draw.rectangle((x - 1, 1, x + text_width + 1, bar_height - 1), fill=0)
            draw.text((x, 1), item, font=font, fill=255)
        else:
            draw.text((x, 1), item, font=font, fill=0)
        x += text_width + 6

    return bar_height


def draw_status(display, info, mode="volume"):
    image = Image.new("1", (128, 64))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    menu_height = draw_menu_bar(draw, font, 128, mode)

    line1 = sanitize_text(info["station"][:20])
    state_symbol = ">" if info["state"] == "play" else "||" if info["state"] == "pause" else "[]"
    line2 = sanitize_text(f"Vol:{info['volume']}%  {state_symbol}")

    draw.text((0, menu_height + 2), line1, font=font, fill=255)
    draw.text((0, menu_height + 18), line2, font=font, fill=255)

    display.image(image)
    display.show()


def draw_menu(display, state, cfg):
    image = Image.new("1", (128, 64))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    menu_height = draw_menu_bar(draw, font, 128, "menu")

    menu_items = ["Jasnosc", "Przyciemn.", "Wygaszenie"]
    values = [
        f"{cfg['oled'].get('brightness_active', 50)}%",
        f"{cfg['oled'].get('brightness_dim', 10)}%",
        f"{cfg['oled'].get('off_timeout', 30)}s"
    ]

    y = menu_height + 2
    for idx, item in enumerate(menu_items):
        prefix = ">" if idx == state.get("menu_index", 0) else " "
        line = f"{prefix}{item}: {values[idx]}"
        draw.text((0, y), sanitize_text(line)[:21], font=font, fill=255)
        y += 12

    display.image(image)
    display.show()


def draw_settings(display, state, cfg):
    image = Image.new("1", (128, 64))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    menu_height = draw_menu_bar(draw, font, 128, "settings")

    settings = [
        ("Jasnosc", "brightness_active", "%"),
        ("Przyciemn.", "brightness_dim", "%"),
        ("Wygaszenie", "off_timeout", "s")
    ]

    idx = state.get("setting_index", 0) % len(settings)
    name, key, suffix = settings[idx]
    value = cfg["oled"].get(key, 0)

    draw.text((0, menu_height + 4), sanitize_text(f"Ustaw: {name}")[:21], font=font, fill=255)
    draw.text((0, menu_height + 20), sanitize_text(f"{value}{suffix}")[:21], font=font, fill=255)
    draw.text((0, menu_height + 36), sanitize_text("Obrot: zmien")[:21], font=font, fill=255)
    draw.text((0, menu_height + 48), sanitize_text("Klik: wroc")[:21], font=font, fill=255)

    display.image(image)
    display.show()


def brightness_to_contrast(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 0
    if value > 100:
        return max(0, min(255, value))
    return max(0, min(255, int(value * 2.55)))

# -------------------------------
# MAIN LOOP
# -------------------------------

def main():
    cfg = load_runtime_config()
    gpio = load_gpio_map()

    oled_cfg = gpio["oled"]
    mpd_cfg = cfg["mpd"]
    oled_rt = cfg["oled"]

    display = init_display(oled_cfg)
    show_logo(display)

    client = connect_mpd(mpd_cfg["host"], mpd_cfg["port"])
    last_activity = time.time()

    try:
        while True:
            if client is None:
                client = connect_mpd(mpd_cfg["host"], mpd_cfg["port"])

            info = get_mpd_status(client)
            state = load_input_state()
            mode = state.get("mode", "volume")

            if mode == "menu":
                draw_menu(display, state, cfg)
            elif mode == "settings":
                draw_settings(display, state, cfg)
            else:
                draw_status(display, info, mode=mode)

            last_activity = state.get("last_activity", last_activity)
            idle = time.time() - last_activity
            bright_active = brightness_to_contrast(oled_rt.get("brightness_active", 50))
            bright_dim = brightness_to_contrast(oled_rt.get("brightness_dim", 10))

            if idle > oled_rt["off_timeout"]:
                display.fill(0)
                display.show()
            elif idle > oled_rt["dim_timeout"]:
                display.contrast(bright_dim)
            else:
                display.contrast(bright_active)

            time.sleep(0.5)

    finally:
        pass


if __name__ == "__main__":
    main()
    
