#!/usr/bin/env python3
import RPi.GPIO as GPIO
import os
import json
import time

BASE_DIR = os.path.join(os.path.expanduser("~"), "streamer")
GPIO_MAP_PATH = os.path.join(BASE_DIR, "config", "gpio.json")


class Buttons:
    """
    Moduł obsługi wejść:
    - enkoder (A/B/SW)
    - przyciski GPIO (w przyszłości)
    """

    def __init__(self, on_rotate=None, on_click=None, on_long_press=None):
        self.on_rotate = on_rotate
        self.on_click = on_click
        self.on_long_press = on_long_press
        self.debounce_s = 0.005
        self._last_event_time = 0.0
        self.long_press_s = 1.2
        self._press_time = None

        # Wczytaj mapę GPIO
        with open(GPIO_MAP_PATH, "r") as f:
            gpio = json.load(f)

        enc = gpio.get("encoder", {})
        self.enabled = enc.get("enabled", False)

        self.pin_a = enc.get("pin_a")
        self.pin_b = enc.get("pin_b")
        self.pin_sw = enc.get("pin_sw")

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        if self.enabled:
            self._init_encoder()

    # -----------------------------------------
    # ENCODER
    # -----------------------------------------

    def _init_encoder(self):
        """Inicjalizacja enkodera z bezpiecznym fallbackiem."""

        # Jeśli któryś pin nie jest ustawiony → wyłącz enkoder
        if None in (self.pin_a, self.pin_b, self.pin_sw):
            print("[buttons] Brak pinów enkodera w gpio.json — wyłączam.")
            self.enabled = False
            return

        GPIO.setup(self.pin_a, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pin_b, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pin_sw, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        self.last_state = GPIO.input(self.pin_a)

        # --- bezpieczne dodawanie przerwań dla A/B ---
        try:
            GPIO.add_event_detect(
                self.pin_a,
                GPIO.BOTH,
                callback=self._rotary_callback,
                bouncetime=2
            )
            GPIO.add_event_detect(
                self.pin_b,
                GPIO.BOTH,
                callback=self._rotary_callback,
                bouncetime=2
            )
        except RuntimeError as e:
            print("[buttons] Nie można dodać event_detect dla pinów enkodera:", e)
            print("[buttons] Wyłączam obsługę enkodera.")
            self.enabled = False
            return

        # --- bezpieczne dodawanie przerwań dla SW ---
        try:
            GPIO.add_event_detect(
                self.pin_sw,
                GPIO.BOTH,
                callback=self._button_callback,
                bouncetime=50
            )
        except RuntimeError as e:
            print("[buttons] Nie można dodać event_detect dla pin_sw:", e)
            print("[buttons] Wyłączam obsługę przycisku.")

    def _rotary_callback(self, channel):
        """Obsługa obrotu enkodera."""
        if not self.enabled:
            return

        now = time.monotonic()
        if now - self._last_event_time < self.debounce_s:
            return
        self._last_event_time = now

        a = GPIO.input(self.pin_a)
        b = GPIO.input(self.pin_b)

        if a != self.last_state:
            direction = +1 if b != a else -1
            if self.on_rotate:
                self.on_rotate(direction)
            self.last_state = a

    def _button_callback(self, channel):
        """Obsługa kliknięcia/long press."""
        if not self.enabled:
            return
        state = GPIO.input(self.pin_sw)
        if state == 0:
            self._press_time = time.monotonic()
            return

        if self._press_time is None:
            return

        duration = time.monotonic() - self._press_time
        self._press_time = None
        if duration >= self.long_press_s:
            if self.on_long_press:
                self.on_long_press()
        else:
            if self.on_click:
                self.on_click()

    # -----------------------------------------
    # CLEANUP
    # -----------------------------------------

    def cleanup(self):
        GPIO.cleanup()
