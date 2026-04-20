#!/usr/bin/env python3
"""
Źródło: S/PDIF (cyfrowe wejście koaksjalne/optyczne).
SZKIELET — do zaimplementowania.
Wymaga: dedykowanego odbiornika S/PDIF (np. CS8416, DIR9001) lub
        karty rozszerzeń z I2S output.
"""

import logging
from .base import AudioSource

log = logging.getLogger(__name__)


class SpdifSource(AudioSource):
    SOURCE_ID   = 'spdif'
    SOURCE_NAME = 'S/PDIF'
    AVAILABLE   = False   # wyszarzone w UI

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sample_rate = None
        self._lock_status = False

    def activate(self) -> bool:
        log.info("[spdif] activate — NOT IMPLEMENTED")
        # TODO:
        # 1. Sprawdź lock odbiornika S/PDIF (GPIO/I2C)
        # 2. Skonfiguruj I2S slave mode dla PCM1808 lub dedykowanego IC
        # 3. Uruchom GStreamer: alsasrc (S/PDIF I2S) → EQ → alsasink
        self._active = True
        self._set_state('error')  # sygnalizuj brak implementacji
        return False

    def deactivate(self):
        self._active = False
        self._set_state('stopped')

    def get_status(self) -> dict:
        return {
            'source':      self.SOURCE_ID,
            'state':       self._state,
            'available':   False,
            'sample_rate': self._sample_rate,
            'lock':        self._lock_status,
            'note':        'Not implemented',
        }
