# Tom's Streamer v3.0

Zintegrowany wzmacniacz/streamer na Raspberry Pi.

## Hardware
- Raspberry Pi 3/4
- DAC: PCM5102 → `hw:sndrpihifiberry,0`
- ADC: PCM1808 (I2S) → wejścia analogowe
- Panel: RP2040 (LCD, enkodery, switche, WS2812) ↔ UART

## Struktura

```
streamer/
├── api/
│   ├── app.py          # Flask + SocketIO, punkt wejściowy
│   └── routes.py       # REST API /api/*
├── core/
│   ├── source_manager.py   # przełączanie źródeł
│   ├── eq_manager.py       # EQ per źródło, presety
│   ├── uart_manager.py     # JSON UART ↔ RP2040
│   ├── bt_manager.py       # BlueZ fasada
│   └── network_manager.py  # nmcli WiFi
├── sources/
│   ├── base.py             # klasa bazowa
│   ├── radio.py            # ✅ Internet radio (GStreamer)
│   ├── bluetooth.py        # ✅ A2DP sink + source (BlueZ)
│   ├── analog.py           # 🔲 Phono / Line (szkielet)
│   └── digital.py          # 🔲 S/PDIF (szkielet)
├── web/
│   └── templates/
│       └── index.html      # Web UI
├── radio/
│   └── stations.json
├── config.json
├── requirements.txt
└── streamer.service
```

## Instalacja

```bash
# 1. Zależności systemowe
sudo apt update
sudo apt install python3-gi python3-gi-cairo \
  gir1.2-gstreamer-1.0 \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly gstreamer1.0-alsa gstreamer1.0-libav \
  python3-dbus bluetooth bluez

# 2. Zależności Python
pip3 install -r requirements.txt --break-system-packages

# 3. Konfiguracja
cp streamer.service /etc/systemd/system/
# Edytuj: User=tom, WorkingDirectory, ALSA_DEVICE, UART_PORT

# 4. Uruchomienie
sudo systemctl daemon-reload
sudo systemctl enable streamer
sudo systemctl start streamer
```

## REST API

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/api/status` | GET | Pełny status systemu |
| `/api/source` | GET/POST | Aktywne źródło |
| `/api/volume` | GET/POST | Głośność 0-100 |
| `/api/eq/{source}` | GET/POST | EQ 10 pasm |
| `/api/eq/{source}/preset/{name}` | POST | Zastosuj preset |
| `/api/eq/presets` | GET | Lista presetów |
| `/api/radio/stations` | GET/POST | Stacje |
| `/api/radio/stations/{id}` | DELETE | Usuń stację |
| `/api/radio/stations/{id}/favorite` | POST | Ulubiona |
| `/api/radio/play` | POST | Odtwarzaj stację |
| `/api/radio/stop` | POST | Stop |
| `/api/bluetooth/devices` | GET | Lista urządzeń |
| `/api/bluetooth/scan` | POST | Skanuj |
| `/api/bluetooth/pair` | POST | Paruj |
| `/api/bluetooth/connect` | POST | Połącz |
| `/api/bluetooth/mode` | POST | sink/source |
| `/api/network/status` | GET | Status WiFi |
| `/api/network/scan` | GET | Skanuj sieci |
| `/api/network/connect` | POST | Połącz z WiFi |
| `/api/system/reboot` | POST | Reboot |
| `/api/system/info` | GET | CPU/RAM/Temp |

## WebSocket events

**Server → Client:**
- `status` — pełny status co 3s
- `state` — zmiana stanu źródła
- `meta` — tytuł/artysta (radio ICY)
- `volume` — zmiana głośności
- `source` — zmiana źródła
- `eq` — zmiana EQ
- `ir` — zdarzenie pilota

**Client → Server:**
- `play_radio` — `{url, name}`
- `stop`
- `set_volume` — `{volume}`
- `set_source` — `{source}`
- `set_eq` — `{source, gains[10]}`

## UART protokół (RPi ↔ RP2040)

**RPi → RP2040:**
```json
{"cmd":"state","source":"radio","title":"Coldplay","volume":75,"state":"playing"}
{"cmd":"eq","gains":[4,2,0,0,0,0,0,1,2,3]}
{"cmd":"led","mode":"vu","data":[12,45,78,90,60,40,20,10]}
{"cmd":"display","line1":"RMF FM","line2":"Coldplay - Scientist"}
{"cmd":"volume","value":75}
```

**RP2040 → RPi:**
```json
{"evt":"encoder","id":0,"delta":1}
{"evt":"encoder","id":1,"delta":-1}
{"evt":"switch","id":3,"state":1}
{"evt":"ir","code":"0xAB12"}
{"evt":"touch","x":120,"y":85}
```

## Motyw kolorystyczny (Web + RP2040)

| Rola | Kolor |
|------|-------|
| Tło | `#0d0f14` |
| Karta | `#111520` |
| Akcent niebieski | `#2d8cf0` |
| Akcent pomarańczowy | `#f0820d` |
| Tekst | `#e8eaf0` |
| VU peak | `#f0820d` |
| Playing | `#22c55e` |
