# Streamer Audio – Raspberry Pi I2S DAC + OLED

Streamer Audio to otwarto‑źródłowy projekt odtwarzacza audio opartego na Raspberry Pi, z obsługą:
- DAC I2S (PCM5102A / Hifiberry DAC)
- MPD/MPC
- OLED SSD1306/SSD1309
- Automatycznego testu audio
- Modularnej konfiguracji (gpio.json)
- Instalatora z pełnym logowaniem i autodetekcją

Projekt jest rozwijany z naciskiem na:
- przejrzystość,
- automatyzację,
- dokumentację,
- łatwość modyfikacji,
- pełną audytowalność zmian.

---

## 📦 Funkcje

- Automatyczna instalacja MPD, MPC, Python, bibliotek i GStreamera
- Autodetekcja Raspberry Pi, DAC I2S i OLED
- Automatyczna konfiguracja `/boot/firmware/config.txt`
- Wyłączenie wbudowanego audio (dtparam=audio=on)
- Generowanie testowego pliku `test.wav` (800 Hz / 0.5 s)
- Test DAC z pominięciem MPD
- Dodanie polskiej stacji radiowej (Radio 357)
- Logowanie wszystkich kroków do `streamer/logs/install.log`
- Tworzenie `gpio.json` jako centralnego źródła konfiguracji
- Przenoszenie instalatora do `streamer/installer/`
- Aktualizacja `change_log`

---

## 🧰 Wymagania sprzętowe

- Raspberry Pi 1 -5 / Zero W / Zero 2 W / CM4
- DAC I2S PCM5102A lub kompatybilny (Hifiberry DAC)
- OLED SSD1306/SSD1309 (I2C, adres 0x3C)
- Zasilanie 5V
- Połączenia I2S:
    - BCK → GPIO18
    - LRCK → GPIO19
    - DIN → GPIO21
    - GND → GND
    - VIN → 5V

---

## 🖥️ Wymagania systemowe

- Raspberry Pi OS Bookworm lub nowszy
- Dostęp do internetu
- Uprawnienia sudo

---

## 🚀 Instalacja

### Instalacja przez `curl`

```bash
curl -s https://gitlab.com/aloisy/start_install.sh -o install.sh
chmod +x install.sh
./install.sh


streamer/
 ├── config/
 │    └── gpio.json
 ├── logs/
 │    └── install.log
 ├── media/
 │    └── test.wav
 ├── installer/
 │    └── start_install.sh
 ├── change_log
 └── README.md


Projekt składa się z trzech warstw licencyjnych:

Element	Licencja
Hardware (schematy, PCB)	CERN-OHL-S
Oprogramowanie (skrypty, Python)	GPLv3
Dokumentacja (README, opisy)	CC-BY-SA 4.0


Roadmap
Integracja enkodera i przycisków

Obsługa wielu DAC (PCM5122, ES9023)

Tryb „standalone” bez sieci

WebUI do konfiguracji

Automatyczne aktualizacje

🐞 Zgłaszanie błędów
Zgłoszenia i propozycje zmian mile widziane w Issues.