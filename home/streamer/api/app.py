#!/usr/bin/env python3
"""
PylonisAmp v0.10.4.41
Flask + SocketIO — serwer Web UI i REST API.

Uruchomienie:
  python3 app.py

Lub przez systemd (streamer.service).
"""

import os
import sys
import logging
import threading
import time
import json

# Dodaj ścieżkę projektu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template
from flask_socketio import SocketIO, emit

from core.source_manager import SourceManager
from core.eq_manager import EQManager
from core.uart_manager import UARTManager
from core.bt_manager import BTManager
from core.network_manager import NetworkManager
from sources.bluetooth import BluetoothSource

from routes import bp as api_bp

# ── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level  = logging.INFO,
    format = '%(asctime)s %(levelname)s [%(name)s] %(message)s',
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler('/tmp/streamer.log'),
    ]
)
log = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.WARNING)  # wycisz access logi

# ── Config ─────────────────────────────────────────────────────────────────

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')

def load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}

cfg = load_config()
ALSA_DEVICE = os.environ.get('ALSA_DEVICE', cfg.get('alsa_device', 'hw:sndrpihifiberry,0'))
UART_PORT   = os.environ.get('UART_PORT',   cfg.get('uart_port', '/dev/ttyAMA0'))
UART_BAUD   = int(os.environ.get('UART_BAUD', cfg.get('uart_baud', 115200)))
WEB_PORT    = int(os.environ.get('WEB_PORT', 8000))

# ── Flask app ──────────────────────────────────────────────────────────────

app = Flask(__name__,
            template_folder='../web/templates',
            static_folder='../web/static')

socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# ── Callbacks SocketIO ─────────────────────────────────────────────────────

def on_state_change(source_id: str, state: str):
    """Callback z SourceManager → push do WebSocket."""
    sm = app.source_manager
    if sm is None:
        return  # inicjalizacja jeszcze trwa
    try:
        payload = {
            'source': source_id,
            'state':  state,
            'status': sm.active_source.get_status() if sm.active_source else {},
            'volume': sm.get_volume(),
        }
        socketio.emit('state', payload)
        src = sm.active_source
        if src and src.SOURCE_ID == source_id and app.uart_manager:
            status = src.get_status()
            app.uart_manager.send_state(
                source_id, state,
                status.get('title', status.get('station', '')),
                sm.get_volume(),
            )
    except Exception as e:
        log.debug(f"on_state_change error: {e}")

def on_meta_change(source_id: str, meta: dict):
    """Callback z source → push tytułu/metadanych do WebSocket."""
    if app.source_manager is None:
        return
    try:
        socketio.emit('meta', {'source': source_id, **meta})
        if app.uart_manager:
            app.uart_manager.send_display(
                meta.get('station', meta.get('source', '')),
                meta.get('title', ''),
            )
    except Exception as e:
        log.debug(f"on_meta_change error: {e}")

def on_uart_event(event: dict):
    """Zdarzenie z RP2040 → obsłuż lub przekaż do Web UI."""
    evt = event.get('evt')
    log.debug(f"UART event: {event}")

    sm = app.source_manager

    if evt == 'encoder':
        eid   = event.get('id', 0)
        delta = event.get('delta', 0)
        if eid == 0:
            # Enkoder 0 = głośność
            new_vol = max(0, min(100, sm.get_volume() + delta * 2))
            sm.set_volume(new_vol)
            socketio.emit('volume', {'volume': new_vol})
            app.uart_manager.send_volume(new_vol)

    elif evt == 'switch':
        sid   = event.get('id', 0)
        state = event.get('state', 0)
        # Mapuj przyciski na akcje — dostosuj do swojego panelu
        if sid == 0 and state == 1:
            sm.switch('radio')
        elif sid == 1 and state == 1:
            sm.switch('bluetooth')
        elif sid == 2 and state == 1:
            sm.switch('phono')
        elif sid == 3 and state == 1:
            sm.switch('line1')
        socketio.emit('source', sm.get_all_status())

    elif evt == 'ir':
        socketio.emit('ir', event)

    elif evt == 'touch':
        socketio.emit('touch', event)

# ── Inicjalizacja managerów ────────────────────────────────────────────────

log.info("Inicjalizacja managerów...")

# Najpierw przypisz placeholdery żeby callbacks nie crashowały
app.source_manager = None
app.eq_manager     = None
app.uart_manager   = None
app.bt_manager     = None
app.net_manager    = None

uart_mgr = UARTManager(
    port     = UART_PORT,
    baud     = UART_BAUD,
    on_event = on_uart_event,
)
app.uart_manager = uart_mgr
uart_mgr.start()

eq_mgr  = EQManager()
net_mgr = NetworkManager()
app.eq_manager  = eq_mgr
app.net_manager = net_mgr

# SourceManager na końcu — jego __init__ już wywołuje switch('radio')
# i potrzebuje app.uart_manager żeby działały callbacks
source_mgr = SourceManager(
    alsa_device     = ALSA_DEVICE,
    on_state_change = on_state_change,
    on_meta_change  = on_meta_change,
)
app.source_manager = source_mgr

# BTManager potrzebuje referencji do BluetoothSource
bt_source = source_mgr.get_source('bluetooth')
bt_mgr    = BTManager(bt_source)
app.bt_manager = bt_mgr

# Teraz wszystko gotowe — przywróć ostatnie źródło
log.info("Przywracanie ostatniego źródła...")
source_mgr.restore_last_source()

# ── Routes ─────────────────────────────────────────────────────────────────

app.register_blueprint(api_bp)

@app.route('/')
def index():
    return render_template('index.html')


# ── WebSocket events ───────────────────────────────────────────────────────

@socketio.on('connect')
def ws_connect():
    sm = app.source_manager
    emit('status', {
        **sm.get_all_status(),
        'volume': sm.get_volume(),
        'uart':   app.uart_manager.connected,
    })

@socketio.on('play_radio')
def ws_play_radio(data):
    url          = (data or {}).get('url', '')
    station_name = (data or {}).get('name', '')
    if not url:
        return
    if not app.source_manager.switch('radio'):
        return
    radio = app.source_manager.get_source('radio')
    radio.play(url, station_name)
    emit('state', {'source': 'radio', 'state': 'buffering'}, broadcast=True)

@socketio.on('stop')
def ws_stop():
    src = app.source_manager.active_source
    if src and hasattr(src, 'stop'):
        src.stop()
    emit('state', {'source': src.SOURCE_ID if src else '', 'state': 'stopped'}, broadcast=True)

@socketio.on('set_volume')
def ws_volume(data):
    vol = int((data or {}).get('volume', 75))
    app.source_manager.set_volume(vol)
    app.uart_manager.send_volume(vol)
    emit('volume', {'volume': vol}, broadcast=True)

@socketio.on('set_source')
def ws_source(data):
    source_id = (data or {}).get('source', '')
    if source_id:
        app.source_manager.switch(source_id)
        emit('source', app.source_manager.get_all_status(), broadcast=True)

@socketio.on('set_eq')
def ws_eq(data):
    source_id = (data or {}).get('source', 'radio')
    gains     = (data or {}).get('gains', [])
    if gains and len(gains) == 10:
        app.source_manager.set_eq(source_id, gains)
        app.eq_manager.set(source_id, gains)
        app.uart_manager.send_eq(gains)
        emit('eq', {'source': source_id, 'gains': gains}, broadcast=True)


# ── Status push ────────────────────────────────────────────────────────────

def _status_push():
    """Push stanu co 3 sekundy do wszystkich klientów."""
    while True:
        time.sleep(3)
        try:
            sm = app.source_manager
            socketio.emit('status', {
                **sm.get_all_status(),
                'volume': sm.get_volume(),
                'uart':   app.uart_manager.connected,
            })
        except Exception as e:
            log.debug(f"Status push error: {e}")

threading.Thread(target=_status_push, daemon=True, name='status-push').start()

# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    log.info(f"Streamer v0.10.4.41 — http://0.0.0.0:{WEB_PORT}")
    log.info(f"ALSA: {ALSA_DEVICE}")
    log.info(f"UART: {UART_PORT} @ {UART_BAUD}")
    socketio.run(app, host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
