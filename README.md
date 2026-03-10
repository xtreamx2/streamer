# 🎵 Tom's Streamer Audio

**Data ukończenia:** 2026-03-05 
**Status:** ✅ ALPHA COMPLETE
**Wersja:** v0.10.3.22 (Alpha)

## 🚀 Cechy Główne
- [x] MPD + Internet Radio Streaming ✅
- [x] Flask WWW UI (Port 8000) ✅
- [x] Documentation

## 🔜 v0.10.5 Roadmap
- [x] EQ Sliders w UI ✅
- [x] Bluetooth jako źródło audio ✅
- [x] Selector źródeł (Radio/BT/Analog) ✅
- [ ] Phase 2: RP2040 + LCD Touch Interface (Brak hardware jeszcze)

## 📖 Opis

Internet Radio Streamer z EQ) i WWW UI (Flask).

**Hardware:**
- Raspberry Pi 3
- PCM5102 DAC (I2S)
- Słuchawki głośniki

**Software:**
- GStreamer (Music Player Daemon with EQ 10-band
- Flask + SocketIO (WWW UI)
- ALSA Loopback (audio chain)

## ✅ Working Features

| Feature | Status | Notes |
|---------|--------|-------|
| MPD streaming | ✅ | Internet radio |
| Flask WWW UI | ✅ | Port 8000 |
| Radio CRUD | ✅ | Add/delete/favorites |
| VU Meter | ⚠️ | wirk but not good |
| Theme toggle | ⚠️ | Dark only |

**Known issues:**
- Spectrum analiser - not working
- RP2040 + LCD hardware UI (Phase 2)

✅ VU Meter - czytelny layout (2 słupki, poziomo)
✅ Gradient colors - niebieski→żółty→czerwony
✅ VU/Spectrum toggle - przełącznik działa (analizator już nie)
✅ Radio CRUR + favorites - działa
✅ EQ - działa (10-band)
✅ Flask API - działa
✅ Backup + README - gotowe

Hi-Res Internet Radio Streamer with EQ

## 📁 Project Structure

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

## 🔧 Quick Start
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

##
🚀 Phase 2 (TODO)
RP2040 + LCD hardware UI
UART communication (RP ↔ Pi)
Physical encoders + buttons
IR remote control
Analog input (PCM1808)
##

📊 Changelog
v0.10.3.22:

Zakładka -Streamer · TrancePulse dla radia (nazwa stacji), Streamer · Bluetooth dla BT itd.

Stream info -kHz i Stereo/ch z GStreamer



v0.10.3.21:
- Meters - jeden endpoint /api/meters zamiast dwóch, polling co 100ms — koniec z ERR_CONNECTION_RESET
- BT/Radio konflikt ALSA - bluealsa-aplay automatycznie zatrzymywany gdy radio aktywne, wznawiany gdy BT aktywne
- Spectrum - te same dane, ale teraz serwer nie pada pod obciążeniem

v0.10.3.20:
- IP - fallback na eth0/wlan0/end0, zwraca IP niezależnie od interfejsu
- Spectrum - prawdziwy FFT z GStreamer spectrum element (32 pasma), endpoint /api/spectrum, canvas rysuje realne dane
- VU polling - 80ms zamiast 60ms

v0.10.3.19 changelog: 
Bugfix:
- usunięty subprocess bluealsa-aplay z kodu, audio BT obsługuje teraz systemowy serwis.
Podsumowanie stanu BT:
- bluealsa.service -daemon BlueZ A2DP
- bluealsa-aplay.service -przekazuje audio na hw:sndrpihifiberry,0 (skonfigurowany przez override)
- Streamer -obsługuje tylko parowanie/connect przez D-Bus, audio zostawia systemowi

v0.10.3.18 changelog:
- Stacja - przywracana przy starcie zawsze, oraz automatycznie gdy przełączasz z BT/innego źródła na radio
- Głośność - przywracana do wszystkich sources przy starcie
- Śmieciowy katalog - usunięty z paczki (usuń też na malinie: rm -rf "/home/$USER/streamer/{core,sources,api,web")

v0.10.3.17 changelog:
- Stacja - przywracana zawsze przy starcie, niezależnie od last_source
- BT audio - bluealsa-aplay w pętli wątkowej, automatycznie restartuje gdy telefon zaczyna/kończy grać
- Spectrum - usunięty roundRect (niekompatybilny ze starszym Chromium), naprawiony rozmiar canvas

v0.10.3.16 changelog:
- Spectrum/VU - chip VU domyślnie on, container widoczny od startu
- IP - usunięte błędne pole IP4 z nmcli
- BT audio - bluealsa-aplay uruchamiany jako subprocess przy activate, zatrzymywany przy deactivate

v0.10.3.15 changelog:
- Peak hold - marker przeniesiony poza maskę CSS, biały z glow, widoczny
- Spectrum - 32 pasma animowane przez requestAnimationFrame, kształt EQ-like (basy/górne wzmocnione), peak ticki białe, ten sam gradient co VU, płynne opadanie

v0.10.3.14 changelog:
- Gradient zawsze rozłożony na całej szerokości tracku (niebieski → żółty → czerwony)
- Ciemna maska CSS ::after odkrywa gradient proporcjonalnie do poziomu
- Peak marker biały z delikatnym glow
- Brak JS manipulacji kolorem — wszystko w CSS

v0.10.3.10 changelog:
- Sieć - naprawiony parser nmcli (obsługuje connected (externally))
- Loudness - endpoint /api/setting + zapis w config + przywracanie przy starcie
- Ostatnia stacja radiowa - przywracana automatycznie po restarcie
- BT - auto-trust przy connect

v0.10.3 changelog:
New:
- parowanie BT
- W-Fi conect

Bugfix:
- Sieć — usunięte hardkodowane dane, dynamiczne ID, filtr BT z listy urządzeń
- Głośność — była zapisywana ale teraz też last_station_id jest zapisywane przy każdym play
- Ostatnia stacja — przywracana automatycznie przy starcie
- Loudness — prawdziwy endpoint /api/setting, zapisywany w config, przywracany przy starcie
- BT connect — auto-trust przed połączeniem

v0.10.2 changelog:
Bugfix:
- problemy z interface
- czasami apka zailcza crush
- znikające podstrony

v0.10.1 changelog:
- interfejs WWW.
- działa Radio
- uruchomiona obsługa bluetooth
- stabilne 60° na procesorze (optymalna praca)

bug:
- problemy z interface
- czasami apka zailcza crush
- znikające podstrony
