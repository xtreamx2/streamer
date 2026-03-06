#!/usr/bin/env python3
# ========================================
# 🎵 Tom's Streamer Audio v0.9.2
# ========================================

from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO, emit
import os
import yaml
import subprocess
import re
import mpd
import time
import numpy as np
from typing import Optional, Dict, Any
from radio_handler import (
    load_stations, save_stations, add_station, remove_station,
    get_enabled_stations, get_favorites, get_station_by_id,
    toggle_favorite
)
from vu_handler import get_vu_data

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
mpd_client = None

# Używamy realnego systemowego configu Camilli z maliny.
CAMILLA_CONFIG = '/etc/camilladsp/config.yml'

# Per-client VU mode (Socket.IO sid -> 'vu' | 'spectrum')
_client_vu_mode: Dict[str, str] = {}

# ===== FUNCJE POMOCNICZE =====
def get_available_filters():
    """Pobiera nazwy wszystkich dostępnych filtrów."""
    try:
        with open(CAMILLA_CONFIG, 'r') as f:
            data = yaml.safe_load(f)

        filters = []
        if 'filters' in data and isinstance(data['filters'], dict):
            for name in data['filters'].keys():
                if isinstance(name, str):
                    current_gain = 0.0
                    if 'parameters' in data['filters'][name] and 'gain' in data['filters'][name]['parameters']:
                        current_gain = float(data['filters'][name]['parameters']['gain'])
                    filters.append({'name': name, 'current_gain': current_gain})
        def _sort_key(item):
            n = item["name"]
            if n == "bass":
                return (0, n)
            if n == "treble":
                return (1, n)
            return (2, n)
        return sorted(filters, key=_sort_key)
    except Exception as e:
        print(f"Error reading filters: {e}")
        return []

def update_eq_yaml(filter_name: str, gain: float) -> bool:
    """Zmienia gain filtra w YAML i zapisuje config.

    Uwaga: zapis przez YAML może zmienić formatowanie pliku, ale jest stabilny
    i dużo mniej podatny na błędy niż manipulacja tekstem.
    """
    try:
        with open(CAMILLA_CONFIG, "r") as f:
            config = yaml.safe_load(f) or {}

        filters = config.get("filters")
        if not isinstance(filters, dict) or filter_name not in filters:
            print(f"Filter '{filter_name}' not found!")
            return False

        params = filters.get(filter_name, {}).get("parameters")
        if not isinstance(params, dict):
            filters[filter_name]["parameters"] = {}
            params = filters[filter_name]["parameters"]

        params["gain"] = float(gain)

        with open(CAMILLA_CONFIG, "w") as f:
            yaml.safe_dump(config, f, sort_keys=False)

        return True

    except Exception as e:
        print(f"Error updating eq yaml: {e}")
        return False

def restart_camilladsp():
    """Restart usługi CamillaDSP po zmianie konfiguracji."""
    try:
        # Prefer systemd service if present; fallback to restarting process is handled elsewhere.
        subprocess.run(['sudo', 'systemctl', 'restart', 'camilladsp'], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"Error restarting camilladsp: {e}")
        return False

def get_mpd():
    """Robust MPD connection with auto-reconnect"""
    global mpd_client
    try:
        if mpd_client is None:
            mpd_client = mpd.MPDClient()
            mpd_client.timeout = 2
            mpd_client.connect("localhost", 6600)
        mpd_client.status()
        return mpd_client
    except (mpd.ConnectionError, OSError, BrokenPipeError) as e:
        print(f"[MPD] Reconnecting: {e}")
        mpd_client = None
        mpd_client = mpd.MPDClient()
        mpd_client.timeout = 2
        mpd_client.connect("localhost", 6600)
        return mpd_client
    except Exception as e:
        print(f"[MPD] Error: {e}")
        return None

def get_audio_sinks():
    """Pobiera listę wszystkich dostępnych wyjść audio (PulseAudio sinks)."""
    try:
        output = subprocess.check_output(['pactl', 'list', 'short', 'sinks']).decode('utf-8')
        sinks = []
        for line in output.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 3:
                    name = parts[2].strip()
                    state = parts[5].strip() if len(parts) > 5 else "unknown"
                    if name and state != "SUSPENDED":
                        sinks.append({'name': name, 'state': state, 'type': 'bt' if 'bluez' in name.lower() else 'other'})
        return sinks
    except Exception as e:
        print(f"Błąd pobierania listy sinków: {e}")
        return []

def get_audio_sources():
    """Pobiera listę źródeł audio (PulseAudio sources) – przydatne dla 'line-in' (np. BT receiver)."""
    try:
        output = subprocess.check_output(['pactl', 'list', 'short', 'sources']).decode('utf-8')
        sources = []
        for line in output.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 3:
                    name = parts[1].strip() if len(parts) > 1 else ""
                    desc = parts[2].strip()
                    state = parts[4].strip() if len(parts) > 4 else "unknown"
                    if desc and "monitor" not in desc.lower():
                        sources.append({
                            "name": desc,
                            "id": name,
                            "state": state,
                            "type": "bt" if "bluez" in desc.lower() or "bluez" in name.lower() else "other"
                        })
        return sources
    except Exception as e:
        print(f"Błąd pobierania listy sources: {e}")
        return []

def _parse_mpd_audio_field(audio: Optional[str]) -> Dict[str, Optional[int]]:
    # MPD status["audio"] often looks like: "44100:16:2" (rate:bits:channels)
    if not audio or not isinstance(audio, str):
        return {"rate": None, "bits": None, "channels": None}
    parts = audio.split(":")
    if len(parts) != 3:
        return {"rate": None, "bits": None, "channels": None}
    try:
        return {"rate": int(parts[0]), "bits": int(parts[1]), "channels": int(parts[2])}
    except ValueError:
        return {"rate": None, "bits": None, "channels": None}

def _quality_label(rate: Optional[int], bits: Optional[int], bitrate: Optional[int], codec_hint: str = "") -> str:
    # Very simple heuristic
    if (rate or 0) >= 88200 or (bits or 0) >= 24:
        return "Hi-Res"
    # Lossless streams often have high bitrate even at 44.1kHz
    if bitrate and bitrate >= 800:
        return "Lossless"
    if bitrate and bitrate >= 320:
        return "HQ"
    if "flac" in codec_hint.lower():
        return "Lossless"
    return "Standard"

# ===== ROUTES =====
@app.route('/')
def index():
    """Full WWW interface"""
    return render_template('index.html')

@app.route('/api/eq/list', methods=['GET'])
def api_get_filter_list():
    """API pobierające dostępne filtry."""
    return jsonify(get_available_filters())

@app.route('/api/eq/<filter_name>', methods=['POST'])
def api_set_eq(filter_name):
    """Ustawia głośność dla konkretnego filtra."""
    try:
        gain = float(request.json.get('gain', 0))
        if not update_eq_yaml(filter_name, gain):
            return jsonify({"error": f"Nie można znaleźć filtra '{filter_name}'"}), 404
        if not restart_camilladsp():
            return jsonify({"error": "Błąd restartu CamillaDSP"}), 500
        return jsonify({"status": "success", "filter": filter_name, "gain": gain})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _set_camilla_pipeline_mode(mode: str) -> bool:
    """Przełącza pipeline na 'tone' albo 'eq' (5-band).

    tone: bass + treble (+ loudness jeśli istnieje)
    eq: eq1..eq5 (+ loudness jeśli istnieje)
    """
    mode = "eq" if mode == "eq" else "tone"
    with open(CAMILLA_CONFIG, "r") as f:
        config = yaml.safe_load(f) or {}

    pipeline = config.get("pipeline")
    if not isinstance(pipeline, list) or len(pipeline) == 0:
        return False

    # Find first Filter stage (common layout)
    stage = None
    for st in pipeline:
        if isinstance(st, dict) and st.get("type") == "Filter":
            stage = st
            break
    if stage is None:
        return False

    names = []
    if mode == "tone":
        names = ["bass", "treble"]
    else:
        names = ["eq1", "eq2", "eq3", "eq4", "eq5"]

    filters = config.get("filters") if isinstance(config.get("filters"), dict) else {}
    if isinstance(filters, dict) and "loudness" in filters:
        names.append("loudness")

    stage["names"] = names

    with open(CAMILLA_CONFIG, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return True

@app.route('/api/camilla/mode/<mode>', methods=['POST'])
def api_set_camilla_mode(mode):
    """Przełącza tryb CamillaDSP: tone vs eq."""
    try:
        if not _set_camilla_pipeline_mode(mode):
            return jsonify({"error": "Nie udało się przełączyć pipeline"}), 500
        if not restart_camilladsp():
            return jsonify({"error": "Błąd restartu CamillaDSP"}), 500
        return jsonify({"status": "success", "mode": "eq" if mode == "eq" else "tone"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/audio-sinks', methods=['GET'])
def api_get_sink_list():
    """API do pobrania listy aktywnych głośników/słuchawek."""
    return jsonify(get_audio_sinks())

@app.route('/api/audio-sources', methods=['GET'])
def api_get_source_list():
    """API do pobrania listy źródeł wejściowych."""
    return jsonify(get_audio_sources())

@app.route('/api/source/set/<sink_name>', methods=['POST'])
def api_set_sink(sink_name):
    """Ustaw dane wyjście jako domyślne."""
    try:
        subprocess.run(['pactl', 'set-default-sink', sink_name], check=True, capture_output=True)
        subprocess.run(['sudo', 'systemctl', 'restart', 'mpd'], check=True, capture_output=True)
        return jsonify({"status": "success", "current": sink_name})
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Błąd zmiany źródła: {str(e)}"}), 500

@app.route('/api/source-input/set/<source_id>', methods=['POST'])
def api_set_source(source_id):
    """Ustaw dane wejście jako domyślne source."""
    try:
        subprocess.run(['pactl', 'set-default-source', source_id], check=True, capture_output=True)
        return jsonify({"status": "success", "current": source_id})
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Błąd zmiany wejścia: {str(e)}"}), 500

@app.route('/api/status')
def api_status():
    try:
        client = get_mpd()
        if client is None:
            return jsonify({"error": "MPD connection failed"}), 503
        status = client.status()
        song = client.currentsong()
        audio = _parse_mpd_audio_field(status.get("audio"))
        bitrate = None
        try:
            bitrate = int(status.get("bitrate")) if status.get("bitrate") is not None else None
        except (TypeError, ValueError):
            bitrate = None
        file_field = song.get("file", "") or ""
        quality = _quality_label(audio.get("rate"), audio.get("bits"), bitrate, codec_hint=file_field)
        return jsonify({
            "state": status.get("state", "stop"),
            "title": song.get("title", song.get("name", "Brak tytułu")),
            "artist": song.get("artist", ""),
            "volume": int(status.get("volume", 50)),
            "playlist_length": int(status.get("playlistlength", 0)),
            "audio": audio,
            "bitrate_kbps": bitrate,
            "file": file_field,
            "quality": quality
        })
    except Exception as e:
        global mpd_client
        mpd_client = None
        return jsonify({"error": str(e)}), 500

@app.route('/api/play', methods=['POST'])
def api_play():
    try:
        get_mpd().play()
        return jsonify({"status": "playing"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/pause', methods=['POST'])
def api_pause():
    try:
        get_mpd().pause(1)
        return jsonify({"status": "paused"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stop', methods=['POST'])
def api_stop():
    try:
        get_mpd().stop()
        return jsonify({"status": "stopped"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/volume/<int:vol>', methods=['POST'])
def api_volume(vol):
    try:
        vol = max(0, min(100, vol))
        get_mpd().setvol(vol)
        return jsonify({"volume": vol})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/radio/stations')
def api_get_stations():
    stations = get_enabled_stations()
    favorites = [s["id"] for s in get_favorites()]
    return jsonify({"stations": stations, "favorites": favorites})

@app.route('/api/radio/station', methods=['POST'])
def api_add_station():
    """Dodaje stację do JSON."""
    try:
        payload = request.get_json(force=True) or {}
        name = (payload.get("name") or "").strip()
        url = (payload.get("url") or "").strip()
        genre = (payload.get("genre") or "").strip()
        if not name or not url:
            return jsonify({"error": "Missing name or url"}), 400
        station_id = add_station(name=name, url=url, genre=genre)
        return jsonify({"status": "created", "id": station_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/radio/favorite/<station_id>', methods=['POST'])
def api_toggle_favorite(station_id):
    """Dodaje/usuwa z ulubionych."""
    try:
        payload = request.get_json(force=True) or {}
        add = bool(payload.get("add", True))
        toggle_favorite(station_id, add=add)
        return jsonify({"status": "ok", "id": station_id, "favorite": add})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/radio/station/<station_id>', methods=['POST'])
def api_play_radio(station_id):
    station = get_station_by_id(station_id)
    if not station:
        return jsonify({"error": "Not found"}), 404
    try:
        script_path = os.path.join(os.path.dirname(__file__), "radio_play.sh")
        result = subprocess.run([script_path, station["url"], "10"], capture_output=True, text=True)
        if result.returncode != 0:
            return jsonify({"error": result.stderr}), 500
        return jsonify({"status": "playing", "name": station["name"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/radio/station/<station_id>', methods=['DELETE'])
def api_remove_station(station_id):
    try:
        remove_station(station_id)
        return jsonify({"status": "deleted", "id": station_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vu')
def api_vu():
    mode = request.args.get('mode', 'vu')
    return jsonify(get_vu_data(mode=mode))

@socketio.on('vu_request')
def ws_vu_request(data=None):
    """WebSocket VU data stream with mode support"""
    mode = (data or {}).get('mode', 'vu')
    sid = request.sid
    _client_vu_mode[sid] = mode if mode in ("vu", "spectrum") else "vu"
    emit('vu_data', get_vu_data(mode=_client_vu_mode[sid]))

@socketio.on('connect')
def ws_connect():
    _client_vu_mode[request.sid] = "vu"
    emit('vu_init', {"status": "connected"})

@socketio.on('disconnect')
def ws_disconnect():
    _client_vu_mode.pop(request.sid, None)

def vu_background_task():
    while True:
        socketio.sleep(0.05)
        # Emit per-client with their selected mode
        for sid, mode in list(_client_vu_mode.items()):
            try:
                socketio.emit('vu_data', get_vu_data(mode=mode), to=sid)
            except Exception:
                # If a client disappeared, remove it lazily
                _client_vu_mode.pop(sid, None)

from threading import Thread
Thread(target=vu_background_task, daemon=True).start()

@app.route('/api/features')
def api_features():
    return jsonify({"wifi_bt": False, "analog_input": False, "camilla": True, "radio": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
