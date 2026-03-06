# streamer/ui/eq.py

import json
from pathlib import Path

EQ_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config-eq.json"


def load_eq_config():
    if not EQ_CONFIG_PATH.exists():
        return {}
    return json.loads(EQ_CONFIG_PATH.read_text())


def save_eq_config(cfg):
    EQ_CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


class EqMenu:
    def __init__(self, ui_state):
        self.state = ui_state
        self.cfg = load_eq_config()
        self.items = [
            "Tryb EQ",
            "Presety",
            "Custom 2‑band",
            "Custom 5‑band",
            "Loudness",
        ]
        self.index = 0
        self.submode = None      # np. "mode", "presets", "custom2", "custom5", "loudness"
        self.edit_band = None    # np. "bass", "60", "230" itd.

    # wywoływane przy wejściu do menu EQ
    def enter(self):
        self.cfg = load_eq_config()
        self.index = 0
        self.submode = None
        self.edit_band = None

    # rysowanie na OLED – dopasuj do swojego display.py
    def render(self, draw):
        # uproszczone – tylko nazwy pozycji
        # w praktyce użyjesz swojego systemu layoutów
        title = "EQ"
        current = self.items[self.index]
        # narysuj title + current + np. aktualny preset / tryb
        # ...

    # obrót enkodera
    def on_rotate(self, direction):
        if self.submode is None:
            # poruszanie się po głównym menu EQ
            self.index = (self.index + direction) % len(self.items)
            return

        # w trybach edycji – zmiana wartości
        if self.submode.startswith("custom2"):
            profile_key = self.submode[-1]  # "A" lub "B"
            band = self.edit_band
            step = 1 * direction
            val = self.cfg["custom2_profiles"][profile_key][band]
            val = max(-12, min(12, val + step))
            self.cfg["custom2_profiles"][profile_key][band] = val
            save_eq_config(self.cfg)
            return

        if self.submode.startswith("custom5"):
            profile_key = self.submode[-1]  # "A" lub "B"
            band = self.edit_band
            step = 1 * direction
            val = self.cfg["custom5_profiles"][profile_key][band]
            val = max(-12, min(12, val + step))
            self.cfg["custom5_profiles"][profile_key][band] = val
            save_eq_config(self.cfg)
            return

        if self.submode == "preset_select":
            presets = list(self.cfg["presets"].keys())
            idx = presets.index(self.cfg["selected_preset"])
            idx = (idx + direction) % len(presets)
            self.cfg["selected_preset"] = presets[idx]
            save_eq_config(self.cfg)
            return

        if self.submode == "loudness":
            step = 5 * direction
            val = self.cfg["loudness"]["strength"]
            val = max(0, min(100, val + step))
            self.cfg["loudness"]["strength"] = val
            save_eq_config(self.cfg)
            return

    # klik enkodera
    def on_click(self):
        # poziom główny
        if self.submode is None:
            current = self.items[self.index]

            if current == "Tryb EQ":
                # przełączanie trybu: preset / custom2A / custom2B / custom5A / custom5B
                modes = ["preset", "custom2A", "custom2B", "custom5A", "custom5B"]
                idx = modes.index(self.cfg["mode"])
                idx = (idx + 1) % len(modes)
                self.cfg["mode"] = modes[idx]
                save_eq_config(self.cfg)
                return

            if current == "Presety":
                self.submode = "preset_select"
                return

            if current == "Custom 2‑band":
                # wejście w edycję – najpierw wybór profilu A/B, potem Bass/Treble
                # dla uproszczenia: od razu edytujemy Bass profilu A
                self.submode = "custom2A"
                self.edit_band = "bass"
                return

            if current == "Custom 5‑band":
                self.submode = "custom5A"
                self.edit_band = "60"
                return

            if current == "Loudness":
                # klik = toggle on/off, obrót = zmiana siły
                self.cfg["loudness"]["enabled"] = not self.cfg["loudness"]["enabled"]
                save_eq_config(self.cfg)
                # drugi klik może wejść w edycję siły
                if self.cfg["loudness"]["enabled"]:
                    self.submode = "loudness"
                return

        # jeśli jesteśmy w submode – klik = wyjście poziom wyżej
        self.submode = None
        self.edit_band = None
        save_eq_config(self.cfg)
