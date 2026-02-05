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

# -------------------------------
# CONFIG LOADERS
# -------------------------------

def load_runtime_config():
    defaults = {
        "oled": {
            "brightness_normal": 80,
            "brightness_dim": 1,
            "dim_timeout": 30,
            "off_timeout": 120
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
            return {**defaults, **data}
    except Exception:
        return defaults


def load_gpio_map():
    with open(GPIO_MAP_PATH, "r") as f:
        return json.load(f)

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

def draw_menu_bar(draw, font, width):
    menu_items = ["RADIO", "INFO", "SET"]
    bar_height = 12
    draw.rectangle((0, 0, width, bar_height), fill=255)

    x = 2
    for item in menu_items:
        bbox = draw.textbbox((0, 0), item, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text((x, 1), item, font=font, fill=0)
        x += text_width + 6

    return bar_height


def draw_status(display, info):
    image = Image.new("1", (128, 64))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    menu_height = draw_menu_bar(draw, font, 128)

    line1 = info["station"][:20]
    line2 = (
        f"Vol:{info['volume']}%  "
        f"{'▶' if info['state']=='play' else '❚❚' if info['state']=='pause' else '■'}"
    )

    draw.text((0, menu_height + 2), line1, font=font, fill=255)
    draw.text((0, menu_height + 18), line2, font=font, fill=255)

    display.image(image)
    display.show()

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
            draw_status(display, info)

            idle = time.time() - last_activity

            if idle > oled_rt["off_timeout"]:
                display.fill(0)
                display.show()
            elif idle > oled_rt["dim_timeout"]:
                display.contrast(oled_rt["brightness_dim"])
            else:
                display.contrast(oled_rt["brightness_normal"])

            time.sleep(0.5)

    finally:
        pass


if __name__ == "__main__":
    main()
