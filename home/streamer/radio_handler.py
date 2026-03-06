#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

RADIO_DIR = Path.home() / "streamer" / "radio"
STATIONS_FILE = RADIO_DIR / "stations.json"
FAVORITES_FILE = RADIO_DIR / "favorites.json"
print(RADIO_DIR)

def ensure_radio_dir():
    """Tworzy katalog, ale NIE nadpisuje istniejących plików!"""
    RADIO_DIR.mkdir(parents=True, exist_ok=True)
    
    # Tylko jeśli plik NIE istnieje – stwórz szablon
    if not STATIONS_FILE.exists():
        default = {
            "version": "1.0",
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "stations": [
                {"id": "radiozet", "name": "Radio Zet", "url": "https://r.dcs.redcdn.pl/sc/o2/Eurozet/live/audio.livx", "genre": "pop", "enabled": True},
                {"id": "rmffm", "name": "RMF FM", "url": "https://rs102-krk.rmfstream.pl/RMFFM48", "genre": "pop", "enabled": True},
                {"id": "tokfm", "name": "TOK FM", "url": "https://stream.tokfm.pl/tokfm.mp3", "genre": "news", "enabled": True}
            ]
        }
        with open(STATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2, ensure_ascii=False)
    
    if not FAVORITES_FILE.exists():
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "favorites": []}, f, indent=2)

def load_stations():
    """Ładuje listę stacji z JSON"""
    ensure_radio_dir()
    try:
        with open(STATIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # DEBUG: print to console (usuń po naprawie)
            print(f"[DEBUG] Loaded {len(data.get('stations', []))} stations from {STATIONS_FILE}")
            return data
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in {STATIONS_FILE}: {e}")
        return {"version": "1.0", "stations": []}
    except FileNotFoundError:
        print(f"[ERROR] File not found: {STATIONS_FILE}")
        return {"version": "1.0", "stations": []}

def save_stations(data):
    ensure_radio_dir()
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    with open(STATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_favorites():
    ensure_radio_dir()
    try:
        with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"version": "1.0", "favorites": []}

def save_favorites(data):
    ensure_radio_dir()
    with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def add_station(name, url, **kwargs):
    import hashlib
    data = load_stations()
    station_id = hashlib.md5(f"{name}{url}".encode()).hexdigest()[:8]
    station = {
        "id": station_id,
        "name": name,
        "url": url,
        "enabled": True,
        **kwargs
    }
    data["stations"].append(station)
    save_stations(data)
    return station_id

def remove_station(station_id):
    data = load_stations()
    data["stations"] = [s for s in data["stations"] if s["id"] != station_id]
    save_stations(data)

def toggle_favorite(station_id, add=True):
    fav = load_favorites()
    if add:
        if station_id not in fav["favorites"]:
            fav["favorites"].append(station_id)
    else:
        if station_id in fav["favorites"]:
            fav["favorites"].remove(station_id)
    save_favorites(fav)

def get_enabled_stations():
    data = load_stations()
    return [s for s in data["stations"] if s.get("enabled", True)]

def get_favorites():
    fav = load_favorites()
    stations = {s["id"]: s for s in load_stations()["stations"]}
    return [stations[sid] for sid in fav["favorites"] if sid in stations]

def get_station_by_id(station_id):
    for s in load_stations()["stations"]:
        if s["id"] == station_id:
            return s
    return None
