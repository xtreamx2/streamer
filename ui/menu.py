# streamer/ui/menu.py

from ui.eq import EqMenu
from pathlib import Path
import json


EQ_CONFIG = Path(__file__).resolve().parents[1] / "config" / "config-eq.json"


def load_eq():
    if EQ_CONFIG.exists():
        return json.loads(EQ_CONFIG.read_text())
    return {}


class Menu:
    """
    Główne menu streamera:
    - obrót: głośność
    - klik: play/pause lub wejście do EQ
    - długie przytrzymanie: wejście do EQ
    """

    def __init__(self, display, player, volume):
        self.display = display
        self.player = player
        self.volume = volume

        self.volume_level = 50
        self.eq_menu = EqMenu(display)

        self.active_menu = None   # None = ekran główny

        # wyświetl od razu preset EQ
        self.show_main_screen()

    # -------------------------------
    # EKRAN GŁÓWNY
    # -------------------------------

    def show_main_screen(self):
        eq = load_eq()
        preset = eq.get("selected_preset", "FLAT")
        mode = eq.get("mode", "preset")

        if mode.startswith("custom"):
            preset_text = f"EQ: {mode.upper()}"
        else:
            preset_text = f"EQ: {preset}"

        self.display.text(f"Vol {self.volume_level} | {preset_text}")

    # -------------------------------
    # OBSŁUGA OBROTU
    # -------------------------------

    def rotate(self, direction):
        # jeśli jesteśmy w EQ → przekazujemy dalej
        if self.active_menu is self.eq_menu:
            self.eq_menu.rotate(direction)
            return

        # normalnie: regulacja głośności
        self.volume_level = max(0, min(100, self.volume_level + direction))
        self.volume.set(self.volume_level)

        # integracja loudness z głośnością
        self.apply_loudness_dynamic()

        self.show_main_screen()

    # -------------------------------
    # OBSŁUGA KLIKNIĘCIA
    # -------------------------------

    def press(self):
        # jeśli jesteśmy w EQ → przekazujemy dalej
        if self.active_menu is self.eq_menu:
            self.eq_menu.press()
            # jeśli EQ wyszedł do góry
            if self.eq_menu.sub is None:
                self.active_menu = None
                self.show_main_screen()
            return

        # klik na ekranie głównym = PLAY
        self.player.play_radio("http://stream.rcs.revma.com/ypqt40u0x1zuv")
        self.display.text("Playing radio")

    # -------------------------------
    # DŁUGIE PRZYTRZYMANIE = EQ
    # -------------------------------

    def long_press(self):
        self.active_menu = self.eq_menu
        self.eq_menu.enter()
        self.display.text("EQ menu")

    # -------------------------------
    # LOUDNESS DYNAMICZNY
    # -------------------------------

    def apply_loudness_dynamic(self):
        """
        Loudness zależny od głośności:
        - przy 0–30% → mocny
        - przy 30–60% → średni
        - przy 60–100% → minimalny
        """
        eq = load_eq()
        if not eq.get("loudness", {}).get("enabled", False):
            return

        vol = self.volume_level

        if vol < 30:
            strength = 80
        elif vol < 60:
            strength = 40
        else:
            strength = 10

        eq["loudness"]["strength"] = strength
        EQ_CONFIG.write_text(json.dumps(eq, indent=2))
