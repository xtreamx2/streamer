#!/usr/bin/env python3
"""
Simple OLED menu + encoder service for STREAMER

Features:
- short click -> play/pause (mpc toggle)
- long press  -> enter/exit menu
- rotate      -> change volume when NOT in menu, change selection when in menu
- in menu: short click selects option
"""
import os
import time
import threading
import subprocess
import signal
import sys

# hardware pins (BCM) - adjust if your wiring differs
ENC_A = int(os.environ.get("ENC_A", "17"))
ENC_B = int(os.environ.get("ENC_B", "18"))
BTN   = int(os.environ.get("BTN",   "27"))

# menu options (simple examples)
MENU_ITEMS = [
    ("Play radio", "play_radio"),
    ("Stop playback", "stop"),
    ("Exit menu", "exit"),
]

# debounce / timing thresholds
LONG_PRESS_SEC = 0.8

# display settings
WIDTH = 128
HEIGHT = 64

# try imports for OLED + GPIO
try:
    import board, busio
    from adafruit_ssd1306 import SSD1306_I2C
    from PIL import Image, ImageDraw, ImageFont
except Exception as e:
    print("Missing display libs:", e)
    SSD1306_I2C = None

try:
    import RPi.GPIO as GPIO
except Exception:
    # fallback for dev/test environments
    GPIO = None

class EncoderMenu:
    def __init__(self):
        self.volume = self.get_mpc_volume() or 30
        self.in_menu = False
        self.menu_index = 0
        self.running = True
        self.last_a = 0
        self.last_b = 0
        self.btn_down_time = None
        self.display = None
        self.font = None
        self._init_display()
        self._setup_gpio()
        signal.signal(signal.SIGTERM, self._sigterm)
        signal.signal(signal.SIGINT, self._sigterm)

    def _init_display(self):
        if SSD1306_I2C is None:
            return
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.display = SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=0x3C)
            self.display.contrast(1)
            self.font = ImageFont.load_default()
        except Exception:
            # try 0x3D
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.display = SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=0x3D)
                self.display.contrast(1)
                self.font = ImageFont.load_default()
            except Exception:
                self.display = None

    def _setup_gpio(self):
        if GPIO is None:
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(ENC_A, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(ENC_B, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(BTN,   GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # event callbacks
        GPIO.add_event_detect(ENC_A, GPIO.BOTH, callback=self._rotary_cb, bouncetime=2)
        GPIO.add_event_detect(ENC_B, GPIO.BOTH, callback=self._rotary_cb, bouncetime=2)
        GPIO.add_event_detect(BTN, GPIO.BOTH, callback=self._btn_cb, bouncetime=50)

    # rotary callback: on change of A or B detect direction
    def _rotary_cb(self, channel):
        if GPIO is None:
            return
        a = GPIO.input(ENC_A)
        b = GPIO.input(ENC_B)
        # simple state-based direction detection
        if a == b:
            self._step(-1)
        else:
            self._step(1)

    def _btn_cb(self, channel):
        if GPIO is None:
            return
        state = GPIO.input(BTN)
        if state == 0:  # pressed (active low)
            self.btn_down_time = time.time()
        else:  # released
            if not self.btn_down_time:
                return
            held = time.time() - self.btn_down_time
            self.btn_down_time = None
            if held >= LONG_PRESS_SEC:
                self._on_long_press()
            else:
                self._on_short_press()

    def _on_short_press(self):
        if self.in_menu:
            self._select_menu_item()
        else:
            self.toggle_play_pause()

    def _on_long_press(self):
        # enter/exit menu
        self.in_menu = not self.in_menu
        if self.in_menu:
            # reset selection
            self.menu_index = 0
        self._draw()

    def _step(self, delta):
        if self.in_menu:
            # rotate through menu items
            self.menu_index = (self.menu_index + (1 if delta > 0 else -1)) % len(MENU_ITEMS)
            self._draw()
        else:
            # change volume
            new_vol = max(0, min(100, self.volume + (5 if delta > 0 else -5)))
            if new_vol != self.volume:
                self.volume = new_vol
                self.set_mpc_volume(self.volume)
                self._draw()

    def _select_menu_item(self):
        label, action = MENU_ITEMS[self.menu_index]
        if action == "play_radio":
            self.play_radio()
        elif action == "stop":
            self.stop_playback()
        elif action == "exit":
            self.in_menu = False
        self._draw()

    # MPD / MPC helpers
    def toggle_play_pause(self):
        subprocess.call(["mpc", "toggle"])
        self._draw()

    def play_radio(self):
        # try to load saved playlist 'radio' or play current 'radio' entry
        subprocess.call(["mpc", "load", "radio"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call(["mpc", "play"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop_playback(self):
        subprocess.call(["mpc", "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def set_mpc_volume(self, vol):
        subprocess.call(["mpc", "volume", str(vol)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def get_mpc_volume(self):
        try:
            out = subprocess.check_output(["mpc", "volume"], stderr=subprocess.STDOUT, text=True)
            # out like: "volume: 30   repeat: off   random: off   single: off   consume: off"
            for part in out.split():
                if part.isdigit():
                    return int(part)
        except Exception:
            return None

    # Drawing
    def _draw(self):
        if self.display is None:
            return
        image = Image.new("1", (WIDTH, HEIGHT))
        draw = ImageDraw.Draw(image)
        if self.in_menu:
            # draw menu (items, highlight)
            y = 0
            for idx, (label, _) in enumerate(MENU_ITEMS):
                prefix = ">" if idx == self.menu_index else " "
                draw.text((0, y), f"{prefix} {label}", font=self.font, fill=255)
                y += 10
        else:
            # main screen: now playing info + volume
            # try to get current track
            try:
                now = subprocess.check_output(["mpc", "current"], text=True).strip()
            except Exception:
                now = ""
            draw.text((0, 0), "STREAMER", font=self.font, fill=255)
            draw.text((0, 14), f"Now: {now[:24]}", font=self.font, fill=255)
            draw.text((0, 28), f"Vol: {self.volume}%", font=self.font, fill=255)
            draw.text((0, 42), "Click=Play/Pause", font=self.font, fill=255)
            draw.text((0, 52), "Hold=Menu", font=self.font, fill=255)
        try:
            self.display.image(image)
            self.display.show()
        except Exception:
            pass

    def run(self):
        # initial draw
        self._draw()
        while self.running:
            time.sleep(0.2)
        self._cleanup()

    def _cleanup(self):
        # blank display on exit
        if self.display:
            try:
                self.display.fill(0)
                self.display.show()
            except Exception:
                pass
        if GPIO is not None:
            GPIO.cleanup()

    def _sigterm(self, signum, frame):
        self.running = False

if __name__ == "__main__":
    svc = EncoderMenu()
    try:
        svc.run()
    except Exception as e:
        print("Service error:", e)
        svc._cleanup()
        sys.exit(1)
