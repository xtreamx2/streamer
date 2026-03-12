#!/usr/bin/env python3
"""
REST API routes — wszystkie endpointy HTTP.
Importowane przez app.py.
"""

import json
import os
import uuid
import psutil
import subprocess
from flask import Blueprint, jsonify, request, current_app

bp = Blueprint('api', __name__, url_prefix='/api')

STATIONS_FILE  = os.path.join(os.path.dirname(__file__), '..', 'radio', 'stations.json')


# ── Helper ─────────────────────────────────────────────────────────────────

def _mgr():
    return current_app.source_manager

def _eq():
    return current_app.eq_manager

def _bt():
    return current_app.bt_manager

def _net():
    return current_app.net_manager

def _uart():
    return current_app.uart_manager


def _load_stations() -> dict:
    try:
        with open(STATIONS_FILE) as f:
            return json.load(f)
    except Exception:
        return {'version': '3.0', 'stations': []}

def _save_stations(data: dict):
    with open(STATIONS_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Status ─────────────────────────────────────────────────────────────────

@bp.route('/status')
def api_status():
    """Pełny status systemu."""
    sm  = _mgr()
    net = _net()
    uart = _uart()

    net_status = net.get_status()

    # CPU temp — bezpośrednio z sysfs (działa na każdym RPi)
    cpu_temp = None
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            cpu_temp = round(int(f.read().strip()) / 1000, 1)
    except Exception:
        try:
            temps = psutil.sensors_temperatures()
            for key in ('cpu_thermal', 'cpu-thermal', 'coretemp'):
                if key in temps and temps[key]:
                    cpu_temp = round(temps[key][0].current, 1)
                    break
        except Exception:
            pass

    # CPU load
    try:
        cpu_load = psutil.cpu_percent(interval=0.0)
    except Exception:
        cpu_load = None

    # Uptime z /proc/uptime
    try:
        with open('/proc/uptime') as f:
            secs = int(float(f.read().split()[0]))
        days  = secs // 86400
        hours = (secs % 86400) // 3600
        mins  = (secs % 3600) // 60
        uptime = f"{days}d {hours}h {mins}m" if days else f"{hours}h {mins}m"
    except Exception:
        uptime = ''

    return jsonify({
        **sm.get_all_status(),
        'volume':    sm.get_volume(),
        'loudness':  sm.get_config('loudness', True),
        'autogain':  sm.get_config('autogain', True),
        'meter_mode': sm.get_config('meter_mode', 'vu'),
        'direct':    sm.get_config('direct', False),
        'source_gains': sm._config.get('source_gains', {}),
        'mono':      sm.get_config('mono', False),
        'network':   net_status,
        'uart':      uart.connected,  # port otwarty (ping/pong gdy RP2040 ma firmware)
        'cpu_temp':  cpu_temp,
        'cpu_load':  cpu_load,
        'cpu_hot':   bool(cpu_temp is not None and cpu_temp >= 70.0),
        'uptime':    uptime,
    })


# ── Source ─────────────────────────────────────────────────────────────────

@bp.route('/source', methods=['GET'])
def api_source_get():
    return jsonify(_mgr().get_all_status())

@bp.route('/source', methods=['POST'])
def api_source_set():
    data = request.get_json(force=True) or {}
    source_id = data.get('source')
    if not source_id:
        return jsonify({'error': 'source required'}), 400
    ok = _mgr().switch(source_id)
    if not ok:
        return jsonify({'error': f'Cannot activate source: {source_id}'}), 400
    # Jeśli przełączono na radio — wznów ostatnią stację
    if source_id == 'radio':
        _mgr().save_source(source_id)
        _mgr()._play_restored_station()
    else:
        _mgr().save_source(source_id)
    status = _mgr().active_source.get_status() if _mgr().active_source else {}
    _uart().send_state(source_id, status.get('state','idle'),
                       status.get('title',''), _mgr().get_volume())
    return jsonify(_mgr().get_all_status())


# ── Volume ─────────────────────────────────────────────────────────────────

@bp.route('/volume', methods=['GET'])
def api_volume_get():
    return jsonify({'volume': _mgr().get_volume()})

@bp.route('/volume', methods=['POST'])
def api_volume_set():
    data = request.get_json(force=True) or {}
    vol  = int(data.get('volume', 75))
    _mgr().set_volume(vol)
    _uart().send_volume(vol)
    return jsonify({'volume': vol})


# ── Level (VU meter) ───────────────────────────────────────────────────────

@bp.route('/level', methods=['GET'])
def api_level():
    radio = _mgr().get_source('radio')
    if radio and hasattr(radio, 'get_level'):
        return jsonify(radio.get_level())
    return jsonify({'rms_l': -60, 'rms_r': -60, 'peak_l': -60, 'peak_r': -60})

@bp.route('/spectrum', methods=['GET'])
def api_spectrum():
    radio = _mgr().get_source('radio')
    if radio and hasattr(radio, 'get_spectrum'):
        return jsonify({'bands': radio.get_spectrum()})
    return jsonify({'bands': [-60.0] * 16})

@bp.route('/meters', methods=['GET'])
def api_meters():
    """Level + Spectrum w jednym requeście."""
    source = _mgr().active_source  # zawsze z aktywnego źródła
    level = {'rms_l': -60.0, 'rms_r': -60.0, 'peak_l': -60.0, 'peak_r': -60.0}
    bands = [-60.0] * 32
    if source:
        if hasattr(source, 'get_level'):
            level = source.get_level()
        if hasattr(source, 'get_spectrum'):
            bands = source.get_spectrum()
    return jsonify({**level, 'bands': bands})


# ── Settings ───────────────────────────────────────────────────────────────

@bp.route('/setting', methods=['POST'])
def api_setting():
    data  = request.get_json(force=True) or {}
    key   = data.get('key')
    value = data.get('value')
    if key in ('loudness', 'mono', 'autogain', 'meter_mode'):
        _mgr().set_config(key, bool(value))
        return jsonify({'key': key, 'value': value})
    return jsonify({'error': 'Unknown setting'}), 400


# ── EQ ─────────────────────────────────────────────────────────────────────

@bp.route('/eq/<source_id>', methods=['GET'])
def api_eq_get(source_id):
    return jsonify({
        'source': source_id,
        'gains':  _eq().get(source_id),
        'bands':  _eq().get_band_names(),
    })

@bp.route('/eq/<source_id>', methods=['POST'])
def api_eq_set(source_id):
    data  = request.get_json(force=True) or {}
    gains = data.get('gains')
    if not gains or len(gains) != 10:
        return jsonify({'error': 'gains must be array of 10'}), 400
    result = _mgr().set_eq(source_id, gains)
    _eq().set(source_id, gains)
    _uart().send_eq(gains)
    return jsonify({'source': source_id, 'gains': gains})

@bp.route('/eq/<source_id>/preset/<preset>', methods=['POST'])
def api_eq_preset(source_id, preset):
    try:
        gains = _eq().apply_preset(source_id, preset)
        _mgr().set_eq(source_id, gains)
        _uart().send_eq(gains)
        return jsonify({'source': source_id, 'preset': preset, 'gains': gains})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/eq/presets', methods=['GET'])
def api_eq_presets():
    eq = _eq()
    presets = eq.get_presets()
    names = eq.get_preset_names()
    return jsonify({'presets': presets, 'names': names})

@bp.route('/eq/user/<preset_id>/save', methods=['POST'])
def api_eq_user_save(preset_id):
    """Zapisz biezace EQ jako user preset."""
    data = request.json or {}
    source_id = data.get('source', _mgr().active_source.SOURCE_ID if _mgr().active_source else 'radio')
    eq = _eq()
    gains = eq.get(source_id)
    try:
        saved = eq.save_user_preset(preset_id, gains)
        return jsonify({'preset': preset_id, 'gains': saved})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/eq/user/<preset_id>/name', methods=['POST'])
def api_eq_user_rename(preset_id):
    """Zmien nazwe user presetu."""
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    try:
        new_name = _eq().set_preset_name(preset_id, name)
        return jsonify({'preset': preset_id, 'name': new_name})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/setting/direct', methods=['POST'])
def api_direct():
    """Tryb Direct - bypass EQ i loudness."""
    data = request.json or {}
    enabled = bool(data.get('enabled', False))
    sm = _mgr()
    sm.set_config('direct', enabled)
    # Zastosuj: bypass EQ i ignoruj loudness
    src = sm.get_source('radio')
    if src and hasattr(src, 'set_direct'):
        src.set_direct(enabled)
    return jsonify({'direct': enabled})


# ── Radio / Stations ────────────────────────────────────────────────────────

@bp.route('/radio/stations', methods=['GET'])
def api_stations():
    return jsonify(_load_stations())

@bp.route('/radio/stations', methods=['POST'])
def api_add_station():
    data  = request.get_json(force=True) or {}
    name  = (data.get('name') or '').strip()
    url   = (data.get('url') or '').strip()
    genre = (data.get('genre') or '').strip()
    if not name or not url:
        return jsonify({'error': 'name and url required'}), 400
    sd = _load_stations()
    station = {
        'id':       str(uuid.uuid4())[:8],
        'name':     name,
        'url':      url,
        'genre':    genre,
        'bitrate':  int(data.get('bitrate', 128)),
        'codec':    data.get('codec', 'MP3'),
        'favorite': False,
        'enabled':  True,
    }
    sd['stations'].append(station)
    _save_stations(sd)
    return jsonify({'status': 'created', 'station': station}), 201

@bp.route('/radio/stations/<station_id>', methods=['DELETE'])
def api_delete_station(station_id):
    sd = _load_stations()
    sd['stations'] = [s for s in sd['stations'] if s['id'] != station_id]
    _save_stations(sd)
    return jsonify({'status': 'deleted'})

@bp.route('/radio/stations/<station_id>/favorite', methods=['POST'])
def api_favorite(station_id):
    add = bool(request.get_json(force=True).get('add', True))
    sd  = _load_stations()
    for s in sd['stations']:
        if s['id'] == station_id:
            s['favorite'] = add
    _save_stations(sd)
    return jsonify({'status': 'ok', 'favorite': add})

@bp.route('/radio/play', methods=['POST'])
def api_radio_play():
    data       = request.get_json(force=True) or {}
    station_id = data.get('id')
    url        = data.get('url')
    station_name = ''

    if station_id:
        stations = _load_stations().get('stations', [])
        station  = next((s for s in stations if s['id'] == station_id), None)
        if not station:
            return jsonify({'error': 'Station not found'}), 404
        url          = station['url']
        station_name = station['name']

    if not url:
        return jsonify({'error': 'No URL or station ID'}), 400

    # Upewnij się że radio jest aktywne
    if not _mgr().switch('radio'):
        return jsonify({'error': 'Cannot activate radio'}), 500

    radio = _mgr().get_source('radio')
    radio.play(url, station_name)

    # Zapamiętaj ostatnią stację
    if station_id:
        _mgr().set_config('last_station_id', station_id)

    _uart().send_state('radio', 'buffering', station_name, _mgr().get_volume(), station_name)
    return jsonify({'status': 'playing', 'url': url, 'station': station_name})

@bp.route('/radio/stop', methods=['POST'])
def api_radio_stop():
    radio = _mgr().get_source('radio')
    if radio:
        radio.stop()
    _uart().send_state('radio', 'stopped', '', _mgr().get_volume())
    return jsonify({'status': 'stopped'})


@bp.route('/network/wifi', methods=['POST'])
def api_wifi_toggle():
    data = request.json or {}
    enabled = bool(data.get('enabled', True))
    nm = current_app.net_manager
    ok = nm.set_wifi_enabled(enabled)
    return jsonify({'wifi': enabled, 'ok': ok})

@bp.route('/network/wifi', methods=['GET'])
def api_wifi_state():
    nm = current_app.net_manager
    return jsonify({'wifi': nm.get_wifi_enabled()})

# ── Source Gain ─────────────────────────────────────────────────────────────

@bp.route('/source/<source_id>/gain', methods=['GET'])
def api_get_gain(source_id):
    return jsonify({'source': source_id, 'gain': _mgr().get_source_gain(source_id)})

@bp.route('/source/<source_id>/gain', methods=['POST'])
def api_set_gain(source_id):
    data = request.json or {}
    gain = float(data.get('gain', 0))
    new_gain = _mgr().set_source_gain(source_id, gain)
    return jsonify({'source': source_id, 'gain': new_gain})

@bp.route('/source/gains', methods=['GET'])
def api_get_all_gains():
    sm = _mgr()
    sources = ['radio','bluetooth','phono','line1','line2','spdif']
    return jsonify({s: sm.get_source_gain(s) for s in sources})

# ── Bluetooth ───────────────────────────────────────────────────────────────

@bp.route('/bluetooth/devices', methods=['GET'])
def api_bt_devices():
    return jsonify({
        'paired':   _bt().get_paired(),
        'scanning': _bt().scanning,
        'mode':     _bt().mode,
        'connected': _bt().connected_device,
    })

@bp.route('/bluetooth/scan', methods=['POST'])
def api_bt_scan():
    results = []
    def _cb(devices):
        results.extend(devices)

    _bt().scan_async(duration=10, callback=None)
    return jsonify({'status': 'scanning', 'message': 'Scan started (10s)'})

@bp.route('/bluetooth/pair', methods=['POST'])
def api_bt_pair():
    mac = (request.get_json(force=True) or {}).get('mac', '')
    if not mac:
        return jsonify({'error': 'mac required'}), 400
    ok = _bt().pair(mac)
    return jsonify({'status': 'paired' if ok else 'error', 'mac': mac})

@bp.route('/bluetooth/connect', methods=['POST'])
def api_bt_connect():
    mac = (request.get_json(force=True) or {}).get('mac', '')
    if not mac:
        return jsonify({'error': 'mac required'}), 400
    ok = _bt().connect(mac)
    return jsonify({'status': 'connected' if ok else 'error', 'mac': mac})

@bp.route('/bluetooth/disconnect', methods=['POST'])
def api_bt_disconnect():
    mac = (request.get_json(force=True) or {}).get('mac', '')
    _bt().disconnect(mac)
    return jsonify({'status': 'disconnected'})

@bp.route('/bluetooth/unpair', methods=['POST'])
def api_bt_unpair():
    data = request.get_json(force=True) or {}
    mac  = data.get('mac', '')
    if not mac:
        return jsonify({'error': 'mac required'}), 400
    _bt().disconnect_device(mac)
    _bt().remove_device(mac)
    return jsonify({'status': 'unpaired', 'mac': mac})

@bp.route('/bluetooth/mode', methods=['POST'])
def api_bt_mode():
    mode = (request.get_json(force=True) or {}).get('mode', 'sink')
    _bt().set_mode(mode)
    return jsonify({'mode': mode})


# ── Network ─────────────────────────────────────────────────────────────────

@bp.route('/network/status', methods=['GET'])
def api_net_status():
    return jsonify(_net().get_status())

@bp.route('/network/scan', methods=['GET'])
def api_net_scan():
    return jsonify({'networks': _net().scan()})

@bp.route('/network/connect', methods=['POST'])
def api_net_connect():
    data     = request.get_json(force=True) or {}
    ssid     = data.get('ssid', '')
    password = data.get('password', '')
    if not ssid:
        return jsonify({'error': 'ssid required'}), 400
    result = _net().connect(ssid, password)
    return jsonify(result)

@bp.route('/network/disconnect', methods=['POST'])
def api_net_disconnect():
    return jsonify(_net().disconnect())


# ── System ──────────────────────────────────────────────────────────────────

@bp.route('/system/reboot', methods=['POST'])
def api_reboot():
    import threading
    def _do():
        import time; time.sleep(1)
        subprocess.run(['sudo', 'reboot'])
    threading.Thread(target=_do, daemon=True).start()
    return jsonify({'status': 'rebooting'})

@bp.route('/system/shutdown', methods=['POST'])
def api_shutdown():
    import threading
    def _do():
        import time; time.sleep(1)
        subprocess.run(['sudo', 'poweroff'])
    threading.Thread(target=_do, daemon=True).start()
    return jsonify({'status': 'shutting_down'})

@bp.route('/system/info', methods=['GET'])
def api_sysinfo():
    try:
        cpu  = psutil.cpu_percent(interval=0.5)
        mem  = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        temps = psutil.sensors_temperatures()
        temp  = round(temps['cpu_thermal'][0].current, 1) if 'cpu_thermal' in temps else None
    except Exception:
        cpu = mem = disk = temp = None

    try:
        with open('/proc/uptime') as f:
            secs = int(float(f.read().split()[0]))
        uptime = f"{secs//86400}d {(secs%86400)//3600}h {(secs%3600)//60}m"
    except Exception:
        uptime = ''

    return jsonify({
        'cpu_pct':  cpu,
        'mem_pct':  mem,
        'disk_pct': disk,
        'temp':     temp,
        'uptime':   uptime,
    })
