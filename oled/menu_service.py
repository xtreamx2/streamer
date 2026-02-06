#!/usr/bin/env python3
"""
STREAMER OLED menu service (user-mode, venv-friendly)

Features:
- rotary encoder (polling + transition table)
- short click -> play/pause (mpc)
- long press -> enter/exit menu
- rotate outside menu -> software volume (mpc)
- simple menu with selectable items
- inactivity dimming: after DIM_TIMEOUT seconds display.contrast(DIM_CONTRAST)
- configurable via env: ENC_A, ENC_B, BTN, INVERT_ROT, DIM_TIMEOUT, DIM_CONTRAST, NORMAL_CONTRAST
"""
from __future__ import annotations
import os, time, threading, subprocess, signal, sys

# ENV-configurable pins (BCM). Default values for your wiring:
ENC_A = int(os.environ.get("ENC_A", "23"))  # physical 16
ENC_B = int(os.environ.get("ENC_B", "24"))  # physical 18
BTN   = int(os.environ.get("BTN",   "13"))  # physical 33
INVERT_ROT = os.environ.get("INVERT_ROT", "0") == "1"

# dimming config (seconds)
DIM_TIMEOUT = float(os.environ.get("DIM_TIMEOUT", "30"))
DIM_CONTRAST = int(os.environ.get("DIM_CONTRAST", "0"))
NORMAL_CONTRAST = int(os.environ.get("NORMAL_CONTRAST", "200"))

MENU_ITEMS = [
    ("Play radio", "play_radio"),
    ("Stop playback", "stop"),
    ("Exit menu", "exit"),
]

LONG_PRESS_SEC = 0.8
POLL_INTERVAL = 0.002

# Try imports
try:
    import board, busio
    from adafruit_ssd1306 import SSD1306_I2C
    from PIL import Image, ImageDraw, ImageFont
except Exception as e:
    SSD1306_I2C = None
    Image = ImageDraw = ImageFont = None
    print("Display libs missing:", e)

try:
    import RPi.GPIO as GPIO
except Exception as e:
    GPIO = None
    print("RPi.GPIO missing:", e)


class EncoderMenu:
    def __init__(self):
        self.volume = self._get_mpc_volume() or 30
        self.in_menu = False
        self.menu_index = 0
        self.running = True
        self.display = None
        self.font = None
        self._prev_ab = 0
        self._poll_thread = None

        # activity / dimming
        self._last_activity = time.time()
        self._is_dimmed = False

        # debounce
        self._last_short_press = 0.0
        self._debounce_sec = 0.25

        self._init_display()
        self._setup_gpio()

        signal.signal(signal.SIGTERM, self._sigterm)
        signal.signal(signal.SIGINT, self._sigterm)

        print(f"EncoderMenu initialized. ENC_A={ENC_A} ENC_B={ENC_B} BTN={BTN} Volume={self.volume} DIM_TIMEOUT={DIM_TIMEOUT}s")

    # Display init (tries 0x3C then 0x3D)
    def _init_display(self):
        if SSD1306_I2C is None or Image is None:
            print("Display not available; running headless.")
            self.display = None
            return
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.display = SSD1306_I2C(128, 64, i2c, addr=0x3C)
            self.display.contrast(NORMAL_CONTRAST)
            self.font = ImageFont.load_default()
            print("Display initialized at 0x3C")
        except Exception as e1:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.display = SSD1306_I2C(128, 64, i2c, addr=0x3D)
                self.display.contrast(NORMAL_CONTRAST)
                self.font = ImageFont.load_default()
                print("Display initialized at 0x3D")
            except Exception as e2:
                print("Display init failed:", e1, e2)
                self.display = None

    def _setup_gpio(self):
        if GPIO is None:
            print("GPIO not available; encoder disabled.")
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(ENC_A, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(ENC_B, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(BTN,   GPIO.IN, pull_up_down=GPIO.PUD_UP)
        a = GPIO.input(ENC_A); b = GPIO.input(ENC_B)
        self._prev_ab = (a << 1) | b
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        print("GPIO polling thread started.")

    def _poll_loop(self):
        # transition map
        trans_table = {
            1:  1, 7:  1, 14: 1, 8:  1,
            2: -1, 11: -1, 13: -1, 4: -1
        }
        btn_last = GPIO.input(BTN)
        btn_time = None
        while self.running:
            try:
                a = GPIO.input(ENC_A); b = GPIO.input(ENC_B)
                state = (a << 1) | b
                if state != self._prev_ab:
                    key = (self._prev_ab << 2) | state
                    move = trans_table.get(key, 0)
                    if move != 0:
                        # allow invert via ENV
                        move = -move if INVERT_ROT else move
                        self._note_activity()
                        self._step(move)
                    self._prev_ab = state

                # button logic (active low)
                s = GPIO.input(BTN)
                if s == 0 and btn_last == 1:
                    btn_time = time.time()
                elif s == 1 and btn_last == 0 and btn_time is not None:
                    held = time.time() - btn_time
                    btn_time = None
                    self._note_activity()
                    if held >= LONG_PRESS_SEC:
                        self._on_long_press()
                    else:
                        self._on_short_press()
                btn_last = s

                # dim check within poll loop (frequent checks)
                self._maybe_dim()
                time.sleep(POLL_INTERVAL)
            except Exception as ex:
                print("Poll loop error:", ex)
                time.sleep(0.05)

    def _note_activity(self):
        self._last_activity = time.time()
        if self._is_dimmed:
            self._undim()

    def _maybe_dim(self):
        if self.display is None:
            return
        if not self._is_dimmed and (time.time() - self._last_activity) >= DIM_TIMEOUT:
            self._dim()

    def _dim(self):
        try:
            self.display.contrast(DIM_CONTRAST)
            self._is_dimmed = True
            # optional: blank, but keep low-contrast shown
            # self.display.fill(0); self.display.show()
            print("Display dimmed.")
        except Exception as e:
            print("Dim error:", e)

    def _undim(self):
        try:
            self.display.contrast(NORMAL_CONTRAST)
            self._is_dimmed = False
            self._draw()
            print("Display restored from dim.")
        except Exception as e:
            print("Undim error:", e)

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
        now = time.time()
        if now - self._last_short_press < self._debounce_sec:
            return
        self._last_short_press = now
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

    # MPD helpers (quiet errors)
    def toggle_play_pause(self):
        subprocess.call(["mpc", "toggle"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def play_radio(self):
        subprocess.call(["mpc", "load", "radio"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call(["mpc", "play"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop_playback(self):
        subprocess.call(["mpc", "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def set_mpc_volume(self, vol: int):
        subprocess.call(["mpc", "volume", str(vol)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _get_mpc_volume(self):
        try:
            out = subprocess.check_output(["mpc", "volume"], stderr=subprocess.DEVNULL, text=True)
            for token in out.replace(":", " ").split():
                if token.isdigit():
                    return int(token)
        except Exception:
            return None

    def _draw(self):
        if self.display is None:
            now = ""
            try:
                now = subprocess.check_output(["mpc", "current"], stderr=subprocess.DEVNULL, text=True).strip()
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

        try:
            img = Image.new("1", (128, 64))
            d = ImageDraw.Draw(img)
            if self.in_menu:
                y = 0
                for idx, (label, _) in enumerate(MENU_ITEMS):
                    prefix = ">" if idx == self.menu_index else " "
                    d.text((0, y), f"{prefix} {label}", font=self.font, fill=255)
                    y += 10
            else:
                try:
                    now = subprocess.check_output(["mpc", "current"], stderr=subprocess.DEVNULL, text=True).strip()
                except Exception:
                    now = ""
                d.text((0, 0), "STREAMER", font=self.font, fill=255)
                d.text((0, 14), f"Now: {now[:24]}", font=self.font, fill=255)
                d.text((0, 28), f"Vol: {self.volume}%", font=self.font, fill=255)
                d.text((0, 42), "Click=Play/Pause", font=self.font, fill=255)
                d.text((0, 52), "Hold=Menu", font=self.font, fill=255)
            self.display.image(img)
            self.display.show()
        except Exception as e:
            print("Draw error:", e)

    def run(self):
        try:
            self._draw()
        except Exception as e:
            print("Initial draw error:", e)
        try:
            while self.running:
                time.sleep(0.2)
                # also check dimming from main loop (redundant to poll)
                self._maybe_dim()
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
        print("Term signal, stopping.")
        self.running = False


if __name__ == "__main__":
    svc = EncoderMenu()
    try:
        svc.run()
    except Exception as e:
        print("Service error:", e)
        try:
            svc._cleanup()
        except Exception:
            pass
        sys.exit(1)
