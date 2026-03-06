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
from radio_handler import (
    load_stations, save_stations, add_station, remove_station,
    get_enabled_stations, get_favorites, get_station_by_id,
    toggle_favorite
)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
mpd_client = None

CAMILLA_CONFIG = '/etc/camilladsp/config.yml'

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
        return sorted(filters, key=lambda x: ['bass', 'treble'].index(x['name']) if x['name'] in ['bass', 'treble'] else 1)
    except Exception as e:
        print(f"Error reading filters: {e}")
        return []

def update_eq_yaml(filter_name, gain):
    """Tylko zmienia gain konkretnego filtra, nie nadpisuje reszty pliku."""
    try:
        with open(CAMILLA_CONFIG, 'r') as f:
            content = f.read()

        import re
        # Szukamy wzoru: gain: <wartość>
        pattern = rf"(?<=^.{20})gain:\s*[\d.-]+"

        # Sprawdzamy czy filtr istnieje w pliku
        if f"{filter_name}:" not in content:
            print(f"Filter '{filter_name}' not found!")
            return False

        # Modyfikujemy wartość gain dla danego filtra
        lines = content.split('\n')
        in_target_filter = False
        new_lines = []

        for line in lines:
            stripped = line.strip()

            # Czy to początek naszego filtra?
            if stripped.rstrip(':') == filter_name + ':' or stripped == f'{filter_name}:':
                in_target_filter = True

            # Jeśli w naszym filtrze i widzimy linię gain
            if in_target_filter and stripped.startswith('gain:'):
                # Pobierz indentation
                indent = line[:len(line) - len(stripped)]
                new_line = f"{indent}gain: {gain}"
                new_lines.append(new_line)
                in_target_filter = False  # Koniec filtra
                continue

            new_lines.append(line)

        # Zapisz
        with open(CAMILLA_CONFIG, 'w') as f:
            f.write('\n'.join(new_lines))

        return True

    except Exception as e:
        print(f"Error updating eq yaml: {e}")
        return False

def restart_camilladsp():
    """Restart usługi CamillaDSP po zmianie konfiguracji."""
    try:
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
    """Pobiera listę wszystkich dostępnych wyjść audio."""
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

# ===== VU METER SKELETON =====
class VUMeter:
    def __init__(self, bands=32, attack_ms=50, decay_ms=200, peak_hold_s=1.5):
        self.bands = bands
        self.attack_coef = np.exp(-1/(attack_ms/1000 * 20))
        self.decay_coef = np.exp(-1/(decay_ms/1000 * 20))
        self.peak_decay = 1/(peak_hold_s * 20)
        self.levels = np.zeros(bands)
        self.peaks = np.zeros(bands)
        self.peak_timers = np.zeros(bands)

    def update(self, amplitudes):
        amplitudes = np.clip(amplitudes, -60, 0)
        for i in range(self.bands):
            if amplitudes[i] > self.levels[i]:
                self.levels[i] = self.levels[i] * self.attack_coef + amplitudes[i] * (1 - self.attack_coef)
            else:
                self.levels[i] = self.levels[i] * self.decay_coef + amplitudes[i] * (1 - self.decay_coef)
            if amplitudes[i] > self.peaks[i]:
                self.peaks[i] = amplitudes[i]
                self.peak_timers[i] = 0
            else:
                self.peak_timers[i] += 1/20
                if self.peak_timers[i] >= 1.5:
                    self.peaks[i] = max(self.peaks[i] - 0.5, self.levels[i])
        return self.levels.copy(), self.peaks.copy()

    def interpolate_to_64(self, levels_32):
        result = []
        for i in range(len(levels_32)):
            result.append(levels_32[i])
            if i < len(levels_32) - 1:
                result.append((levels_32[i] + levels_32[i+1]) / 2)
        return np.array(result)

vu_meter = VUMeter(bands=32)

def get_vu_data(mode='vu'):
    import random
    amplitudes = np.array([random.uniform(-60, -6) for _ in range(32)])
    levels, peaks = vu_meter.update(amplitudes)
    levels_64 = vu_meter.interpolate_to_64(levels)
    peaks_64 = vu_meter.interpolate_to_64(peaks)
    return {"vu_l": levels_64[:32].tolist(), "vu_r": levels_64[32:].tolist(), "peak_l": peaks_64[:32].tolist(), "peak_r": peaks_64[32:].tolist(), "timestamp": time.time()}

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

@app.route('/api/audio-sinks', methods=['GET'])
def api_get_sink_list():
    """API do pobrania listy aktywnych głośników/słuchawek."""
    return jsonify(get_audio_sinks())

@app.route('/api/source/set/<sink_name>', methods=['POST'])
def api_set_sink(sink_name):
    """Ustaw dane wyjście jako domyślne."""
    try:
        subprocess.run(['pactl', 'set-default-sink', sink_name], check=True, capture_output=True)
        subprocess.run(['sudo', 'systemctl', 'restart', 'mpd'], check=True, capture_output=True)
        return jsonify({"status": "success", "current": sink_name})
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Błąd zmiany źródła: {str(e)}"}), 500

@app.route('/api/status')
def api_status():
    try:
        client = get_mpd()
        if client is None:
            return jsonify({"error": "MPD connection failed"}), 503
        status = client.status()
        song = client.currentsong()
        return jsonify({
            "state": status.get("state", "stop"),
            "title": song.get("title", song.get("name", "Brak tytułu")),
            "artist": song.get("artist", ""),
            "volume": int(status.get("volume", 50)),
            "playlist_length": int(status.get("playlistlength", 0))
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

@app.route('/api/radio/station/<station_id>', methods=['POST'])
def api_play_radio(station_id):
    station = get_station_by_id(station_id)
    if not station:
        return jsonify({"error": "Not found"}), 404
    try:
        import subprocess
        result = subprocess.run(["/home/tom/streamer/radio_play.sh", station["url"], "10"], capture_output=True, text=True)
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
    emit('vu_data', get_vu_data(mode=mode))

@socketio.on('connect')
def ws_connect():
    emit('vu_init', {"status": "connected"})

def vu_background_task():
    while True:
        socketio.sleep(0.05)
        socketio.emit('vu_data', get_vu_data())

from threading import Thread
Thread(target=vu_background_task, daemon=True).start()

@app.route('/api/features')
def api_features():
    return jsonify({"wifi_bt": False, "analog_input": False, "camilla": True, "radio": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
