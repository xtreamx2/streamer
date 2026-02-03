#!/bin/bash
clear

SOFT_VERSION="0.07a1"

RED="\e[31m"
GREEN="\e[32m"
YELLOW="\e[33m"
BLUE="\e[34m"
RESET="\e[0m"

STREAMER_DIR="$HOME/streamer"
LOG_DIR="$STREAMER_DIR/logs"
CONFIG_DIR="$STREAMER_DIR/config"
INSTALLER_DIR="$STREAMER_DIR/installer"
CHANGELOG_DIR="$STREAMER_DIR/changelog"
MEDIA_DIR="$STREAMER_DIR/media"
OLED_DIR="$STREAMER_DIR/oled"

LOGFILE="$LOG_DIR/install.log"

if [ -f /boot/firmware/config.txt ]; then
    CONFIG_TXT="/boot/firmware/config.txt"
else
    CONFIG_TXT="/boot/config.txt"
fi

REPO_BASE="https://gitlab.com/aloisy/streamer/-/raw/master"

log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S')  $1" | tee -a "$LOGFILE"
}

pause_step() {
    echo ""
    read -p "ENTER = kontynuuj, q = przerwij: " choice
    if [ "$choice" = "q" ]; then
        log "Instalacja przerwana przez użytkownika."
        exit 1
    fi
}

spinner() {
    local pid=$1
    local delay=0.15
    local spin='|/-\'
    while kill -0 $pid 2>/dev/null; do
        for i in $(seq 0 3); do
            printf "\r${BLUE}Przetwarzanie...${RESET} ${spin:$i:1}"
            sleep $delay
        done
    done
    printf "\r${GREEN}Zakończono.${RESET}\n"
}

ensure_line() {
    local line="$1"
    local file="$2"
    if ! grep -Fxq "$line" "$file"; then
        echo "$line" | sudo tee -a "$file" >/dev/null
        log "Dodano do $(basename "$file"): $line"
        return 0
    fi
    return 1
}

echo -e "${BLUE}=============================================="
echo -e " STREAMER AUDIO – Instalator v$SOFT_VERSION"
echo -e "==============================================${RESET}"
pause_step

mkdir -p "$LOG_DIR" "$CONFIG_DIR" "$INSTALLER_DIR" "$CHANGELOG_DIR" "$MEDIA_DIR" \
         "$OLED_DIR/graphics/anim"
touch "$LOGFILE"
log "Struktura katalogów gotowa."

echo -e "${BLUE}Krok 1: Aktualizacja systemu${RESET}"
(sudo apt update && sudo apt upgrade -y) &
spinner $!
log "System zaktualizowany."
pause_step

echo -e "${BLUE}Krok 2: Instalacja pakietów${RESET}"
(sudo apt install -y git python3 python3-pip python3-venv \
    mpd mpc alsa-utils i2c-tools jq curl wget unzip sox) &
spinner $!
log "Pakiety zainstalowane."
pause_step

echo -e "${BLUE}Krok 3: Instalacja bibliotek Python${RESET}"
(pip3 install --break-system-packages \
    python-mpd2 RPi.GPIO pillow adafruit-circuitpython-ssd1306 requests) &
spinner $!
log "Biblioteki Python zainstalowane."
pause_step

echo -e "${BLUE}Krok 4: Synchronizacja config.txt${RESET}"

CHANGES=0
ensure_line "dtoverlay=hifiberry-dac" "$CONFIG_TXT" && CHANGES=1
ensure_line "dtparam=i2c_arm=on" "$CONFIG_TXT" && CHANGES=1
ensure_line "dtparam=i2s=on" "$CONFIG_TXT" && CHANGES=1

if grep -q "^dtparam=audio=on" "$CONFIG_TXT"; then
    sudo sed -i 's/^dtparam=audio=on/#dtparam=audio=on/' "$CONFIG_TXT"
    log "Wyłączono wbudowane audio."
    CHANGES=1
fi

log "Synchronizacja config.txt zakończona."
pause_step

echo -e "${BLUE}Krok 5: Restart MPD${RESET}"
sudo systemctl restart mpd
mpc stop >/dev/null 2>&1
log "MPD uruchomiony i zatrzymany."
pause_step

echo -e "${BLUE}Krok 6: Autodetekcja DAC${RESET}"
if aplay -l | grep -qi "sndrpihifiberry"; then
    log "Wykryto DAC: PCM5102A"
else
    log "Nie wykryto DAC!"
fi
pause_step

echo -e "${BLUE}Krok 7: Autodetekcja OLED${RESET}"
if sudo i2cdetect -y 1 | grep -q "3c"; then
    log "OLED wykryty."
    OLED_PRESENT=1
else
    log "OLED nie wykryty."
    OLED_PRESENT=0
fi
pause_step

echo -e "${BLUE}Krok 8: Dodanie stacji radiowej${RESET}"

RADIO_URL="http://stream.rcs.revma.com/ye5kghkgcm0uv"

if mpc playlist | grep -q "$RADIO_URL"; then
    RADIO_NEW=0
    log "Stacja radiowa już istnieje."
else
    mpc clear
    mpc add "$RADIO_URL"

    if ! mpc lsplaylists | grep -q "^radio$"; then
        mpc save radio
    fi

    mpc volume 30
    mpc play
    RADIO_NEW=1
    log "Dodano i uruchomiono Radio 357."
fi

pause_step

echo -e "${BLUE}Krok 9: Test DAC${RESET}"

TEST_WAV="$MEDIA_DIR/test.wav"

log "Generuję test.wav (400 Hz, stereo, 0.5 s)."
sox -n -r 48000 -b 16 -c 2 "$TEST_WAV" synth 0.5 sine 400

mpc stop >/dev/null 2>&1
sudo systemctl stop mpd

aplay "$TEST_WAV" -D plughw:0,0
log "Test DAC zakończony."
pause_step

echo -e "${BLUE}Krok 10: Test OLED${RESET}"

if [ "$OLED_PRESENT" -eq 1 ]; then
python3 << 'EOF'
import time
import board, busio
from adafruit_ssd1306 import SSD1306_I2C
from PIL import Image, ImageDraw, ImageFont

try:
    i2c = busio.I2C(board.SCL, board.SDA)
    display = SSD1306_I2C(128, 64, i2c, addr=0x3C)
except Exception as e:
    print("OLED not detected:", e)
    exit(0)

display.contrast(1)

image = Image.new("1", (128, 64))
draw = ImageDraw.Draw(image)
font = ImageFont.load_default()

text = "STREAMER"
bbox = draw.textbbox((0, 0), text, font=font)
w = bbox[2] - bbox[0]
h = bbox[3] - bbox[1]

draw.text(((128 - w) // 2, (64 - h) // 2), text, font=font, fill=255)

display.image(image)
display.show()

time.sleep(2)

display.fill(0)
display.show()
EOF
    log "OLED test zakończony (niska jasność + wygaszenie)."
else
    log "OLED pominięty – brak urządzenia."
fi

pause_step

echo -e "${BLUE}Krok 11: Pobieranie changelog${RESET}"

CHANGELOG_URL="$REPO_BASE/change_log"
curl -L -s "$CHANGELOG_URL" -o "$CHANGELOG_DIR/latest.txt"

log "Pobrano changelog."
pause_step

echo -e "${BLUE}Krok 12: Pobieranie OLED daemona, configu i grafik${RESET}"

curl -L -s "$REPO_BASE/oled/oled_daemon.py" -o "$OLED_DIR/oled_daemon.py"
curl -L -s "$REPO_BASE/oled/config.json" -o "$OLED_DIR/config.json"

curl -L -s "$REPO_BASE/oled/graphics/logo.pbm"   -o "$OLED_DIR/graphics/logo.pbm"
curl -L -s "$REPO_BASE/oled/graphics/volume.pbm" -o "$OLED_DIR/graphics/volume.pbm"
curl -L -s "$REPO_BASE/oled/graphics/play.pbm"   -o "$OLED_DIR/graphics/play.pbm"
curl -L -s "$REPO_BASE/oled/graphics/pause.pbm"  -o "$OLED_DIR/graphics/pause.pbm"
curl -L -s "$REPO_BASE/oled/graphics/radio.pbm"  -o "$OLED_DIR/graphics/radio.pbm"
curl -L -s "$REPO_BASE/oled/graphics/khz.pbm"    -o "$OLED_DIR/graphics/khz.pbm"
curl -L -s "$REPO_BASE/oled/graphics/bits.pbm"   -o "$OLED_DIR/graphics/bits.pbm"
curl -L -s "$REPO_BASE/oled/graphics/time.pbm"   -o "$OLED_DIR/graphics/time.pbm"

# animacja (jeśli jest)
curl -L -s "$REPO_BASE/oled/graphics/anim/frame01.pbm" -o "$OLED_DIR/graphics/anim/frame01.pbm"
curl -L -s "$REPO_BASE/oled/graphics/anim/frame02.pbm" -o "$OLED_DIR/graphics/anim/frame02.pbm"
curl -L -s "$REPO_BASE/oled/graphics/anim/frame03.pbm" -o "$OLED_DIR/graphics/anim/frame03.pbm"

chmod +x "$OLED_DIR/oled_daemon.py"

log "OLED daemon, config i grafiki pobrane."
pause_step

echo -e "${BLUE}Krok 13: Instalacja usługi systemd dla OLED${RESET}"

TMP_SERVICE="/tmp/oled.service"
curl -L -s "$REPO_BASE/systemd/oled.service" -o "$TMP_SERVICE"

CURRENT_USER="$(whoami)"
sudo sed -i "s/%i/$CURRENT_USER/g" "$TMP_SERVICE"

sudo mv "$TMP_SERVICE" /etc/systemd/system/oled.service
sudo systemctl daemon-reload
sudo systemctl enable oled.service
sudo systemctl restart oled.service

log "Usługa OLED zainstalowana i uruchomiona."
pause_step

echo -e "${BLUE}Krok 14: Przenoszenie instalatora${RESET}"

SCRIPT_NAME="$(basename "$0")"
TARGET_PATH="$INSTALLER_DIR/$SCRIPT_NAME"

if [ "$(realpath "$0")" != "$TARGET_PATH" ]; then
    cp "$0" "$TARGET_PATH"
    rm "$0"
    log "Instalator przeniesiony do $TARGET_PATH"
fi

pause_step

mpc stop >/dev/null 2>&1

echo -e "${GREEN}=============================================="
echo -e " INSTALACJA ZAKOŃCZONA SUKCESEM"
echo -e " Log: $LOGFILE"
echo -e "${GREEN}==============================================${RESET}"

log "=== Instalacja zakończona pomyślnie ==="
