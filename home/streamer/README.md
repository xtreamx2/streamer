# 🎵 Tom's Streamer Audio

**Data ukończenia:** 2026-03-05 
**Status:** ✅ ALPHA COMPLETE
**Wersja:** v0.9.1 (Alpha)

## 🚀 Cechy Główne
- [x] MPD + Internet Radio Streaming
- [x] CamillaDSP 7-Band EQ Processing
- [x] Flask WWW UI (Port 8000)
- [x] Auto-Recover Watchdog
- [x] System Monitoring (`monit`)
- [x] Full Backup & Documentation

## 🔜 v0.9.2 Roadmap
- [ ] EQ Sliders w UI (sterowanie CamillaDSP)
- [ ] Bluetooth jako źródło audio
- [ ] Selector źródeł (Radio/BT/Analog)
- [ ] Phase 2: ESP32 + LCD Touch Interface

## 📖 Opis

Internet Radio Streamer z EQ (CamillaDSP) i WWW UI (Flask).

**Hardware:**
- Raspberry Pi 3/4
- PCM5102 DAC (I2S)
- Słuchawki głośniki

**Software:**
- MPD (Music Player Daemon)
- CamillaDSP v3.0.1 (EQ 7-band)
- Flask + SocketIO (WWW UI)
- ALSA Loopback (audio chain)

## ✅ Working Features

| Feature | Status | Notes |
|---------|--------|-------|
| MPD streaming | ✅ | Internet radio |
| CamillaDSP EQ | ✅ | 7-band (bass, treble, 5x PEQ) |
| Flask WWW UI | ✅ | Port 8000 |
| Radio CRUD | ✅ | Add/delete/favorites |
| VU Meter | ⚠️ | Simulated data (Phase 2: real FFT) |
| Theme toggle | ✅ | Dark/Light |
| ALSA Loopback | ✅ | MPD → CamillaDSP → DAC |

**Known issues:**
- Hi-Res streams may occasionally drop on track change (buffer limits)
- ESP32 + LCD hardware UI (Phase 2)

✅ VU Meter - czytelny layout (32 słupki, poziomo)
✅ Gradient colors - niebieski→żółty→czerwony
✅ VU/Spectrum toggle - przełącznik działa
✅ Theme toggle - dark/light working
✅ Radio CRUD + favorites - działa
✅ CamillaDSP EQ - działa (7-band)
✅ Flask API - działa
✅ Backup + README - gotowe

Hi-Res Internet Radio Streamer with CamillaDSP EQ

## 📁 Project Structure

/home/tom/streamer/
├── app.py # Flask app (WWW UI + API)
├── radio_handler.py # Radio stations CRUD
├── vu_handler.py # VU meter logic (simulated)
├── radio_watchdog.sh # Auto-reconnect na track change
├── templates/
│ └── index.html # WWW UI
├── radio/
│ ├── stations.json # Radio stations list
│ └── favorites.json # Favorites
├── logs/
│ └── watchdog.log # Watchdog logs
├── static/
│ ├── css/
│ └── js/
├── README.md
└── backups/
└── (tar.gz archiwa)

## 🔧 Quick Start
```bash

# Start MPD
sudo systemctl start mpd

# Start CamillaDSP
sudo camilladsp /etc/camilladsp/config.yml &

# Start Flask
cd ~/streamer && python3 app.py &

# Open browser
http://<ip_streamer>:8000/

🎚️ EQ Config
Location: /etc/camilladsp/config.yml
Bass: Highshelf @ 200Hz
Treble: Lowshelf @ 4000Hz
5-band PEQ: 100, 500, 1000, 4000, 10000 Hz
Max gain: +3 to +6dB (avoid clipping!)

##
🚀 Phase 2 (TODO)
ESP32 + LCD hardware UI
UART communication (ESP32 ↔ Pi)
Physical encoders + buttons
IR remote control
Bluetooth audio input
Analog input (PCM1808)
##

📊 Changelog
v0.9.1 (2026-03-03) - Alpha Complete
✅ MPD + Internet Radio streaming
✅ CamillaDSP v3.0.1 EQ (7-band)
✅ Flask WWW UI (play/pause/volume/radio)
✅ VU Meter (64 bands, Winamp-style gradient)
✅ Dark/Light theme toggle
✅ Radio CRUD + favorites (JSON)
✅ ALSA Loopback chain
✅ Radio watchdog (auto-reconnect na track change)
⚠️ VU Meter: simulated data (Phase 2: real FFT from audio)
v0.9.0 (2026-03-02) - Core Working
✅ MPD configured
✅ CamillaDSP config (v3.0.1 format)
✅ Flask basic API
v0.1.0-v0.8.x (2026-02-xx) - Development
Multiple iterations, hardware testing, BOM finalization
v0.9.2 roadmap added - EQ sliders + dynamic source selection
