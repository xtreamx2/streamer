
---

# 🇬🇧 **README_EN.md**

```markdown
# Streamer Audio – Raspberry Pi I2S DAC + OLED

Streamer Audio is an open‑source audio player for Raspberry Pi featuring:
- I2S DAC support (PCM5102A / Hifiberry DAC)
- MPD/MPC backend
- SSD1306/SSD1309 OLED display
- Automatic audio test
- Modular configuration via `gpio.json`
- Full installation logging and hardware autodetection

The project focuses on:
- clarity,
- automation,
- documentation,
- modifiability,
- full auditability.

---

## 📦 Features

- Automatic installation of MPD, MPC, Python libs and GStreamer
- Raspberry Pi, DAC and OLED autodetection
- Automatic configuration of `/boot/firmware/config.txt`
- Disabling onboard audio (dtparam=audio=on)
- Generating `test.wav` (800 Hz / 0.5 s)
- DAC test with MPD disabled
- Adding Polish radio station (Radio 357)
- Logging all steps to `streamer/logs/install.log`
- Creating `gpio.json` as a central configuration source
- Moving installer to `streamer/installer/`
- Updating `change_log`

---

## 🧰 Hardware Requirements

- Raspberry Pi 3 / 4 / Zero 2 W / CM4
- PCM5102A or compatible I2S DAC (Hifiberry DAC)
- SSD1306/SSD1309 OLED (I2C, address 0x3C)
- 5V power supply
- I2S wiring:
  - BCK → GPIO18
  - LRCK → GPIO19
  - DIN → GPIO21
  - GND → GND
  - VIN → 5V

---

## 🖥️ OS Requirements

- Raspberry Pi OS Bookworm or newer
- Internet connection
- sudo privileges

---

## 🚀 Installation

### Install via `curl`

```bash
curl -s https://gitlab.com/aloisy/streamer/-/raw/master/start_install.sh -o install.sh
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
 └── README_EN.md

Licensing
The project uses three licensing layers:

Component	License
Hardware (schematics, PCB)	CERN-OHL-S
Software (scripts, Python)	GPLv3
Documentation	CC-BY-SA 4.0

Roadmap
Encoder and button support

Multi‑DAC support (PCM5122, ES9023)

Offline standalone mode

WebUI configuration panel

Automatic updates

🐞 Issues
Bug reports and feature requests are welcome.