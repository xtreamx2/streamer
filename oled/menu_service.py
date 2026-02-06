#!/usr/bin/env python3
"""
STREAMER OLED menu service (complete file)

- Polling-based rotary encoder (quadrature) decoder with transition table
- Button short press = play/pause (mpc toggle)
- Button long press = enter/exit menu
- Rotate when not in menu = software volume change (mpc)
- Simple menu: Play radio / Stop playback / Exit menu
- Robust: tolerates missing display or missing GPIO libs (runs but limited)
"""
from __future__ import annotations
import os
import time
import threading
import subprocess
import signal
import sys

# Default hardware pins (BCM) - override via systemd Environment variables if needed
ENC_A = int(os.environ.get("ENC_A", "23"))  # physical 16
ENC_B = int(os.environ.get("ENC_B", "24"))  # physical 18
BTN   = int(os.environ.get("BTN",   "13"))  # physical 33

# menu items
MENU_ITEMS = [
    ("Play radio", "play_radio"),
    ("Stop playback", "stop"),
    ("Exit menu", "exit"),
]

LONG_PRESS_SEC = 0.8  # seconds to consider a long press

# display defaults
WIDTH = 128
HEIGHT = 64

# Try display imports (non-fatal)
try:
    import board, busio
    from adafruit_ssd1306 import SSD1306_I2C
    from PIL import Image, ImageDraw, ImageFont
except Exception as e:
    SSD1306_I2C = None
    Image = None
    ImageDraw = None
    ImageFont = None
    # Don't exit — service should continue even without display
    print("Missing display libs:", e)

# Try GPIO import (non-fatal; service still runs without GPIO)
try:
    import RPi.GPIO as GPIO
except Exception as e:
    GPIO = None
    print("Missing RPi.GPIO:", e)


class EncoderMenu:
    def __init__(self):
        # initial volume (attempt to read from mpc)
        vol = self.get_mpc_volume()
        self.volume = vol if vol is not None else 30
        self.in_menu = False
        self.menu_index = 0
        self.running = True
        self.display = None
        self.font = None
        self._prev_ab = 0
        self._poll_thread = None

        # initialize display and GPIO
        self._init_display()
        self._setup_gpio()

        # handle termination signals
        signal.signal(signal.SIGTERM, self._sigterm)
        signal.signal(signal.SIGINT, self._sigterm)

        print(f"EncoderMenu initialized. ENC_A={ENC_A} ENC_B={ENC_B} BTN={BTN} Volume={self.volume}")

    # Display initialization (tries 0x3C then 0x3D)
    def _init_display(self):
        if SSD1306_I2C is None or Image is None:
            print("Display not available; running headless.")
            self.display = None
            return
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.display = SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=0x3C)
            self.display.contrast(200)
            self.font = ImageFont.load_default()
            print("Display initialized at 0x3C")
        except Exception as e1:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.display = SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=0x3D)
                self.display.contrast(200)
                self.font = ImageFont.load_default()
                print("Display initialized at 0x3D")
            except Exception as e2:
                print("Failed to initialize display:", e1, e2)
                self.display = None

    # Setup GPIOs and start poll thread
    def _setup_gpio(self):
        if GPIO is None:
            print("GPIO not available; encoder/button disabled.")
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(ENC_A, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(ENC_B, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(BTN,   GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # initial AB state
        a = GPIO.input(ENC_A)
        b = GPIO.input(ENC_B)
        self._prev_ab = (a << 1) | b
        # start polling thread
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        print("GPIO polling thread started.")

    # Polling loop with transition table + simple button detection
    def _poll_loop(self):
        # transition map: (prev<<2)|curr -> step
        trans_table = {
            1:  1,   # 00 -> 01
            7:  1,   # 01 -> 11
            14: 1,   # 11 -> 10
            8:  1,   # 10 -> 00
            2:  -1,  # 00 -> 10
            11: -1,  # 10 -> 11
            13: -1,  # 11 -> 01
            4:  -1   # 01 -> 00
        }
        btn_last = GPIO.input(BTN)
        btn_time = None
        while self.running:
            try:
                a = GPIO.input(ENC_A)
                b = GPIO.input(ENC_B)
                state = (a << 1) | b
                if state != self._prev_ab:
                    key = (self._prev_ab << 2) | state
                    move = trans_table.get(key, 0)
                    if move != 0:
                        # single step per detent
                        self._step(move)
                    self._prev_ab = state
                # button logic (active low)
                s = GPIO.input(BTN)
                if s == 0 and btn_last == 1:
                    btn_time = time.time()
                elif s == 1 and btn_last == 0 and btn_time is not None:
                    held = time.time() - btn_time
                    btn_time = None
                    if held >= LONG_PRESS_SEC:
                        self._on_long_press()
                    else:
                        self._on_short_press()
                btn_last = s
                time.sleep(0.002)  # 2 ms poll
            except Exception as ex:
                print("Error in poll loop:", ex)
                time.sleep(0.05)

    # step: delta = +1 or -1
    def _step(self, delta):
        if self.in_menu:
            self.menu_index = (self.menu_index + (1 if delta > 0 else -1)) % len(MENU_ITEMS)
            self._draw()
        else:
            new_vol = max(0, min(100, self.volume + (5 if delta > 0 else -5)))
            if new_vol != self.volume:
                self.volume = new_vol
                self.set_mpc_volume(self.volume)
                self._draw()

    def _on_short_press(self):
        if self.in_menu:
            self._select_menu_item()
        else:
            self.toggle_play_pause()
        self._draw()

    def _on_long_press(self):
        self.in_menu = not self.in_menu
        if self.in_menu:
            self.menu_index = 0
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

    # MPC / MPD helpers
    def toggle_play_pause(self):
        try:
            subprocess.call(["mpc", "toggle"])
        except Exception as e:
            print("toggle_play_pause error:", e)

    def play_radio(self):
        try:
            subprocess.call(["mpc", "load", "radio"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.call(["mpc", "play"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("play_radio: triggered")
        except Exception as e:
            print("play_radio error:", e)

    def stop_playback(self):
        try:
            subprocess.call(["mpc", "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("stop_playback: triggered")
        except Exception as e:
            print("stop_playback error:", e)

    def set_mpc_volume(self, vol: int):
        try:
            subprocess.call(["mpc", "volume", str(vol)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print("set_mpc_volume error:", e)

    def get_mpc_volume(self):
        try:
            out = subprocess.check_output(["mpc", "volume"], stderr=subprocess.STDOUT, text=True)
            # output example: "volume: 30   repeat: off   random: off   single: off   consume: off"
            for token in out.replace(":", " ").split():
                if token.isdigit():
                    return int(token)
        except Exception:
            return None

    # Drawing function
    def _draw(self):
        if self.display is None:
            # fallback: print to stdout minimal info
            now = ""
            try:
                now = subprocess.check_output(["mpc", "current"], text=True).strip()
            except Exception:
                now = ""
            if self.in_menu:
                print("MENU:")
                for idx, (label, _) in enumerate(MENU_ITEMS):
                    prefix = ">" if idx == self.menu_index else " "
                    print(f"{prefix} {label}")
            else:
                print(f"STREAMER | Vol: {self.volume}% | Now: {now[:30]}")
            return

        # draw to OLED
        try:
            image = Image.new("1", (WIDTH, HEIGHT))
            draw = ImageDraw.Draw(image)
            if self.in_menu:
                y = 0
                for idx, (label, _) in enumerate(MENU_ITEMS):
                    prefix = ">" if idx == self.menu_index else " "
                    draw.text((0, y), f"{prefix} {label}", font=self.font, fill=255)
                    y += 10
            else:
                try:
                    now = subprocess.check_output(["mpc", "current"], text=True).strip()
                except Exception:
                    now = ""
                draw.text((0, 0), "STREAMER", font=self.font, fill=255)
                draw.text((0, 14), f"Now: {now[:24]}", font=self.font, fill=255)
                draw.text((0, 28), f"Vol: {self.volume}%", font=self.font, fill=255)
                draw.text((0, 42), "Click=Play/Pause", font=self.font, fill=255)
                draw.text((0, 52), "Hold=Menu", font=self.font, fill=255)
            self.display.image(image)
            self.display.show()
        except Exception as e:
            print("Draw error:", e)

    def run(self):
        # initial draw
        try:
            self._draw()
        except Exception as e:
            print("Initial draw error:", e)
        # main loop just keeps service alive; poll thread does input handling
        try:
            while self.running:
                time.sleep(0.2)
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def _cleanup(self):
        print("Cleaning up service...")
        if self.display:
            try:
                self.display.fill(0)
                self.display.show()
            except Exception:
                pass
        if GPIO is not None:
            try:
                GPIO.cleanup()
            except Exception:
                pass

    def _sigterm(self, signum, frame):
        print("Term signal received, stopping.")
        self.running = False


def main():
    svc = EncoderMenu()
    try:
        svc.run()
    except Exception as e:
        print("Service fatal error:", e)
        try:
            svc._cleanup()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
