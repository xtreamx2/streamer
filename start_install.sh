#!/bin/bash
if [ -z "${BASH_VERSION:-}" ]; then
    echo "Ten instalator wymaga bash."
    exit 1
fi
set -o pipefail
clear

SOFT_VERSION="0.08a1b"

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
    read -p "ENTER = kontynuuj, Ctrl + C / q = przerwij: " choice
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

SPINNER_FLAG="/tmp/streamer_oled_spinner.stop"
SPINNER_SCRIPT="/tmp/streamer_oled_spinner.py"
rm -f "$SPINNER_FLAG"
cat <<'PY' > "$SPINNER_SCRIPT"
import time
import board, busio
from adafruit_ssd1306 import SSD1306_I2C
from PIL import Image, ImageDraw, ImageFont
import os

try:
    i2c = busio.I2C(board.SCL, board.SDA)
    display = SSD1306_I2C(128, 64, i2c, addr=0x3C)
except Exception:
    raise SystemExit(0)

display.contrast(200)
font = ImageFont.load_default()

spinner = ["|", "/", "-", "\\"]
flag = "/tmp/streamer_oled_spinner.stop"
while not os.path.exists(flag):
    for frame in spinner:
        if os.path.exists(flag):
            break
        image = Image.new("1", (128, 64))
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), "Updating...", font=font, fill=255)
        draw.text((0, 16), f"[{frame}]", font=font, fill=255)
        display.image(image)
        display.show()
        time.sleep(0.2)
PY
python3 "$SPINNER_SCRIPT" >/dev/null 2>&1 &
SPINNER_PID=$!
log "Ekran instalacji uruchomiony (spinner OLED w tle)."

echo -e "${BLUE}Krok 1: Aktualizacja systemu${RESET}"

pause_step
(sudo apt update && sudo apt upgrade -y) &
spinner $!
log "System zaktualizowany."
spinner $!

echo -e "${BLUE}Krok 2: Instalacja pakietów${RESET}"

(sudo apt install -y git python3 python3-pip python3-venv python3-pil \
    mpd mpc alsa-utils i2c-tools jq curl wget unzip sox) &
spinner $!
log "Pakiety zainstalowane."

echo -e "${BLUE}Krok 3: Instalacja bibliotek Python${RESET}"

(pip3 install --break-system-packages --prefer-binary \
    python-mpd2 RPi.GPIO adafruit-circuitpython-ssd1306 requests) &
spinner $!
log "Biblioteki Python zainstalowane."

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

echo -e "${BLUE}Krok 5: Restart MPD${RESET}"

sudo systemctl restart mpd
mpc stop >/dev/null 2>&1
log "MPD uruchomiony i zatrzymany."

echo -e "${BLUE}Krok 6: Autodetekcja DAC${RESET}"
if aplay -l | grep -qi "sndrpihifiberry"; then
    log "Wykryto DAC: PCM5102A"
else
    log "Nie wykryto DAC!"
fi

if [ -n "${SPINNER_PID:-}" ]; then
    touch "$SPINNER_FLAG"
    kill -9 "$SPINNER_PID" >/dev/null 2>&1 || true
    sleep 1
    unset SPINNER_PID
fi

# --- Krok 7: Autodetekcja OLED (bezpieczna wersja) ---
# Ensure oled.service not running so it doesn't auto-start spinner
if systemctl is-active --quiet oled.service; then
    sudo systemctl stop oled.service >/dev/null 2>&1 || true
    log "oled.service zatrzymany na czas detekcji."
fi

# Stop spinner process if running (zwalnia dostęp do wyświetlacza)
if [ -n "${SPINNER_PID:-}" ]; then
    touch "$SPINNER_FLAG"
    kill "$SPINNER_PID" >/dev/null 2>&1 || true
    unset SPINNER_PID
    sleep 0.3
    log "Spinner zatrzymany przed detekcją OLED."
fi

echo -e "${BLUE}Krok 7: Autodetekcja OLED${RESET}"

# Zapisz output i2cdetect do zmiennej i do logu — ułatwia diagnostykę
I2C_OUT=$(sudo i2cdetect -y 1 2>/dev/null || true)
echo "$I2C_OUT" | sed 's/^/    /' >> "$LOGFILE"
# wykryj 3c lub 3d (case-insensitive)
if echo "$I2C_OUT" | grep -qiE '(^|[[:space:]])3[cC]([[:space:]]|$)|(^|[[:space:]])3[dD]([[:space:]]|$)'; then
    log "OLED wykryty na magistrali I2C."
    OLED_PRESENT=1
else
    log "OLED nie wykryty (i2cdetect nie zwrócił adresu 3c/3d)."
    OLED_PRESENT=0
fi

# Jeżeli wykryto urządzenie, uruchom hermetyczny test Pythona (zapisany do pliku i uruchomiony)
if [ "$OLED_PRESENT" -eq 1 ]; then
    OLED_TEST_SCRIPT="/tmp/streamer_oled_test.py"
    cat <<'PY' > "$OLED_TEST_SCRIPT"
import time
import board, busio
from adafruit_ssd1306 import SSD1306_I2C
from PIL import Image, ImageDraw, ImageFont

i2c = busio.I2C(board.SCL, board.SDA)
display = None
for addr in (0x3C, 0x3D):
    try:
        display = SSD1306_I2C(128, 64, i2c, addr=addr)
        print("OLED opened at 0x%02x" % addr)
        break
    except Exception as e:
        print("Open failed at 0x%02x: %s" % (addr, e))
if display is None:
    raise SystemExit(0)

display.contrast(1)
font = ImageFont.load_default()
image = Image.new("1", (128, 64))
draw = ImageDraw.Draw(image)
text = "STREAMER - TEST"
bbox = draw.textbbox((0, 0), text, font=font)
w = bbox[2] - bbox[0]
h = bbox[3] - bbox[1]
draw.text(((128 - w) // 2, (64 - h) // 2), text, font=font, fill=255)
display.image(image)
display.show()
time.sleep(2)
display.fill(0)
display.show()
PY
    python3 "$OLED_TEST_SCRIPT"
    log "OLED test zakończony (test wyświetlenia)."
else
    log "OLED pominięty – brak urządzenia."
fi

# Nie wznawiamy spinnera od razu: spinner ma być wznawiany dopiero gdy jest to potrzebne

echo -e "${BLUE}Krok 8: Dodanie stacji radiowej${RESET}"

RADIO_URL="http://stream.rcs.revma.com/ye5kghkgcm0uv"

# Najpierw sprawdź czy URL istnieje już w obecnej kolejce lub w zapisanych playlistach
if mpc playlist | grep -qF "$RADIO_URL" || mpc listall | grep -qF "$RADIO_URL"; then
    RADIO_NEW=0
    log "Stacja radiowa już istnieje."
else
    # dodaj do bieżącej kolejki i zapisz jako playlistę 'radio' (ale NIE odtwarzaj od razu)
    mpc add "$RADIO_URL" >/dev/null 2>&1 || log "Uwaga: nie udało się dodać URL do MPD"
    if ! mpc lsplaylists | grep -q "^radio$"; then
        mpc save radio >/dev/null 2>&1 || log "Uwaga: nie udało się zapisać playlisty 'radio'"
    fi
    RADIO_NEW=1
    log "Dodano stację Radio 357 (zapisano playlistę)."

    # Jeśli MPD ma aktywne wyjścia, możemy ewentualnie ustawić głośność — nie uruchamiamy odtwarzania automatycznie
    if mpc outputs | grep -qi "enabled"; then
        mpc volume 30 >/dev/null 2>&1 || true
        log "MPD ma aktywne wyjścia — gotowe do odtwarzania (nie włączam automatycznie)."
    else
        log "MPD ma wyłączone wyjścia — pomijam automatyczne odtwarzanie."
    fi
fi

echo -e "${BLUE}Krok 9: Test DAC${RESET}"

TEST_WAV="$MEDIA_DIR/test.wav"

log "Generuję test.wav (400 Hz, stereo, 0.5 s)."
sox -n -r 48000 -b 16 -c 2 "$TEST_WAV" synth 0.5 sine 400

mpc stop >/dev/null 2>&1
sudo systemctl stop mpd

aplay "$TEST_WAV" -D plughw:0,0
log "Test DAC zakończony."

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

echo -e "${BLUE}Krok 11: Pobieranie i aktualizacja projektu STREAMER${RESET}"

TMP_DIR=$(mktemp -d)
log "Pobieranie repozytorium: $REPO_GIT (branch: $REPO_BRANCH)"
CLONE_OK=0
if GIT_TERMINAL_PROMPT=0 git clone --depth=1 --branch "$REPO_BRANCH" \
    "$REPO_GIT" "$TMP_DIR" 2>&1 | tee -a "$LOGFILE"; then
    if [ -n "$(ls -A "$TMP_DIR")" ]; then
        CLONE_OK=1
    fi
fi

if [ "$CLONE_OK" -ne 1 ]; then
    log "Git clone nieudany, próbuję pobrać archiwum z GitHuba."
    if [[ "$REPO_GIT" =~ github.com/([^/]+)/([^/.]+)(\.git)?$ ]]; then
        OWNER="${BASH_REMATCH[1]}"
        REPO_NAME="${BASH_REMATCH[2]}"
        ARCHIVE_URL="https://github.com/${OWNER}/${REPO_NAME}/archive/refs/heads/${REPO_BRANCH}.tar.gz"
        ARCHIVE_FILE="$(mktemp)"
        if curl -fL --retry 3 --retry-delay 2 "$ARCHIVE_URL" -o "$ARCHIVE_FILE" 2>&1 | tee -a "$LOGFILE"; then
            tar -xzf "$ARCHIVE_FILE" -C "$TMP_DIR" --strip-components=1
            log "Archiwum pobrane i rozpakowane."
        else
            log "Błąd: nie udało się pobrać archiwum z GitHuba!"
            exit 1
        fi
    else
        log "Błąd: nie udało się pobrać repozytorium!"
        exit 1
    fi
fi

rsync -av \
    --exclude=installer \
    --exclude=logs \
    --exclude=.git \
    --exclude=.gitignore \
    "$TMP_DIR/" "$STREAMER_DIR/"

# === Utworzenie venv i instalacja deps dla użytkownika (umieszczone w $HOME/streamer) ===
# Określamy rzeczywistego użytkownika (jeśli instalator uruchomiony przez sudo)
if [ -n "${SUDO_USER:-}" ]; then
  REAL_USER="$SUDO_USER"
else
  REAL_USER="$(whoami)"
fi
USER_HOME=$(eval echo "~$REAL_USER")
STREAMER_DIR="$USER_HOME/streamer"
VENV_DIR="$STREAMER_DIR/venv"

echo "Instalacja venv i zależności dla użytkownika: $REAL_USER w $STREAMER_DIR"

# Upewnij się, że katalog projektu istnieje (repo powinien być już sklonowany/synchronizowany)
mkdir -p "$STREAMER_DIR"
chown -R "$REAL_USER":"$REAL_USER" "$STREAMER_DIR"

# Stwórz venv jako REAL_USER (jeżeli jeszcze nie istnieje)
if [ ! -d "$VENV_DIR" ]; then
  sudo -u "$REAL_USER" python3 -m venv "$VENV_DIR"
  sudo -u "$REAL_USER" "$VENV_DIR/bin/pip" install --upgrade pip
  # Zainstaluj wymagane pakiety w venv
  sudo -u "$REAL_USER" "$VENV_DIR/bin/pip" install adafruit-blinka adafruit-circuitpython-ssd1306 Pillow RPi.GPIO
fi

mkdir -p "$USER_HOME/.config/systemd/user"
chown -R "$REAL_USER":"$REAL_USER" "$USER_HOME/.config/systemd/user"

# Zakładamy, że w repo jest plik systemd/oled-menu.service (dostosuj ścieżkę jeśli inna)
if [ -f "$PWD/streamer/systemd/oled-menu.service" ]; then
  cp "$PWD/streamer/systemd/oled-menu.service" "$USER_HOME/.config/systemd/user/oled-menu.service"
  chown "$REAL_USER":"$REAL_USER" "$USER_HOME/.config/systemd/user/oled-menu.service"
else
  echo "Uwaga: nie znaleziono streamer/systemd/oled-menu.service w bieżącym katalogu. Upewnij się, że unit jest w repo."
fi

# Dodaj użytkownika do wymaganych grup (i2c, gpio, audio) — wywoływane jako sudo
sudo usermod -aG i2c,gpio,audio "$REAL_USER" || true

# Włącz lingering (jeśli chcesz, żeby user services uruchamiały się bez logowania)
sudo loginctl enable-linger "$REAL_USER" || true

# Przeładuj user systemd i uruchom unit jako REAL_USER
# Używamy runuser/su aby wykonać systemctl --user w kontekście użytkownika
sudo -u "$REAL_USER" bash -c 'systemctl --user daemon-reload || true'
sudo -u "$REAL_USER" bash -c 'systemctl --user enable --now oled-menu.service || true'

# Upewnij się o własności plików w streamer
chown -R "$REAL_USER":"$REAL_USER" "$STREAMER_DIR"

log "Repozytorium zsynchronizowane."

echo -e "${BLUE}Krok 12: Aktualizacja changelog${RESET}"

if [ -f "$CHANGELOG_SOURCE" ]; then
    cp "$CHANGELOG_SOURCE" "$CHANGELOG_DIR/latest.txt"
    log "Changelog zaktualizowany z repozytorium."
else
    log "Brak pliku change_log w repozytorium."
fi

echo -e "${BLUE}Krok 13: Instalacja usług systemd${RESET}"

REAL_USER="${SUDO_USER:-$USER}"
VENV_PYTHON="$STREAMER_DIR/venv/bin/python3"

# 1. Naprawa oled.service (Usługa systemowa)
if [ -f "$STREAMER_DIR/systemd/oled.service" ]; then
    sudo cp "$STREAMER_DIR/systemd/oled.service" /etc/systemd/system/oled.service
    
    # Podmiana User, WorkingDirectory i ExecStart na absolutne ścieżki
    sudo sed -i "s|^User=.*|User=$REAL_USER|" /etc/systemd/system/oled.service
    sudo sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$STREAMER_DIR|" /etc/systemd/system/oled.service
    sudo sed -i "s|^ExecStart=.*|ExecStart=$VENV_PYTHON $STREAMER_DIR/oled/oled_daemon.py|" /etc/systemd/system/oled.service
    
    sudo systemctl daemon-reload
    sudo systemctl enable oled.service
    sudo systemctl restart oled.service
    log "Usługa oled.service skonfigurowana pod użytkownika $REAL_USER"
fi

# 2. Naprawa input.service
if [ -f "$STREAMER_DIR/systemd/input.service" ]; then
    sudo cp "$STREAMER_DIR/systemd/input.service" /etc/systemd/system/input.service
    sudo sed -i "s|^User=.*|User=$REAL_USER|" /etc/systemd/system/input.service
    sudo sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$STREAMER_DIR|" /etc/systemd/system/input.service
    sudo sed -i "s|^ExecStart=.*|ExecStart=$VENV_PYTHON $STREAMER_DIR/input/input_daemon.py|" /etc/systemd/system/input.service
    
    sudo systemctl enable input.service
    sudo systemctl restart input.service
    log "Usługa input.service skonfigurowana."
fi

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

echo -e "${BLUE}Krok 15: Przywracanie usług${RESET}"
# Zatrzymaj spinner jeśli jeszcze działa
if [ -n "${SPINNER_PID:-}" ]; then
    touch "$SPINNER_FLAG"
    kill "$SPINNER_PID" >/dev/null 2>&1 || true
fi

# Przywróć OLED - restart, ale bez ponownego kopiowania/enabling, reset failed jeśli potrzeba
if [ -f "$STREAMER_DIR/systemd/oled.service" ]; then
    sudo systemctl daemon-reload
    sudo systemctl reset-failed oled.service >/dev/null 2>&1 || true
    if sudo systemctl restart oled.service >/dev/null 2>&1; then
        log "Usługa OLED uruchomiona po instalacji."
    else
        log "Uwaga: nie udało się uruchomić oled.service — sprawdź journalctl -xeu oled.service"
    fi
fi

# Przywróć INPUT
if [ -f "$STREAMER_DIR/systemd/input.service" ]; then
    if sudo systemctl restart input.service >/dev/null 2>&1; then
        log "Usługa INPUT uruchomiona po instalacji."
    else
        log "Uwaga: nie udało się uruchomić input.service"
    fi
fi

mpc stop >/dev/null 2>&1

echo -e "${GREEN}=============================================="
echo -e " INSTALACJA ZAKOŃCZONA SUKCESEM"
echo -e " Log: $LOGFILE"
echo -e "${GREEN}==============================================${RESET}"

log "=== Instalacja zakończona pomyślnie ==="
