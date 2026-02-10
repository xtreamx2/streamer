#!/usr/bin/env python3
import time
import json
import signal
import sys
from dataclasses import dataclass, field
from pathlib import Path

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306

from PIL import ImageFont
from mpd import MPDClient

from encoder import Encoder


# ================== ŚCIEŻKI ==================

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR.parent / "config"
CONFIG_DIR.mkdir(exist_ok=True)

CONFIG_OLED = CONFIG_DIR / "config-oled.json"
CONFIG_RADIO = CONFIG_DIR / "config-radio.json"

FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
FONT_SMALL = ImageFont.truetype(str(FONT_PATH), 10)
FONT_NORMAL = ImageFont.truetype(str(FONT_PATH), 12)


# ================== KONFIG DOMYŚLNY ==================

DEFAULT_OLED_CONFIG = {
    "eq_mode": "5band",
    "screensaver_dim_after": 10,
    "screensaver_dim_level": 10,
    "screensaver_off_after": 60,
    "brightness_default": 50
}

DEFAULT_RADIO_CONFIG = {
    "stations": [
        {
            "name": "Radio Paradise (FLAC)",
            "url": "http://stream.radioparadise.com/flac",
            "favorite": True,
            "tags": ["hires", "flac"]
        }
    ]
}


# ================== DANE / STANY ==================

@dataclass
class NowPlaying:
    source: str = "radio"
    artist: str = ""
    title: str = ""
    bitrate_kbps: int = 0
    bit_depth: int = 16
    sample_rate: int = 44100
    volume: int = 42
    playing: bool = False


@dataclass
class ScreenState:
    screen_off: bool = False
    mode: str = "main"
    menu_path: list = field(default_factory=list)
    last_input_time: float = field(default_factory=time.time)

    scroll_offset_line1: int = 0
    scroll_offset_line2: int = 0
    last_scroll_time: float = field(default_factory=time.time)

    selected_index: int = 0
    scroll_offset: int = 0


@dataclass
class Settings:
    eq_mode: str = "5band"
    screensaver_dim_after: int = 10
    screensaver_dim_level: int = 10
    screensaver_off_after: int = 60
    brightness_default: int = 50


# ================== PARAMETRY OLED ==================

I2C_PORT = 1
I2C_ADDRESS = 0x3C

FPS = 20
SCROLL_SPEED = 0.3
MENU_TIMEOUT = 10


# ================== KONFIG / RADIO ==================

def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        path.write_text(json.dumps(default, indent=2), encoding="utf-8")
        return default.copy()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default.copy()


def save_json(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_oled_config() -> Settings:
    cfg = load_json(CONFIG_OLED, DEFAULT_OLED_CONFIG)
    return Settings(
        eq_mode=cfg.get("eq_mode", "5band"),
        screensaver_dim_after=int(cfg.get("screensaver_dim_after", 10)),
        screensaver_dim_level=int(cfg.get("screensaver_dim_level", 10)),
        screensaver_off_after=int(cfg.get("screensaver_off_after", 60)),
        brightness_default=int(cfg.get("brightness_default", 50)),
    )


def load_radio_stations():
    data = load_json(CONFIG_RADIO, DEFAULT_RADIO_CONFIG)
    return data.get("stations", [])


def get_favorite_stations():
    stations = load_radio_stations()
    return [s for s in stations if s.get("favorite")]


# ================== OLED INIT ==================

def init_device():
    serial = i2c(port=I2C_PORT, address=I2C_ADDRESS)
    device = ssd1306(serial, rotate=0)
    return device


# ================== TEKST / FORMAT ==================

def normalize(text: str) -> str:
    return text or ""


def get_source_icon(np: NowPlaying) -> str:
    return "▶" if np.playing else "⏸"


def format_bitrate(np: NowPlaying) -> str:
    return f"{np.bitrate_kbps}k" if np.bitrate_kbps else ""


def format_bitdepth(np: NowPlaying) -> str:
    sr_khz = int(np.sample_rate / 1000)
    return f"{np.bit_depth}/{sr_khz}"


def is_hq(np: NowPlaying) -> bool:
    if not np.playing:
        return False
    return np.bit_depth >= 16 and np.sample_rate >= 44100


def is_hires(np: NowPlaying) -> bool:
    if not np.playing:
        return False
    return np.bit_depth >= 24 or np.sample_rate > 48000


# ================== RYSOWANIE ==================

def draw_startup_animation(device):
    w, h = device.width, device.height
    steps = 10

    logo_lines = [
        "  _____ _                             ",
        " / ____| |                            ",
        "| (___ | |_ _ __ ___  _ __ ___  _   _ ",
        " \\___ \\| __| '__/ _ \\| '_ ` _ \\| | | |",
        " ____) | |_| | | (_) | | | | | | |_| |",
        "|_____/ \\__|_|  \\___/|_| |_| |_|\\__,_|",
        "           STREAMER                    ",
    ]

    for i in range(steps):
        with canvas(device) as draw:
            draw.rectangle((0, 0, w, h), outline=0, fill=0)
            max_line = int(len(logo_lines) * (i + 1) / steps)
            y = 0
            for line in logo_lines[:max_line]:
                draw.text((0, y), line[:21], font=FONT_SMALL, fill=255)
                y += 8
        time.sleep(0.1)

def draw_edit_screen(device, state: ScreenState):
    with canvas(device) as draw:
        draw.text((0, 0), f"Ustaw: {state.edit_key}", font=FONT_NORMAL, fill=255)
        draw.text((0, 20), f"{state.edit_value}", font=FONT_NORMAL, fill=255)
        draw.text((0, 40), "Klik = Zapis", font=FONT_SMALL, fill=255)

def draw_volume_icon(draw, x, y, height, width, volume):
    draw.line((x, y, x, y + height), fill=255)
    mid = y + height // 2
    draw.line((x, mid, x + width, mid), fill=255)

    fill_width = int(width * (volume / 100.0))
    if fill_width > 0:
        draw.line((x, mid, x + fill_width, mid), fill=255)

def scroll_text(text: str, width_chars: int, offset: int) -> str:
    text = normalize(text)
    if len(text) <= width_chars:
        return text.ljust(width_chars)
    padded = text + "   "
    start = offset % len(padded)
    return (padded + padded)[start:start + width_chars]


def draw_main_screen(device, np: NowPlaying, state: ScreenState):
    w, h = device.width, device.height
    chars_per_line = 16

    icon = get_source_icon(np)
    hq = is_hq(np)
    hires = is_hires(np)

    # RADIO
    if np.source == "radio":
        if np.artist:
            line1_text = np.artist
            line2_text = np.title
        else:
            line1_text = np.title
            line2_text = ""
    else:
        line1_text = np.title or ""
        line2_text = f"{format_bitrate(np)} {format_bitdepth(np)}".strip()

    # przewijanie
    now = time.time()
    if now - state.last_scroll_time > SCROLL_SPEED:
        state.scroll_offset_line1 += 1
        state.scroll_offset_line2 += 1
        state.last_scroll_time = now

    line1 = scroll_text(line1_text, chars_per_line - 2, state.scroll_offset_line1)
    line2 = scroll_text(line2_text, chars_per_line, state.scroll_offset_line2)

    bitinfo = f"{np.bit_depth}bit / {np.sample_rate//1000}kHz"

    with canvas(device) as draw:
        draw.text((0, 0), icon, font=FONT_NORMAL, fill=255)
        draw.text((14, 0), line1, font=FONT_NORMAL, fill=255)

        draw.text((0, 14), line2, font=FONT_NORMAL, fill=255)

        draw.text((0, 26), bitinfo, font=FONT_SMALL, fill=255)

        # HQ / HiRes
        if hires:
            draw.text((w - 26, 14), "HiRes", font=FONT_SMALL, fill=255)
        elif hq:
            draw.text((w - 20, 14), "HQ", font=FONT_SMALL, fill=255)

        # ikona głośności
        draw_volume_icon(draw, 0, h - 12, 10, w - 40, np.volume)
        draw.text((w - 30, h - 12), f"{np.volume}%", font=FONT_SMALL, fill=255)


# ================== MENU ==================

def build_menu_structure():
    fav_names = [s["name"] for s in get_favorite_stations()]
    if not fav_names:
        fav_names = ["(brak ulubionych)"]
    return {
        "root": ["Ustawienia", "Ulubione stacje", "Stacje radiowe", "Źródło", "ESC"],
        "Ustawienia": ["Filtry EQ", "Wygaszacz", "Ekran", "ESC"],
        "Filtry EQ": ["EQ 5-pasmowy", "EQ 2-pasmowy", "ESC"],
        "Wygaszacz": ["Czas do przyciemnienia", "Jasność po przyciemnieniu", "Czas do wygaszenia", "ESC"],
        "Ekran": ["Jasność domyślna", "ESC"],
        "Stacje radiowe": [s["name"] for s in load_radio_stations()] + ["ESC"],
        "Ulubione stacje": fav_names + ["ESC"],
        "Źródło": ["Radio", "Pliki", "Bluetooth (niedostępne)", "ESC"],
    }


MENU_STRUCTURE = build_menu_structure()


def current_menu_items(state: ScreenState):
    if not state.menu_path:
        return MENU_STRUCTURE["root"]
    return MENU_STRUCTURE.get(state.menu_path[-1], ["ESC"])


def draw_menu(device, state: ScreenState):
    items = current_menu_items(state)
    title = state.menu_path[-1] if state.menu_path else "MENU"

    visible = 2

    if state.selected_index < state.scroll_offset:
        state.scroll_offset = state.selected_index
    elif state.selected_index >= state.scroll_offset + visible:
        state.scroll_offset = state.selected_index - visible + 1

    with canvas(device) as draw:
        draw.text((0, 0), title[:16], font=FONT_NORMAL, fill=255)

        for i in range(visible):
            idx = state.scroll_offset + i
            if idx >= len(items):
                break
            prefix = "> " if idx == state.selected_index else "  "
            draw.text((0, 14 + i * 12), prefix + items[idx][:14], font=FONT_NORMAL, fill=255)


# ================== MPD ==================

def init_mpd():
    client = MPDClient()
    client.timeout = 2
    client.idletimeout = None
    try:
        client.connect("localhost", 6600)
    except Exception:
        client = None
    return client


def update_now_playing_from_mpd(client: MPDClient | None, np: NowPlaying):
    if client is None:
        return

    try:
        status = client.status()
        song = client.currentsong()

        np.playing = (status.get("state") == "play")

        # głośność z MPD
        if "volume" in status:
            try:
                np.volume = int(status["volume"])
            except ValueError:
                pass

        # audio format
        if "audio" in status:
            parts = status["audio"].split(":")
            if len(parts) >= 2:
                try:
                    np.sample_rate = int(parts[0])
                    np.bit_depth = int(parts[1])
                except ValueError:
                    pass

        # bitrate
        if "bitrate" in status:
            try:
                np.bitrate_kbps = int(status["bitrate"])
            except ValueError:
                pass

        file_path = song.get("file", "")

        # źródło
        if file_path.startswith("http"):
            np.source = "radio"
        elif file_path.startswith("bluetooth:"):
            np.source = "bt"
        else:
            np.source = "file"

        # RADIO — NAZWA STACJI
        if np.source == "radio":
            stations = load_radio_stations()
            for s in stations:
                if s["url"] in file_path:
                    np.title = s["name"]
                    break
            else:
                np.title = song.get("title", file_path)

            # METADANE STREAMU: "Artist - Title"
            stream_title = song.get("title", "")
            if " - " in stream_title:
                artist, title = stream_title.split(" - ", 1)
                np.artist = artist
                np.title = title
            else:
                np.artist = ""
            return

        # PLIKI
        np.title = song.get("title", file_path)
        np.artist = song.get("artist", "")

    except Exception:
        pass


def play_station_by_name(client: MPDClient | None, name: str):
    if client is None:
        return
    stations = load_radio_stations()
    for s in stations:
        if s["name"] == name:
            try:
                client.clear()
                client.add(s["url"])
                client.play()
            except Exception:
                pass
            break


# ================== ENKODER ==================

def on_encoder_rotate(direction: int, np: NowPlaying, state: ScreenState, client: MPDClient | None):
    state.last_input_time = time.time()

    if state.mode == "edit":
        state.edit_value = max(0, min(255, state.edit_value + direction))
        return
    if state.mode == "main":
        new_vol = max(0, min(100, np.volume + direction))
        if client:
            try:
                client.setvol(new_vol)
            except:
                pass
        np.volume = new_vol
    elif state.mode == "menu":
        items = current_menu_items(state)
        state.selected_index = max(0, min(len(items) - 1, state.selected_index + direction))

def handle_menu_action(choice: str, np: NowPlaying, state: ScreenState, settings: Settings, client: MPDClient | None):
    if choice == "Radio":
        np.source = "radio"
    elif choice == "Pliki":
        np.source = "file"
    elif choice == "Bluetooth (niedostępne)":
        pass
    elif choice == "EQ 5-pasmowy":
        settings.eq_mode = "5band"
        save_json(CONFIG_OLED, settings.__dict__)
    elif choice == "EQ 2-pasmowy":
        settings.eq_mode = "2band"
        save_json(CONFIG_OLED, settings.__dict__)
    elif choice in [s["name"] for s in get_favorite_stations()]:
        play_station_by_name(client, choice)
    elif choice in [s["name"] for s in load_radio_stations()]:
        play_station_by_name(client, choice)
    elif choice == "Czas do przyciemnienia":
        state.mode = "edit"
        state.edit_key = "screensaver_dim_after"
        state.edit_value = settings.screensaver_dim_after
        return

    elif choice == "Jasność po przyciemnieniu":
        state.mode = "edit"
        state.edit_key = "screensaver_dim_level"
        state.edit_value = settings.screensaver_dim_level
        return

    elif choice == "Czas do wygaszenia":
        state.mode = "edit"
        state.edit_key = "screensaver_off_after"
        state.edit_value = settings.screensaver_off_after
        return

    elif choice == "Jasność domyślna":
        state.mode = "edit"
        state.edit_key = "brightness_default"
        state.edit_value = settings.brightness_default
        return

def on_encoder_click(np: NowPlaying, state: ScreenState, settings: Settings, client: MPDClient | None):

        # jeśli ekran jest wygaszony → klik tylko wybudza
    if state.screen_off:
        state.last_input_time = time.time()
        state.screen_off = False
        return

    state.last_input_time = time.time()

    if state.mode == "edit":
        setattr(settings, state.edit_key, state.edit_value)
        save_json(CONFIG_OLED, settings.__dict__)
        state.mode = "menu"
        return
    if state.mode == "main":
        if client:
            if np.playing:
                client.pause(1)
            else:
                client.pause(0)
        np.playing = not np.playing
        return

    items = current_menu_items(state)
    if not items:
        return

    choice = items[state.selected_index]

    if choice == "ESC":
        if state.menu_path:
            state.menu_path.pop()
        else:
            state.mode = "main"
        state.selected_index = 0
        state.scroll_offset = 0
        return

    if choice in MENU_STRUCTURE:
        state.menu_path.append(choice)
        state.selected_index = 0
        state.scroll_offset = 0
        return

    handle_menu_action(choice, np, state, settings, client)


def on_encoder_hold(np: NowPlaying, state: ScreenState):
    state.last_input_time = time.time()

    if state.mode == "main":
        state.mode = "menu"
        state.menu_path = []
        state.selected_index = 0
        state.scroll_offset = 0

    elif state.mode == "menu":
        if state.menu_path:
            state.menu_path.pop()
        else:
            state.mode = "main"
        state.selected_index = 0
        state.scroll_offset = 0


# ================== PĘTLA GŁÓWNA ==================

running = True


def signal_handler(sig, frame):
    global running
    running = False


def main():
    global running

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    device = init_device()
    settings = load_oled_config()
    np = NowPlaying()
    state = ScreenState()
    client = init_mpd()

    draw_startup_animation(device)

    enc = Encoder(
        on_rotate=lambda d: on_encoder_rotate(d, np, state, client),
        on_click=lambda: on_encoder_click(np, state, settings, client),
        on_hold=lambda: on_encoder_hold(np, state)
    )

    while running:
        now = time.time()
        inactive = now - state.last_input_time

        update_now_playing_from_mpd(client, np)


        # soft-dimming
        if inactive > settings.screensaver_off_after:
            state.screen_off = True
            with canvas(device) as draw:
                draw.rectangle((0, 0, device.width, device.height), outline=0, fill=0)
            time.sleep(0.1)
            continue
        else:
            state.screen_off = False

        if inactive > settings.screensaver_dim_after:
            # soft dimming (10%)
            try:
                device.contrast(int(255 * (settings.screensaver_dim_level / 100.0)))
            except Exception:
                pass
        else:
            # jasność domyślna
            try:
                device.contrast(int(255 * (settings.brightness_default / 100.0)))
            except Exception:
                pass

        # timeout menu
        if state.mode == "menu" and inactive > MENU_TIMEOUT:
            state.mode = "main"

        # rysowanie ekranu
        if state.mode == "main":
            draw_main_screen(device, np, state)
        elif state.mode == "menu":
            draw_menu(device, state)
        elif state.mode == "edit":
            draw_edit_screen(device, state)

        time.sleep(1.0 / FPS)

    enc.stop()
    sys.exit(0)


if __name__ == "__main__":
    main()
