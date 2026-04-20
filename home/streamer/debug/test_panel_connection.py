#!/usr/bin/env python3
"""
PylonisAmp — Test połączenia z panelem RP2040
Uruchom na malinie: python3 test_panel_connection.py

Co robi:
- Szuka /dev/ttyACM0 (RP2040 USB CDC)
- Wysyła heartbeat co 3s
- Wysyła aktualny status radia (tytuł, wykonawca, głośność)
- Loguje zwrotkę: heartbeat, ready, touch events
- Ctrl+C aby zakończyć
"""

import serial
import json
import threading
import time
import sys
import glob
import os

# ── Konfiguracja ──────────────────────────────────
PORT_PATTERNS = [
    '/dev/ttyACM0',
    '/dev/serial/by-id/usb-Raspberry_Pi_Pico*',
    '/dev/ttyACM1',
]
BAUD = 115200
HB_INTERVAL = 3.0

# ── Kolory terminala ──────────────────────────────
GRN = '\033[92m'
YEL = '\033[93m'
RED = '\033[91m'
CYN = '\033[96m'
RST = '\033[0m'

def find_port():
    for pat in PORT_PATTERNS:
        matches = glob.glob(pat)
        if matches:
            return matches[0]
    return None

def log(color, prefix, msg):
    ts = time.strftime('%H:%M:%S')
    print(f"{color}[{ts}] {prefix}{RST} {msg}")

def read_loop(ser, stop_event):
    buf = b''
    while not stop_event.is_set():
        try:
            chunk = ser.read(256)
            if not chunk:
                continue
            buf += chunk
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    evt = data.get('evt', '?')
                    if evt == 'hb':
                        log(GRN, '← HB', f"Panel alive (ok={data.get('ok')})")
                    elif evt == 'ready':
                        log(GRN, '← READY', f"Firmware: {data.get('fw', '?')}")
                    elif evt == 'touch':
                        log(CYN, '← TOUCH', f"x={data.get('x')} y={data.get('y')}")
                    elif evt == 'img_err':
                        log(RED, '← IMG_ERR', data.get('msg', ''))
                    else:
                        log(YEL, f'← {evt.upper()}', str(data))
                except json.JSONDecodeError:
                    log(YEL, '← RAW', line.decode('utf-8', errors='replace'))
        except Exception as e:
            if not stop_event.is_set():
                log(RED, 'READ ERR', str(e))
            break

def send(ser, data: dict):
    line = json.dumps(data, ensure_ascii=False) + '\n'
    ser.write(line.encode())

def main():
    print(f"\n{CYN}PylonisAmp — Test połączenia panelu{RST}")
    print("=" * 45)

    port = find_port()
    if not port:
        log(RED, 'ERROR', 'Nie znaleziono RP2040! Sprawdź kabel USB.')
        log(YEL, 'INFO', 'Szukam w: ' + ', '.join(PORT_PATTERNS))
        sys.exit(1)

    log(GRN, 'FOUND', f"Port: {port}")

    try:
        ser = serial.Serial(port, BAUD, timeout=0.1)
    except Exception as e:
        log(RED, 'OPEN ERR', str(e))
        sys.exit(1)

    log(GRN, 'OPEN', f"Połączono z {port} @ {BAUD}")
    print(f"{YEL}Ctrl+C aby zakończyć{RST}\n")

    stop = threading.Event()
    reader = threading.Thread(target=read_loop, args=(ser, stop), daemon=True)
    reader.start()

    # Przykładowe dane radia do wysłania
    demo_states = [
        {"cmd": "state", "source": "radio", "volume": 65,
         "title": "The Scientist", "artist": "Coldplay"},
        {"cmd": "state", "source": "radio", "volume": 70,
         "title": "Bohemian Rhapsody", "artist": "Queen"},
        {"cmd": "state", "source": "bluetooth", "volume": 50,
         "title": "Test BT Track", "artist": "Test Artist"},
    ]
    demo_idx = 0

    hb_count = 0
    try:
        while True:
            time.sleep(HB_INTERVAL)
            if not ser.is_open:
                break

            # Heartbeat
            send(ser, {"cmd": "hb"})
            hb_count += 1
            log(YEL, '→ HB', f"#{hb_count}")

            # Co 3 HB - zmień stan demo
            if hb_count % 3 == 0:
                state = demo_states[demo_idx % len(demo_states)]
                demo_idx += 1
                send(ser, state)
                log(YEL, '→ STATE', f"{state['source']} | {state['artist']} – {state['title']} | vol:{state['volume']}")

    except KeyboardInterrupt:
        print(f"\n{YEL}Zatrzymano.{RST}")
    finally:
        stop.set()
        ser.close()
        log(GRN, 'CLOSED', 'Port zamknięty')

if __name__ == '__main__':
    main()
