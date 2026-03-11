#!/usr/bin/env python3
"""
Source Manager — zarządza aktywnym źródłem audio.
Jedno źródło aktywne na raz. Przełączanie: deactivate stare → activate nowe.
"""

import logging
import json
import os
from typing import Optional, Callable, Dict
from sources import (AudioSource, RadioSource, BluetoothSource,
                     PhonoSource, Line1Source, Line2Source, SpdifSource)

log = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')


class SourceManager:
    def __init__(self,
                 alsa_device: str = 'hw:sndrpihifiberry,0',
                 on_state_change: Optional[Callable] = None,
                 on_meta_change:  Optional[Callable] = None):

        self._on_state_change = on_state_change
        self._on_meta_change  = on_meta_change
        self._active: Optional[AudioSource] = None
        self._config = self._load_config()

        common = dict(
            alsa_device     = alsa_device,
            on_state_change = self._handle_state,
            on_meta_change  = self._handle_meta,
        )

        # Instancje wszystkich źródeł
        self._sources: Dict[str, AudioSource] = {
            'radio':     RadioSource(**common),
            'bluetooth': BluetoothSource(**common),
            'phono':     PhonoSource(**common),
            'line1':     Line1Source(**common),
            'line2':     Line2Source(**common),
            'spdif':     SpdifSource(**common),
        }

        # NIE przywracamy źródła w __init__ — robimy to z app.py po pełnej inicjalizacji
        self._last_source = self._config.get('last_source', 'radio')

    # ── Public API ─────────────────────────────────────────────

    def restore_last_source(self):
        """Przywróć ostatnie źródło i ostatnią stację."""
        # Zawsze przywróć głośność
        vol = self._config.get('volume', 75)

        # Wczytaj ostatnią stację (zawsze, nie tylko gdy last_source=radio)
        self._restore_station_url = None
        self._restore_station_name = None
        last_station = self._config.get('last_station_id')
        if last_station:
            import json as _json, os as _os
            stations_path = _os.path.join(_os.path.dirname(__file__), '..', 'radio', 'stations.json')
            try:
                with open(stations_path) as f:
                    data = _json.load(f)
                station = next((s for s in data.get('stations', []) if s['id'] == last_station), None)
                if station:
                    self._restore_station_url  = station['url']
                    self._restore_station_name = station['name']
                    log.info(f"Last station to restore: {station['name']}")
            except Exception as e:
                log.warning(f"Could not load last station: {e}")

        # Przełącz na ostatnie źródło
        self.switch(self._last_source)

        # Ustaw głośność
        for src in self._sources.values():
            src.set_volume(vol)

        # Jeśli radio jest aktywne — odtwarzaj od razu
        if self._active and self._active.SOURCE_ID == 'radio':
            self._play_restored_station()

    def _play_restored_station(self):
        """Odtwórz ostatnią zapisaną stację na radio source."""
        url  = getattr(self, '_restore_station_url',  None)
        name = getattr(self, '_restore_station_name', '')
        radio = self._sources.get('radio')
        if radio and url:
            radio.play(url, name)
            log.info(f"Playing restored station: {name}")

    def switch(self, source_id: str) -> bool:
        """Przełącz na nowe źródło."""
        if source_id not in self._sources:
            log.error(f"Nieznane źródło: {source_id}")
            return False
        if self._active and self._active.SOURCE_ID == source_id:
            log.debug(f"Źródło {source_id} już aktywne")
            return True

        log.info(f"Switch: {self._active_id()} → {source_id}")

        # Zatrzymaj/wznów bluealsa-aplay zależnie od źródła
        import subprocess as _sp
        if source_id == 'bluetooth':
            _sp.run(['sudo', 'systemctl', 'start', 'bluealsa-aplay'], capture_output=True)
            log.info("bluealsa-aplay: start")
        else:
            _sp.run(['sudo', 'systemctl', 'stop', 'bluealsa-aplay'], capture_output=True)
            log.info("bluealsa-aplay: stop")

        # Deaktywuj stare
        if self._active:
            try:
                self._active.deactivate()
            except Exception as e:
                log.error(f"Deactivate error: {e}")

        # Aktywuj nowe
        new_source = self._sources[source_id]
        ok = False
        try:
            ok = new_source.activate()
        except Exception as e:
            log.error(f"Activate error [{source_id}]: {e}")

        if ok:
            self._active = new_source
            # Przywróć głośność i EQ dla tego źródła
            vol = self._config.get('volume', 75)
            eq  = self._config.get('eq', {}).get(source_id, [0]*10)
            new_source.set_volume(vol)
            new_source.set_eq_gains(eq)
            # Zapisz ostatnie źródło
            self._config['last_source'] = source_id
            self._save_config(debounce=True)
            log.info(f"Active: {source_id}")
        else:
            log.error(f"Nie można aktywować: {source_id}")

        return ok

    @property
    def active_source(self) -> Optional[AudioSource]:
        return self._active

    def get_source(self, source_id: str) -> Optional[AudioSource]:
        return self._sources.get(source_id)

    def get_all_status(self) -> dict:
        """Status aktywnego źródła + lista wszystkich z availability."""
        return {
            'active':  self._active_id(),
            'status':  self._active.get_status() if self._active else {},
            'sources': [
                {
                    'id':        sid,
                    'name':      src.SOURCE_NAME,
                    'available': src.AVAILABLE,
                    'active':    (self._active and self._active.SOURCE_ID == sid),
                }
                for sid, src in self._sources.items()
            ],
        }

    def set_volume(self, vol: int):
        """Ustaw głośnosc aktywnego zrodla i zapisz w config."""
        self._config['volume'] = vol
        self._save_config()
        if self._active:
            self._active.set_volume(vol)

    # ── Gain per source ──────────────────────────────────────

    def get_source_gain(self, source_id: str) -> float:
        """Pobierz gain dla danego zrodla w dB (-10..+6)."""
        gains = self._config.get('source_gains', {})
        return float(gains.get(source_id, 0.0))

    def set_source_gain(self, source_id: str, gain_db: float) -> float:
        """Ustaw gain dla danego zrodla (-10..+6 dB) i zastosuj jezeli aktywne."""
        gain_db = max(-10.0, min(6.0, float(gain_db)))
        if 'source_gains' not in self._config:
            self._config['source_gains'] = {}
        self._config['source_gains'][source_id] = gain_db
        self._save_config(debounce=True)
        if self._active and self._active.SOURCE_ID == source_id:
            self._apply_source_gain(self._active, gain_db)
        return gain_db

    def _apply_source_gain(self, source, gain_db: float):
        """Zastosuj gain jako pre-gain (modyfikacja volume elementu GStreamer)."""
        if hasattr(source, 'set_pregain'):
            source.set_pregain(gain_db)

    def autogain_clip(self, source_id: str) -> float:
        """Wywolane przy CLIP — obniz gain o 1dB i zapisz. Zwraca nowy gain."""
        current = self.get_source_gain(source_id)
        if current > -10.0:
            new_gain = max(-10.0, current - 1.0)
            log.info(f"AutoGain CLIP: {source_id} {current:.1f} → {new_gain:.1f} dB")
            return self.set_source_gain(source_id, new_gain)
        return current

    def set_eq(self, source_id: str, gains: list):
        """Ustaw EQ dla danego źródła i zapisz."""
        if len(gains) != 10:
            return
        if 'eq' not in self._config:
            self._config['eq'] = {}
        self._config['eq'][source_id] = gains
        self._save_config(debounce=True)
        src = self._sources.get(source_id)
        if src:
            src.set_eq_gains(gains)

    def get_volume(self) -> int:
        return self._config.get('volume', 75)

    def save_source(self, source_id: str):
        """Zapisz ostatnie aktywne źródło w config."""
        self._config['last_source'] = source_id
        self._save_config()

    def set_config(self, key: str, value):
        """Zapisz dowolny klucz w config (np. last_station_id, loudness)."""
        self._config[key] = value
        self._save_config()

    def get_config(self, key: str, default=None):
        return self._config.get(key, default)

    def get_eq(self, source_id: str) -> list:
        return self._config.get('eq', {}).get(source_id, [0]*10)

    # ── Config ─────────────────────────────────────────────────

    def _load_config(self) -> dict:
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_config(self, debounce: bool = False):
        """Zapisz config na dysk. debounce=True: max raz na 5s."""
        import time
        now = time.monotonic()
        if debounce and hasattr(self, '_last_save') and (now - self._last_save) < 5.0:
            self._dirty = True
            return
        self._dirty = False
        self._last_save = now
        self._do_save()

    def _flush_config(self):
        if getattr(self, '_dirty', False):
            self._dirty = False
            self._do_save()

    def _do_save(self):
        try:
            # Odczytaj aktualny config żeby nie nadpisać innych kluczy
            try:
                with open(CONFIG_PATH) as f:
                    current = json.load(f)
            except Exception:
                current = {}
            current.update(self._config)
            with open(CONFIG_PATH, 'w') as f:
                json.dump(current, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Config save error: {e}")

    # ── Callbacks ──────────────────────────────────────────────

    def _handle_state(self, source_id: str, state: str):
        if self._on_state_change:
            self._on_state_change(source_id, state)

    def _handle_meta(self, source_id: str, meta: dict):
        if self._on_meta_change:
            self._on_meta_change(source_id, meta)

    def _active_id(self) -> Optional[str]:
        return self._active.SOURCE_ID if self._active else None
