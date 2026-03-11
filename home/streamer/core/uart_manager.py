#!/usr/bin/env python3
"""
UART Manager — komunikacja JSON z panelem RP2040.

Protokół RPi → RP2040:
  {"cmd":"state","source":"radio","title":"Coldplay","volume":75,"state":"playing"}
  {"cmd":"eq","gains":[4,2,0,0,0,0,0,1,2,3]}
  {"cmd":"led","mode":"vu","data":[12,45,78,...]}
  {"cmd":"display","line1":"RMF FM","line2":"Coldplay - Scientist"}

Protokół RP2040 → RPi:
  {"evt":"encoder","id":0,"delta":1}
  {"evt":"encoder","id":1,"delta":-1}
  {"evt":"switch","id":3,"state":1}
  {"evt":"ir","code":"0xAB12"}
  {"evt":"touch","x":120,"y":85}
"""

import serial
import serial.threaded
import json
import logging
import threading
import time
from typing import Optional, Callable

log = logging.getLogger(__name__)


class UARTManager:
    def __init__(self,
                 port: str = '/dev/ttyAMA0',
                 baud: int = 115200,
                 on_event: Optional[Callable] = None):
        """
        on_event(event_dict) — callback wywoływany dla każdego zdarzenia z RP2040.
        """
        self._port     = port
        self._baud     = baud
        self._on_event = on_event
        self._serial:  Optional[serial.Serial] = None
        self._thread:  Optional[threading.Thread] = None
        self._running  = False
        self._lock     = threading.Lock()
        self._connected = False
        self._last_rx   = 0.0   # timestamp ostatniego odbioru danych

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self):
        """Otwórz port i zacznij czytać."""
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True, name='uart')
        self._thread.start()
        log.info(f"UART start: {self._port} @ {self._baud}")

    def stop(self):
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def active(self) -> bool:
        """True tylko gdy port otwarty ORAZ RP2040 przysłał dane w ostatnich 30s."""
        import time
        return self._connected and (time.monotonic() - self._last_rx) < 30

    # ── Send ───────────────────────────────────────────────────

    def send_state(self, source: str, state: str, title: str = '',
                   volume: int = 0, station: str = ''):
        self._send({
            'cmd':     'state',
            'source':  source,
            'state':   state,
            'title':   title[:32],       # max 32 znaków na LCD
            'station': station[:16],
            'volume':  volume,
        })

    def send_eq(self, gains: list):
        self._send({'cmd': 'eq', 'gains': [round(g, 1) for g in gains]})

    def send_led(self, mode: str, data: list = None):
        """
        mode: 'vu' | 'spectrum' | 'idle' | 'off'
        data: lista 8 wartości (dla WS2812 ring)
        """
        self._send({'cmd': 'led', 'mode': mode, 'data': data or []})

    def send_display(self, line1: str, line2: str = ''):
        self._send({'cmd': 'display', 'line1': line1[:20], 'line2': line2[:20]})

    def send_volume(self, volume: int):
        self._send({'cmd': 'volume', 'value': volume})

    # ── Internal ───────────────────────────────────────────────

    def _send(self, msg: dict):
        if not self._serial or not self._serial.is_open:
            return
        try:
            line = json.dumps(msg, separators=(',', ':')) + '\n'
            with self._lock:
                self._serial.write(line.encode('utf-8'))
        except Exception as e:
            log.warning(f"UART send error: {e}")
            self._connected = False

    def _run(self):
        """Główna pętla: otwórz port, czytaj linie JSON, reconnect przy błędzie."""
        while self._running:
            try:
                self._serial = serial.Serial(
                    self._port, self._baud,
                    timeout=1.0,
                    write_timeout=1.0
                )
                self._connected = True
                log.info(f"UART connected: {self._port}")
                self._read_loop()
            except serial.SerialException as e:
                self._connected = False
                log.warning(f"UART error: {e} — retry in 5s")
                time.sleep(5)
            except Exception as e:
                self._connected = False
                log.error(f"UART unexpected: {e}")
                time.sleep(5)
            finally:
                if self._serial:
                    try:
                        self._serial.close()
                    except Exception:
                        pass
                    self._serial = None

    def _read_loop(self):
        buf = b''
        while self._running and self._serial and self._serial.is_open:
            try:
                chunk = self._serial.read(64)
                if not chunk:
                    continue
                buf += chunk
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    self._handle_line(line.decode('utf-8', errors='ignore').strip())
            except serial.SerialException:
                break
            except Exception as e:
                log.warning(f"UART read error: {e}")
                break

    def _handle_line(self, line: str):
        if not line:
            return
        try:
            msg = json.loads(line)
            log.debug(f"UART ← {msg}")
            self._last_rx = __import__('time').monotonic()
            if self._on_event:
                self._on_event(msg)
        except json.JSONDecodeError:
            log.debug(f"UART bad JSON: {line!r}")
