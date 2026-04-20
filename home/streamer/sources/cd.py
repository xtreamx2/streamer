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

class CdSource(AudioSource):
    def __init__(self, **kwargs):
        super().__init__(id='cd', name='CD Player', **kwargs)
        
    def start(self):
        log.info("Starting CD playback")
        
    def stop(self):
        log.info("Stopping CD playback")
    SOURCE_ID   = 'sources.cd'
    SOURCE_NAME = 'CD'
    AVAILABLE   = False   # wyszarzone w UI

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
