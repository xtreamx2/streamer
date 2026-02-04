#!/usr/bin/env python3
import RPi.GPIO as GPIO
import os
import json

BASE_DIR = os.path.join(os.path.expanduser("~"), "streamer")
GPIO_MAP_PATH = os.path.join(BASE_DIR, "config", "gpio.json")


class Buttons:
    """
    Moduł obsługi wejść:
    - enkoder (A/B/SW)
    - przyciski GPIO (w przyszłości)
    """

    def __init__(self, on_rotate=None, on_click=None):
        self.on_rotate = on_rotate
        self.on_click = on_click

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

        # --- bezpieczne dodawanie przerwań dla A ---
        try:
            GPIO.add_event_detect(
                self.pin_a,
                GPIO.BOTH,
                callback=self._rotary_callback,
                bouncetime=2
            )
        except RuntimeError as e:
            print("[buttons] Nie można dodać event_detect dla pin_a:", e)
            print("[buttons] Wyłączam obsługę enkodera.")
            self.enabled = False
            return

        # --- bezpieczne dodawanie przerwań dla SW ---
        try:
            GPIO.add_event_detect(
                self.pin_sw,
                GPIO.FALLING,
                callback=self._button_callback,
                bouncetime=200
            )
        except RuntimeError as e:
            print("[buttons] Nie można dodać event_detect dla pin_sw:", e)
            print("[buttons] Wyłączam obsługę przycisku.")

    def _rotary_callback(self, channel):
        """Obsługa obrotu enkodera."""
        if not self.enabled:
            return

        a = GPIO.input(self.pin_a)
        b = GPIO.input(self.pin_b)

        if a != self.last_state:
            direction = +1 if b != a else -1
            if self.on_rotate:
                self.on_rotate(direction)
            self.last_state = a

    def _button_callback(self, channel):
        """Obsługa kliknięcia."""
        if self.on_click:
            self.on_click()

    # -----------------------------------------
    # CLEANUP
    # -----------------------------------------

    def cleanup(self):
        GPIO.cleanup()
