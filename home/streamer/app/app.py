#!/usr/bin/env python3
"""
PylonisAmp v0.10.4.43 - USB Frontpanel Edition
Flask + SocketIO — serwer Web UI i REST API.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import threading
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flask import request

from modules.source_manager import SourceManager
from modules.eq_manager import EQManager
from display.frontpanel_manager import FrontpanelManager
from modules.bt_manager import BTManager
from modules.network_manager import NetworkManager
from sources.bluetooth import BluetoothSource

from routes import bp as api_bp

# ── Logging ────────────────────────────────────────────────────────────────

LOG_DIR = '/home/tom/streamer/logs'
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'streamer.log')

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')

# Rotating File Handler: 10MB, 5 backups
rfh = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5)
rfh.setFormatter(formatter)
root_logger.addHandler(rfh)

# Stream Handler for console
sh = logging.StreamHandler()
sh.setFormatter(formatter)
root_logger.addHandler(sh)

log = logging.getLogger(__name__)

# DEBUG levels for critical modules
logging.getLogger('display.frontpanel_manager').setLevel(logging.DEBUG)
logging.getLogger('modules.source_manager').setLevel(logging.DEBUG)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

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
WEB_PORT    = int(os.environ.get('WEB_PORT', 8000))

# ── Flask app ──────────────────────────────────────────────────────────────

app = Flask(__name__,
            template_folder='../web/templates',
            static_folder='../web/static')

socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# ── UartManager adapter (USB/Pico) ─────────────────────────────────────────

class _UartAdapter:
    """
    Adapter: routes.py i callbacks wołają send_state/send_volume/send_eq,
    delegujemy do FrontpanelManager który trzyma port USB do Pico.
    """
    def __init__(self, fp):
        self._fp = fp

    @property
    def connected(self) -> bool:
        return bool(self._fp and self._fp.running and
                    self._fp.serial and self._fp.serial.is_open)

    @property
    def active(self) -> bool:
        return self.connected

    def send_state(self, source: str, state: str, title: str = '',
                   volume: int = 0, station: str = ''):
        if self._fp:
            self._fp.send_current_state()

    def send_volume(self, volume: int):
        if self._fp:
            self._fp.send_fast_update()

    def send_eq(self, gains: list):
        if self._fp:
            self._fp._send({"cmd": "eq", "gains": [round(g, 1) for g in gains]})

    def send_display(self, line1: str, line2: str = ''):
        if self._fp:
            self._fp._send({"cmd": "display", "line1": line1[:20], "line2": line2[:20]})

    def send_meters(self, data: list):
        if self._fp:
            self._fp.send_meters(data)

# ── Callbacks SocketIO i Pico ──────────────────────────────────────────────

_cover_thread = None

def on_state_change(source_id: str, state: str):
    sm = app.source_manager
    if sm is None:
        return
    try:
        payload = {
            'source': source_id,
            'state':  state,
            'status': sm.active_source.get_status() if sm.active_source else {},
            'volume': sm.get_volume(),
        }
        socketio.emit('state', payload)
        if app.uart_manager:
            status = sm.active_source.get_status() if sm.active_source else {}
            app.uart_manager.send_state(
                source_id, state,
                status.get('title', status.get('station', '')),
                sm.get_volume(),
            )
    except Exception as e:
        log.debug(f"on_state_change error: {e}")

def on_meta_change(source_id: str, meta: dict):
    if app.source_manager is None:
        return
    try:
        artist  = meta.get('artist', '')
        title   = meta.get('title', '')
        station = meta.get('station', '')

        # Pobierz okładkę w tle — używamy jednego dedykowanego wątku, by uniknąć zombie
        global _cover_thread
        if _cover_thread and _cover_thread.is_alive():
            # Jeśli poprzedni wątek jeszcze pobiera, nie spawnujemy nowego bezmyślnie
            # (opcjonalnie można tu dodać kolejkę, ale dla stabilności ograniczamy liczbę wątków)
            pass

        def _fetch_cover():
            try:
                from modules.cover_manager import get_cover_url, get_cover
                cover_url = get_cover_url(artist, title, station)
                if cover_url:
                    socketio.emit('cover', {'url': cover_url, 'source': source_id})
                    if app.frontpanel:
                        cover_path = get_cover(artist, title, station)
                        if cover_path:
                            app.frontpanel.send_cover_to_pico(cover_path)
            except Exception as e:
                log.error(f"Cover fetch error: {e}")

        _cover_thread = threading.Thread(target=_fetch_cover, daemon=True)
        _cover_thread.start()

        socketio.emit('meta', {'source': source_id, **meta})

        if app.frontpanel:
            app.frontpanel.send_current_state()
    except Exception as e:
        log.debug(f"on_meta_change error: {e}")

# ── Inicjalizacja managerów ────────────────────────────────────────────────

log.info("Inicjalizacja managerów...")

app.source_manager = None
app.eq_manager     = None
app.frontpanel     = None
app.uart_manager   = None
app.bt_manager     = None
app.net_manager    = None

eq_mgr  = EQManager()
net_mgr = NetworkManager()
app.eq_manager  = eq_mgr
app.net_manager = net_mgr

source_mgr = SourceManager(
    alsa_device     = ALSA_DEVICE,
    on_state_change = on_state_change,
    on_meta_change  = on_meta_change,
)
app.source_manager = source_mgr

app.frontpanel = FrontpanelManager(source_manager=source_mgr)
app.frontpanel.start()
app.uart_manager = _UartAdapter(app.frontpanel)

bt_source = source_mgr.get_source('bluetooth')
bt_mgr    = BTManager(bt_source)
app.bt_manager = bt_mgr

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
        'uart':   app.uart_manager.connected if app.uart_manager else False,
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
    if app.uart_manager:
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
        if app.uart_manager:
            app.uart_manager.send_eq(gains)
        emit('eq', {'source': source_id, 'gains': gains}, broadcast=True)

@socketio.on('set_viz_mode')
def ws_viz_mode(data):
    app.viz_mode = data.get('mode', 'vu')
    emit('viz_mode', {'mode': app.viz_mode}, broadcast=True)

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
                'uart':   app.uart_manager.connected if app.uart_manager else False,
            })
        except Exception:
            pass

threading.Thread(target=_status_push, daemon=True, name='status-push').start()

# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    log.info(f"PylonisAmp v0.10.4.43 — http://0.0.0.0:{WEB_PORT}")
    log.info(f"ALSA: {ALSA_DEVICE}")
    socketio.run(app, host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
