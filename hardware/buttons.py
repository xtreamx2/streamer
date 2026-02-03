#!/usr/bin/env python3
import os
import json
import time
import RPi.GPIO as GPIO

BASE_DIR = os.path.join(os.path.expanduser("~"), "streamer")
GPIO_MAP_PATH = os.path.join(BASE_DIR, "config", "gpio.json")


class Buttons:
    """
    Uniwersalny moduł wejść:
    - enkoder (A/B/SW)
    - przyciski GPIO
    - przyszłościowo: IR, MCP23017, RGB, relays
    """

    def __init__(self, on_rotate=None, on_click=None):
        self.on_rotate = on_rotate
        self.on_click = on_click

        # Wczytaj mapę GPIO
        with open(GPIO_MAP_PATH, "r") as f:
            gpio = json.load(f)

        enc = gpio.get("encoder", {})
        self.pin_a = enc.get("pin_a")
        self.pin_b = enc.get("pin_b")
        self.pin_sw = enc.get("pin_sw")
        self.enabled = enc.get("enabled", False)

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        if self.enabled:
            self._init_encoder()

    # -----------------------------------------
    # ENCODER
    # -----------------------------------------

    def _init_encoder(self):
        GPIO.setup(self.pin_a, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pin_b, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pin_sw, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        self.last_state = GPIO.input(self.pin_a)

        GPIO.add_event_detect(self.pin_a, GPIO.BOTH,
                              callback=self._rotary_callback,
                              bouncetime=2)

        GPIO.add_event_detect(self.pin_sw, GPIO.FALLING,
                              callback=self._button_callback,
                              bouncetime=200)

    def _rotary_callback(self, channel):
        a = GPIO.input(self.pin_a)
        b = GPIO.input(self.pin_b)

        if a != self.last_state:
            if self.on_rotate:
                direction = +1 if b != a else -1
                self.on_rotate(direction)
            self.last_state = a

    def _button_callback(self, channel):
        if self.on_click:
            self.on_click()

    # -----------------------------------------
    # CLEANUP
    # -----------------------------------------

    def cleanup(self):
        GPIO.cleanup()
