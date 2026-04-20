#!/usr/bin/env python3
"""
PylonisAmp — USB Debug
Testuje połączenie z RP2040 przez /dev/ttyACM0
Log: streamer/debug/debug.log

Użycie:
  python3 usb_debug.py
  python3 usb_debug.py --port /dev/ttyACM0 --baud 115200
"""

import serial
import json
import time
import logging
import argparse
import sys
import os
from datetime import datetime

# ── Konfiguracja ──────────────────────────────────────────────────
DEFAULT_PORT  = '/dev/ttyACM0'
DEFAULT_BAUD  = 115200
HB_INTERVAL   = 0.5          # heartbeat co 500ms
HB_TIMEOUT    = 3            # 3 nieudane HB = error
LOG_FILE      = os.path.join(os.path.dirname(__file__), 'debug.log')

# ── Logger ────────────────────────────────────────────────────────
def setup_logger():
    log = logging.getLogger('usb_debug')
    log.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        '%(asctime)s.%(msecs)03d [%(levelname)-5s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Plik
    fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    log.addHandler(fh)

    # Konsola
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(fmt)
    log.addHandler(ch)

    return log


# ── Wysyłanie JSON ────────────────────────────────────────────────
def send(ser, obj, log):
    try:
        line = json.dumps(obj, separators=(',', ':')) + '\n'
        ser.write(line.encode('utf-8'))
        log.debug(f'TX: {line.strip()}')
    except serial.SerialException as e:
        log.error(f'TX error: {e}')


# ── Główna pętla ──────────────────────────────────────────────────
def run(port, baud, log):
    log.info('=' * 60)
    log.info(f'PylonisAmp USB Debug start')
    log.info(f'Port: {port}  Baud: {baud}')
    log.info(f'HB interval: {HB_INTERVAL}s  Timeout: {HB_TIMEOUT} missed')
    log.info('=' * 60)

    # ── Otwórz port ───────────────────────────────────────────────
    try:
        ser = serial.Serial(
            port     = port,
            baudrate = baud,
            bytesize = serial.EIGHTBITS,
            parity   = serial.PARITY_NONE,
            stopbits = serial.STOPBITS_ONE,
            timeout  = 0.1,      # nieblokujący odczyt
        )
        log.info(f'Port otwarty: {ser.name}')
    except serial.SerialException as e:
        log.error(f'Nie można otworzyć portu {port}: {e}')
        log.error('Sprawdź: ls /dev/ttyACM0')
        sys.exit(1)

    # ── Stan połączenia ───────────────────────────────────────────
    hb_sent       = 0      # łączna liczba wysłanych HB
    hb_missed     = 0      # obecna seria missed
    hb_ok         = 0      # łączna liczba odebranych pong/hb
    connected     = False
    last_hb_time  = 0
    buf           = ''

    log.info('Czekam na RP2040... (Ctrl+C aby wyjść)')

    try:
        while True:
            now = time.monotonic()

            # ── Wyślij heartbeat ──────────────────────────────────
            if now - last_hb_time >= HB_INTERVAL:
                send(ser, {'cmd': 'hb'}, log)
                hb_sent      += 1
                last_hb_time  = now

            # ── Odbierz dane ──────────────────────────────────────
            try:
                raw = ser.read(256)
                if raw:
                    buf += raw.decode('utf-8', errors='replace')
            except serial.SerialException as e:
                log.error(f'RX error: {e}')
                break

            # ── Parsuj linie JSON ─────────────────────────────────
            while '\n' in buf:
                line, buf = buf.split('\n', 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    log.debug(f'RX: {line}')
                    handle_event(obj, log)

                    # Heartbeat odpowiedź
                    evt = obj.get('evt', '')
                    if evt in ('hb', 'pong'):
                        ok = obj.get('ok', 1)
                        if ok:
                            if not connected:
                                log.info('>>> POŁĄCZENIE OK — RP2040 odpowiada')
                                connected = True
                            hb_missed  = 0
                            hb_ok     += 1
                            log.debug(f'HB OK (sent={hb_sent} ok={hb_ok} missed={hb_missed})')
                        else:
                            hb_missed += 1
                            log.warning(f'HB ok=0 — RP2040 zgłasza problem (missed={hb_missed})')

                    elif evt == 'ready':
                        fw  = obj.get('fw', '?')
                        disp = obj.get('display', '?')
                        log.info(f'>>> RP2040 READY — fw={fw} display={disp}')
                        connected = True
                        hb_missed = 0

                except json.JSONDecodeError:
                    log.warning(f'Nieprawidłowy JSON: {repr(line)}')

            # ── Sprawdź timeout heartbeat ─────────────────────────
            # Jeśli wysłaliśmy >= 3 HB i nie dostaliśmy żadnej odpowiedzi
            # od ostatnich HB_TIMEOUT interwałów
            elapsed_since_last_ok = (hb_sent - hb_ok) if hb_ok == 0 else 0
            if hb_sent >= HB_TIMEOUT and hb_ok == 0 and hb_sent % HB_TIMEOUT == 0:
                if connected:
                    connected = False
                    log.error(
                        f'>>> BRAK POŁĄCZENIA — brak odpowiedzi po {hb_sent} HB '
                        f'({hb_sent * HB_INTERVAL:.1f}s)'
                    )
                elif hb_sent % 10 == 0:
                    # Przypomnienie co 10 HB (5s)
                    log.error(
                        f'>>> NADAL BRAK POŁĄCZENIA — '
                        f'wysłano {hb_sent} HB, odebrano {hb_ok} odpowiedzi'
                    )

            # Seria missed
            if hb_missed >= HB_TIMEOUT:
                if connected:
                    connected = False
                log.error(
                    f'>>> ZERWANE POŁĄCZENIE — '
                    f'{hb_missed} nieudanych HB z rzędu'
                )
                hb_missed = 0   # reset serii (logujemy raz)

            time.sleep(0.01)   # 10ms pętla

    except KeyboardInterrupt:
        log.info('')
        log.info('─' * 60)
        log.info(f'Przerwano przez użytkownika')
        log.info(f'Statystyki: wysłano={hb_sent} odebrano={hb_ok} '
                 f'skuteczność={hb_ok/hb_sent*100:.1f}%' if hb_sent else 'brak danych')
        log.info('─' * 60)
    finally:
        ser.close()
        log.info('Port zamknięty')


# ── Obsługa zdarzeń ───────────────────────────────────────────────
def handle_event(obj, log):
    evt = obj.get('evt', '')

    if evt == 'encoder':
        eid   = obj.get('id', '?')
        delta = obj.get('delta', 0)
        name  = 'MENU/NAV' if eid == 0 else 'VOLUME'
        direction = '▲' if delta > 0 else '▼'
        log.info(f'ENCODER id={eid} ({name}) delta={delta} {direction}')

    elif evt == 'switch':
        sid   = obj.get('id', '?')
        names = {0: 'ENC1-BTN', 1: 'ENC2-MUTE', 2: 'POWER',
                 3: 'BACK', 4: 'PLAY/PAUSE', 5: 'STOP', 6: 'FORWARD'}
        name  = names.get(sid, f'SW{sid}')

        if obj.get('long'):
            log.info(f'SWITCH id={sid} ({name}) LONG PRESS')
        elif obj.get('wake'):
            log.info(f'SWITCH id={sid} ({name}) WAKE')
        elif obj.get('confirm'):
            log.info(f'SWITCH id={sid} ({name}) CONFIRM={obj["confirm"]}')
        else:
            state = obj.get('state', '?')
            action = 'DOWN' if state == 1 else 'UP'
            log.info(f'SWITCH id={sid} ({name}) {action}')

    elif evt == 'ir':
        code = obj.get('code', '?')
        raw  = obj.get('raw', '')
        if code == 'unknown':
            log.warning(f'IR UNKNOWN raw={raw}')
        else:
            log.info(f'IR code={code}')

    elif evt == 'display_error':
        log.error(f'DISPLAY ERROR: {obj.get("msg", "?")}')

    elif evt == 'usb_overflow':
        log.error('USB OVERFLOW — RP2040 zgłasza przepełnienie bufora')

    elif evt == 'shutdown_cancelled':
        log.info('SHUTDOWN anulowany przez RP2040')

    elif evt == 'cover_hit':
        log.info(f'COVER HIT id={obj.get("id")}')

    elif evt == 'cover_miss':
        log.info(f'COVER MISS id={obj.get("id")}')


# ── Entry point ───────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PylonisAmp USB Debug')
    parser.add_argument('--port', default=DEFAULT_PORT)
    parser.add_argument('--baud', type=int, default=DEFAULT_BAUD)
    args = parser.parse_args()

    log = setup_logger()
    run(args.port, args.baud, log)
