#!/bin/bash
if [ -z "${BASH_VERSION:-}" ]; then
    echo "Ten instalator wymaga bash."
    exit 1
fi
set -o pipefail
clear

SOFT_VERSION="0.08a"

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
CHANGELOG_SOURCE="$STREAMER_DIR/change_log"
MEDIA_DIR="$STREAMER_DIR/media"
OLED_DIR="$STREAMER_DIR/oled"

LOGFILE="$LOG_DIR/install.log"

if [ -f /boot/firmware/config.txt ]; then
    CONFIG_TXT="/boot/firmware/config.txt"
else
    CONFIG_TXT="/boot/config.txt"
fi

REPO_GIT_DEFAULT="https://github.com/xtreamx2/streamer.git"
REPO_GIT="${REPO_GIT:-$REPO_GIT_DEFAULT}"
REPO_BRANCH="${REPO_BRANCH:-main}"
if [ -z "$REPO_BRANCH" ]; then
    REPO_BRANCH="main"
fi

log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S')  $1" | tee -a "$LOGFILE"
}
export -f log

pause_step() {
    echo ""
    if [ ! -t 0 ]; then
        return 0
    fi
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

echo -e "${BLUE}Krok 0: Zatrzymanie usług na czas instalacji${RESET}"
if systemctl is-active --quiet oled.service; then
    sudo systemctl stop oled.service
    log "Usługa OLED zatrzymana na czas instalacji."
fi
if systemctl is-active --quiet input.service; then
    sudo systemctl stop input.service
    log "Usługa INPUT zatrzymana na czas instalacji."
fi

echo -e "${BLUE}Krok 0a: Ekran instalacji${RESET}"
python3 << 'EOF'
import time
import board, busio
from adafruit_ssd1306 import SSD1306_I2C
from PIL import Image, ImageDraw, ImageFont

try:
    i2c = busio.I2C(board.SCL, board.SDA)
    display = SSD1306_I2C(128, 64, i2c, addr=0x3C)
except Exception:
    raise SystemExit(0)

display.contrast(200)
font = ImageFont.load_default()

spinner = ["|", "/", "-", "\\"]
for _ in range(10):
    for frame in spinner:
        image = Image.new("1", (128, 64))
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), "Updating...", font=font, fill=255)
        draw.text((0, 16), f"[{frame}]", font=font, fill=255)
        display.image(image)
        display.show()
        time.sleep(0.2)
EOF

echo -e "${BLUE}Krok 1: Aktualizacja systemu${RESET}"
(sudo apt update && sudo apt upgrade -y) &
spinner $!
log "System zaktualizowany."
pause_step

echo -e "${BLUE}Krok 2: Instalacja pakietów${RESET}"
(sudo apt install -y git python3 python3-pip python3-venv python3-pil \
    mpd mpc alsa-utils i2c-tools jq curl wget unzip sox) &
spinner $!
log "Pakiety zainstalowane."
pause_step

echo -e "${BLUE}Krok 3: Instalacja bibliotek Python${RESET}"
(pip3 install --break-system-packages --prefer-binary \
    python-mpd2 RPi.GPIO adafruit-circuitpython-ssd1306 requests) &
spinner $!
log "Biblioteki Python zainstalowane."
pause_step

echo -e "${BLUE}Krok 4: Synchronizacja config.txt${RESET}"

CHANGES=0
ensure_line "dtoverlay=hifiberry-dac" "$CONFIG_TXT" && CHANGES=1
if grep -q "^#dtparam=i2c_arm=on" "$CONFIG_TXT"; then
    sudo sed -i 's/^#dtparam=i2c_arm=on/dtparam=i2c_arm=on/' "$CONFIG_TXT"
    log "Odkomentowano dtparam=i2c_arm=on."
    CHANGES=1
else
    ensure_line "dtparam=i2c_arm=on" "$CONFIG_TXT" && CHANGES=1
fi

if grep -q "^#dtparam=i2s=on" "$CONFIG_TXT"; then
    sudo sed -i 's/^#dtparam=i2s=on/dtparam=i2s=on/' "$CONFIG_TXT"
    log "Odkomentowano dtparam=i2s=on."
    CHANGES=1
else
    ensure_line "dtparam=i2s=on" "$CONFIG_TXT" && CHANGES=1
fi

if grep -q "^dtparam=audio=on" "$CONFIG_TXT"; then
    sudo sed -i 's/^dtparam=audio=on/#dtparam=audio=on/' "$CONFIG_TXT"
    log "Wyłączono wbudowane audio."
    CHANGES=1
fi

log "Synchronizacja config.txt zakończona."

MODULES_LOAD_DIR="/etc/modules-load.d"
MODULES_LOAD_FILE="$MODULES_LOAD_DIR/streamer.conf"
if [ -d "$MODULES_LOAD_DIR" ]; then
    sudo touch "$MODULES_LOAD_FILE"
    ensure_line "i2c-dev" "$MODULES_LOAD_FILE" && CHANGES=1
    ensure_line "i2c-bcm2835" "$MODULES_LOAD_FILE" && CHANGES=1
    log "Sprawdzono $MODULES_LOAD_FILE (I2C)."
elif [ -f /etc/modules ]; then
    ensure_line "i2c-dev" /etc/modules && CHANGES=1
    ensure_line "i2c-bcm2835" /etc/modules && CHANGES=1
    log "Sprawdzono /etc/modules (I2C)."
fi

if ! ls /dev/i2c-1 >/dev/null 2>&1; then
    sudo modprobe i2c-dev
    sudo modprobe i2c-bcm2835
    if ls /dev/i2c-1 >/dev/null 2>&1; then
        log "I2C aktywne (załadowano moduły kernel)."
    else
        log "Uwaga: /dev/i2c-1 nadal niedostępne — może być wymagany restart."
    fi
else
    log "I2C już aktywne (/dev/i2c-1 dostępne)."
fi

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

echo -e "${BLUE}Krok 11: Pobieranie i aktualizacja projektu STREAMER${RESET}"

TMP_DIR=$(mktemp -d)
log "Pobieranie repozytorium: $REPO_GIT (branch: $REPO_BRANCH)"
CLONE_OK=0
if GIT_TERMINAL_PROMPT=0 git clone --depth=1 --branch "$REPO_BRANCH" \
    "$REPO_GIT" "$TMP_DIR" 2>&1 | tee -a "$LOGFILE"; then
echo -e "${BLUE}Krok 10: Test OLED${RESET}"

if [ "$OLED_PRESENT" -eq 1 ]; then
python3 <<'EOF'
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
    log "Brak pliku change_log w repozytorium."
fi

pause_step

echo -e "${BLUE}Krok 13: Instalacja usług systemd${RESET}"

CURRENT_USER="$(whoami)"

if [ -f "$STREAMER_DIR/systemd/oled.service" ]; then
    sudo cp "$STREAMER_DIR/systemd/oled.service" /etc/systemd/system/oled.service
    sudo sed -i "s/%i/$CURRENT_USER/g" /etc/systemd/system/oled.service
    sudo systemctl enable oled.service
    sudo systemctl restart oled.service
    log "Usługa OLED zainstalowana i uruchomiona."
else
    log "Brak pliku systemd/oled.service w repozytorium."
fi

if [ -f "$STREAMER_DIR/systemd/input.service" ]; then
    sudo cp "$STREAMER_DIR/systemd/input.service" /etc/systemd/system/input.service
    sudo sed -i "s/%i/$CURRENT_USER/g" /etc/systemd/system/input.service
    sudo systemctl enable input.service
    sudo systemctl restart input.service
    log "Usługa INPUT zainstalowana i uruchomiona."
else
    log "Brak pliku systemd/input.service w repozytorium (pomijam)."
fi

sudo systemctl daemon-reload
pause_step

echo -e "${BLUE}Krok 14: Przenoszenie instalatora${RESET}"

SCRIPT_PATH="$(realpath "$0" 2>/dev/null || true)"
SCRIPT_NAME="$(basename "$0")"
TARGET_PATH="$INSTALLER_DIR/${SCRIPT_NAME:-start_install.sh}"

if [ "$SCRIPT_NAME" = "bash" ] || [ ! -f "$SCRIPT_PATH" ]; then
    log "Uruchomiono instalator z wejścia standardowego — pomijam przenoszenie pliku."
elif [ "$SCRIPT_PATH" != "$TARGET_PATH" ]; then
    cp "$SCRIPT_PATH" "$TARGET_PATH"
    rm "$SCRIPT_PATH"
    log "Instalator przeniesiony do $TARGET_PATH"
fi

pause_step

echo -e "${BLUE}Krok 15: Przywracanie usług${RESET}"
if [ -f "$STREAMER_DIR/systemd/oled.service" ]; then
    sudo systemctl restart oled.service
    log "Usługa OLED uruchomiona po instalacji."
fi
if [ -f "$STREAMER_DIR/systemd/input.service" ]; then
    sudo systemctl restart input.service
    log "Usługa INPUT uruchomiona po instalacji."
fi

pause_step

mpc stop >/dev/null 2>&1

echo -e "${GREEN}=============================================="
echo -e " INSTALACJA ZAKOŃCZONA SUKCESEM"
echo -e " Log: $LOGFILE"
echo -e "${GREEN}==============================================${RESET}"

log "=== Instalacja zakończona pomyślnie ==="
