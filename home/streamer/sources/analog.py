#!/usr/bin/env python3
"""
Źródło: Wejścia analogowe — Phono (RIAA) i Line In (x2).
Hardware: PCM1808 ADC przez I2S → sprzętowy przełącznik 4-kanałowy.

SZKIELET — do zaimplementowania gdy hardware będzie gotowy.
"""

import logging
from .base import AudioSource

log = logging.getLogger(__name__)

# GPIO lub I2C adres przełącznika audio (np. TS3A4751 / PI3USB)
SWITCH_CHANNEL_PHONO = 0
SWITCH_CHANNEL_LINE1 = 1
SWITCH_CHANNEL_LINE2 = 2


class AnalogSource(AudioSource):
    """
    Bazowa klasa dla wejść analogowych przez PCM1808.
    Podklasy: PhonoSource, Line1Source, Line2Source.
    """
    SOURCE_ID   = 'analog'
    SOURCE_NAME = 'Analog'
    AVAILABLE   = True

    SWITCH_CHANNEL = 0   # nadpisz w podklasie

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._gain_db = 0.0

    def activate(self) -> bool:
        log.info(f"[{self.SOURCE_ID}] activate → channel {self.SWITCH_CHANNEL}")
        self._set_switch_channel(self.SWITCH_CHANNEL)
        # TODO: uruchom GStreamer pipeline: alsasrc (PCM1808) → EQ → alsasink
        self._active = True
        self._set_state('active')
        return True

    def deactivate(self):
        log.info(f"[{self.SOURCE_ID}] deactivate")
        # TODO: zatrzymaj GStreamer pipeline
        self._active = False
        self._set_state('stopped')

    def get_status(self) -> dict:
        return {
            'source':  self.SOURCE_ID,
            'state':   self._state,
            'channel': self.SWITCH_CHANNEL,
            'gain_db': self._gain_db,
        }

    def _set_switch_channel(self, channel: int):
        """
        Przełącz sprzętowy multiplekser audio na wybrany kanał.
        TODO: implementacja przez GPIO lub I2C w zależności od układu.
        """
        log.info(f"Audio switch → channel {channel}")
        # Przykład GPIO (RPi.GPIO):
        # GPIO.output(PIN_SEL0, channel & 1)
        # GPIO.output(PIN_SEL1, (channel >> 1) & 1)
        pass


class PhonoSource(AnalogSource):
    """
    Wejście gramofonowe z korektą RIAA.
    Przed ADC: zewnętrzny preamp RIAA.
    EQ GStreamera stosuje dodatkową korekcję jeśli potrzeba.
    """
    SOURCE_ID      = 'phono'
    SOURCE_NAME    = 'Phono (RIAA)'
    SWITCH_CHANNEL = SWITCH_CHANNEL_PHONO


class Line1Source(AnalogSource):
    """Wejście liniowe 1."""
    SOURCE_ID      = 'line1'
    SOURCE_NAME    = 'Line In 1'
    SWITCH_CHANNEL = SWITCH_CHANNEL_LINE1


class Line2Source(AnalogSource):
    """Wejście liniowe 2."""
    SOURCE_ID      = 'line2'
    SOURCE_NAME    = 'Line In 2'
    SWITCH_CHANNEL = SWITCH_CHANNEL_LINE2
