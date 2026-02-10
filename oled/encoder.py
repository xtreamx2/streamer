#!/usr/bin/env python3
import time
import threading
import RPi.GPIO as GPIO


# ==========================
# KONFIGURACJA PINÓW
# ==========================

PIN_A = 24      # CLK
PIN_B = 23      # DT
PIN_SW = 13     # SW (przycisk)

DEBOUNCE_ROTATE = 0.002     # 2 ms
DEBOUNCE_CLICK = 0.05       # 50 ms
HOLD_TIME = 1.2             # przytrzymanie 1.2 sekundy


# ==========================
# KLASA ENKODERA
# ==========================

class Encoder:
    def __init__(self, on_rotate=None, on_click=None, on_hold=None):
        """
        on_rotate(direction)  → direction = +1 / -1
        on_click()            → klik
        on_hold()             → przytrzymanie
        """

        self.on_rotate = on_rotate
        self.on_click = on_click
        self.on_hold = on_hold

        self.last_state_A = 1
        self.last_button_state = 1
        self.button_down_time = None
        self.hold_fired = False

        self.running = True

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_A, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(PIN_B, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(PIN_SW, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # wątek do obsługi enkodera
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    # ==========================
    # PĘTLA GŁÓWNA ENKODERA
    # ==========================

    def _loop(self):
        while self.running:
            self._check_rotation()
            self._check_button()
            time.sleep(0.001)  # 1 ms

    # ==========================
    # ROTACJA
    # ==========================

    def _check_rotation(self):
        state_A = GPIO.input(PIN_A)
        if state_A != self.last_state_A:
            # zmiana stanu = impuls
            time.sleep(DEBOUNCE_ROTATE)

            state_B = GPIO.input(PIN_B)

            if state_A == 0:  # impuls w dół
                if state_B == 1:
                    direction = +1
                else:
                    direction = -1

                if self.on_rotate:
                    self.on_rotate(direction)

        self.last_state_A = state_A

    # ==========================
    # PRZYCISK
    # ==========================

    def _check_button(self):
        state = GPIO.input(PIN_SW)

        # przycisk wciśnięty
        if state == 0 and self.last_button_state == 1:
            self.button_down_time = time.time()
            self.hold_fired = False
            time.sleep(DEBOUNCE_CLICK)

        # przycisk trzymany
        if state == 0 and self.button_down_time:
            if not self.hold_fired and (time.time() - self.button_down_time) >= HOLD_TIME:
                self.hold_fired = True
                if self.on_hold:
                    self.on_hold()

        # przycisk puszczony
        if state == 1 and self.last_button_state == 0:
            if not self.hold_fired:
                if self.on_click:
                    self.on_click()
            self.button_down_time = None
            time.sleep(DEBOUNCE_CLICK)

        self.last_button_state = state

    # ==========================
    # ZATRZYMANIE
    # ==========================

    def stop(self):
        self.running = False
        time.sleep(0.05)
        GPIO.cleanup()
