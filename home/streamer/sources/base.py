#!/usr/bin/env python3
"""
Bazowa klasa źródła audio.
Każde źródło (radio, bluetooth, analog, digital) dziedziczy po AudioSource.
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable
import logging

log = logging.getLogger(__name__)


class AudioSource(ABC):
    """
    Abstrakcyjna klasa bazowa dla źródeł audio.
    
    Każde źródło musi implementować: activate(), deactivate(), get_status().
    Opcjonalnie: set_volume(), set_eq_gains() jeśli obsługuje własny DSP.
    """

    SOURCE_ID: str = 'base'    # nadpisz w podklasie: 'radio', 'bluetooth', itd.
    SOURCE_NAME: str = 'Base'
    AVAILABLE: bool = True     # False = wyświetlaj jako wyszarzone (np. S/PDIF szkielet)

    def __init__(self,
                 alsa_device: str = 'hw:sndrpihifiberry,0',
                 on_state_change: Optional[Callable] = None,
                 on_meta_change: Optional[Callable] = None):
        self.alsa_device     = alsa_device
        self.on_state_change = on_state_change   # fn(source_id, state_str)
        self.on_meta_change  = on_meta_change    # fn(source_id, meta_dict)
        self._active         = False
        self._state          = 'stopped'

    # ── lifecycle ──────────────────────────────────────────────

    @abstractmethod
    def activate(self) -> bool:
        """Aktywuj źródło. Zwraca True jeśli sukces."""
        ...

    @abstractmethod
    def deactivate(self):
        """Deaktywuj źródło, zwolnij zasoby audio."""
        ...

    @abstractmethod
    def get_status(self) -> dict:
        """Zwróć słownik ze stanem źródła."""
        ...

    # ── optional overrides ─────────────────────────────────────

    def set_volume(self, vol: int):
        """Ustaw głośność 0-100 (implementacja w audio_engine przez source_manager)."""
        pass

    def set_eq_gains(self, gains: list):
        """Ustaw 10-pasmowy EQ (implementacja w audio_engine)."""
        pass

    # ── helpers ────────────────────────────────────────────────

    @property
    def active(self) -> bool:
        return self._active

    @property
    def state(self) -> str:
        return self._state

    def _set_state(self, state: str):
        if state != self._state:
            self._state = state
            log.debug(f"[{self.SOURCE_ID}] state → {state}")
            if self.on_state_change:
                self.on_state_change(self.SOURCE_ID, state)

    def _set_meta(self, meta: dict):
        if self.on_meta_change:
            self.on_meta_change(self.SOURCE_ID, meta)
