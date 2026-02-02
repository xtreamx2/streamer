#!/usr/bin/env python3
import os
import time
import json
import board, busio
import RPi.GPIO as GPIO
from mpd import MPDClient
from adafruit_ssd1306 import SSD1306_I2C
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.join(os.path.expanduser("~"), "streamer")
CONFIG_PATH = os.path.join(BASE_DIR, "oled", "config.json")
GRAPHICS_DIR = os.path.join(BASE_DIR, "oled", "graphics")

def load_config():
    cfg = {
        "dim_timeout": 30,
        "off_timeout": 120,
        "brightness_normal": 80,
        "brightness_dim": 1,
        "mpd_host": "localhost",
        "mpd_port": 6600,
        "encoder": {
            "enabled": True,
            "pin_a": 17,
            "pin_b": 27,
            "pin_sw": 22
        }
    }
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
            cfg.update(data)
    except Exception:
        pass
    return cfg

def init_display():
    i2c = busio.I2C(board.SCL, board.SDA)
    disp = SSD1306_I2C(128, 64, i2c, addr=0x3C)
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
    except Exception as e:
        print("Logo/anim error:", e)

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

        volume = status.get("volume", "0")
        state = status.get("state", "stop")
        bitrate = status.get("bitrate", "")
        samplerate = song.get("samplerate", "")
        bits = song.get("bitdepth", "")

        return {
            "station": station,
            "volume": volume,
            "state": state,
            "bitrate": bitrate,
            "samplerate": samplerate,
            "bits": bits
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

def draw_status(display, info):
    image = Image.new("1", (128, 64))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    station = info["station"]
    volume = info["volume"]
    state = info["state"]

    line1 = station[:20]
    line2 = f"Vol:{volume}%  {'▶' if state=='play' else '❚❚' if state=='pause' else '■'}"

    draw.text((0, 0), line1, font=font, fill=255)
    draw.text((0, 16), line2, font=font, fill=255)

    display.image(image)
    display.show()

class Encoder:
    def __init__(self, pin_a, pin_b, pin_sw, on_rotate, on_click):
        self.pin_a = pin_a
        self.pin_b = pin_b
        self.pin_sw = pin_sw
        self.on_rotate = on_rotate
        self.on_click = on_click
        self.last_state = None

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin_a, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pin_b, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pin_sw, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        GPIO.add_event_detect(self.pin_a, GPIO.BOTH, callback=self._rotary_callback, bouncetime=2)
        GPIO.add_event_detect(self.pin_sw, GPIO.FALLING, callback=self._button_callback, bouncetime=200)

    def _rotary_callback(self, channel):
        a = GPIO.input(self.pin_a)
        b = GPIO.input(self.pin_b)
        if self.last_state is None:
            self.last_state = a
            return
        if a != self.last_state:
            if b != a:
                self.on_rotate(+1)
            else:
                self.on_rotate(-1)
            self.last_state = a

    def _button_callback(self, channel):
        self.on_click()

def main():
    cfg = load_config()
    dim_timeout = cfg["dim_timeout"]
    off_timeout = cfg["off_timeout"]
    b_norm = cfg["brightness_normal"]
    b_dim = cfg["brightness_dim"]

    display = init_display()
    show_logo(display)

    client = connect_mpd(cfg["mpd_host"], cfg["mpd_port"])
    last_activity = time.time()

    def enc_rotate(direction):
        nonlocal client, last_activity
        if client is None:
            client = connect_mpd(cfg["mpd_host"], cfg["mpd_port"])
        try:
            status = client.status()
            vol = int(status.get("volume", "0"))
            vol = max(0, min(100, vol + direction * 2))
            client.setvol(vol)
            last_activity = time.time()
        except Exception:
            client = None

    def enc_click():
        nonlocal client, last_activity
        if client is None:
            client = connect_mpd(cfg["mpd_host"], cfg["mpd_port"])
        try:
            status = client.status()
            state = status.get("state", "stop")
            if state == "play":
                client.pause(1)
            else:
                client.play()
            last_activity = time.time()
        except Exception:
            client = None

    encoder = None
    if cfg["encoder"]["enabled"]:
        encoder = Encoder(
            cfg["encoder"]["pin_a"],
            cfg["encoder"]["pin_b"],
            cfg["encoder"]["pin_sw"],
            enc_rotate,
            enc_click
        )

    try:
        while True:
            if client is None:
                client = connect_mpd(cfg["mpd_host"], cfg["mpd_port"])

            info = get_mpd_status(client)
            draw_status(display, info)

            now = time.time()
            idle = now - last_activity

            if idle > off_timeout:
                display.fill(0)
                display.show()
            elif idle > dim_timeout:
                display.contrast(b_dim)
            else:
                display.contrast(b_norm)

            time.sleep(0.5)
    finally:
        if encoder:
            GPIO.cleanup()

if __name__ == "__main__":
    main()
