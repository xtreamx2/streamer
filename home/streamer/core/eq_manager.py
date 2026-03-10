#!/usr/bin/env python3
"""
EQ Manager — zarządza nastawnymi 10-pasm EQ per źródło.
Predefiniowane presety, zapis/odczyt z config.json.
"""

import json
import os
import logging

log = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')

EQ_BANDS = ['31Hz','63Hz','125Hz','250Hz','500Hz','1kHz','2kHz','4kHz','8kHz','16kHz']

PRESETS = {
    'flat':     [ 0,  0,  0,  0,  0,  0,  0,  0,  0,  0],
    'bass':     [ 6,  5,  4,  2,  0,  0,  0,  0,  0,  0],
    'treble':   [ 0,  0,  0,  0,  0,  1,  2,  4,  5,  6],
    'vocal':    [-1, -1,  0,  2,  4,  4,  3,  1,  0, -1],
    'loudness': [ 4,  2,  0,  0,  0,  0,  0,  1,  2,  3],
    'pop':      [-1,  0,  2,  3,  2,  0, -1,  0,  1,  2],
    'rock':     [ 3,  2,  0, -1, -1,  1,  3,  4,  4,  3],
    'jazz':     [ 3,  2,  0,  2,  3,  3,  2,  1,  2,  3],
    'classical': [ 0,  0,  0,  0,  0,  0, -2, -2, -2, -3],
}

SOURCE_DEFAULTS = {
    'radio':     [ 0,  2,  3,  2,  0, -1,  0,  1,  2,  1],
    'bluetooth': [ 0,  0,  0,  0,  0,  0,  0,  0,  0,  0],
    'phono':     [ 3,  2,  1,  0,  0,  0, -1, -1,  0,  1],
    'line1':     [ 0,  0,  0,  0,  0,  0,  0,  0,  0,  0],
    'line2':     [ 0,  0,  0,  0,  0,  0,  0,  0,  0,  0],
    'spdif':     [ 0,  0,  0,  0,  0,  0,  0,  0,  0,  0],
}


class EQManager:
    def __init__(self):
        self._eq = self._load()

    def get(self, source_id: str) -> list:
        return self._eq.get(source_id, SOURCE_DEFAULTS.get(source_id, [0]*10))[:]

    def set(self, source_id: str, gains: list) -> list:
        if len(gains) != 10:
            raise ValueError("gains must have 10 elements")
        clamped = [max(-24.0, min(12.0, g)) for g in gains]
        self._eq[source_id] = clamped
        self._save()
        return clamped

    def set_band(self, source_id: str, band: int, gain: float) -> list:
        gains = self.get(source_id)
        gains[band] = max(-24.0, min(12.0, gain))
        return self.set(source_id, gains)

    def apply_preset(self, source_id: str, preset_name: str) -> list:
        if preset_name not in PRESETS:
            raise ValueError(f"Unknown preset: {preset_name}. Available: {list(PRESETS)}")
        return self.set(source_id, PRESETS[preset_name][:])

    def reset(self, source_id: str) -> list:
        return self.set(source_id, SOURCE_DEFAULTS.get(source_id, [0]*10)[:])

    def get_presets(self) -> dict:
        return {name: gains[:] for name, gains in PRESETS.items()}

    def get_band_names(self) -> list:
        return EQ_BANDS[:]

    # ── Persistence ────────────────────────────────────────────

    def _load(self) -> dict:
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f).get('eq', {})
        except Exception:
            return {}

    def _save(self):
        try:
            try:
                with open(CONFIG_PATH) as f:
                    cfg = json.load(f)
            except Exception:
                cfg = {}
            cfg['eq'] = self._eq
            with open(CONFIG_PATH, 'w') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"EQ save error: {e}")
