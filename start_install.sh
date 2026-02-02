#!/bin/bash

SOFT_VERSION="0.04d"

# Kolory
RED="\e[31m"
GREEN="\e[32m"
YELLOW="\e[33m"
BLUE="\e[34m"
RESET="\e[0m"

# Katalogi projektu (dynamiczne)
STREAMER_DIR="$HOME/streamer"
LOG_DIR="$STREAMER_DIR/logs"
CONFIG_DIR="$STREAMER_DIR/config"
INSTALLER_DIR="$STREAMER_DIR/installer"
LOGFILE="$LOG_DIR/install.log"
GPIO_FILE="$CONFIG_DIR/gpio.json"
CHANGELOG="$STREAMER_DIR/change_log"

# Wykrycie właściwego config.txt
if [ -f /boot/firmware/config.txt ]; then
CONFIG_TXT="/boot/firmware/config.txt"
else
CONFIG_TXT="/boot/config.txt"
fi

# Funkcja logowania
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
echo -e "${YELLOW}Dodano: ${GREEN}$line${RESET}"
log "Dodano do $(basename "$file"): $line"
return 0
fi
return 1
}

echo -e "${BLUE}=============================================="
echo -e " STREAMER AUDIO – Instalator v$SOFT_VERSION"
echo -e "==============================================${RESET}"
echo ""
pause_step

# -----------------------------------------------
# Przygotowanie środowiska
# -----------------------------------------------
echo -e "${BLUE}Przygotowanie środowiska...${RESET}"

mkdir -p "$LOG_DIR" "$CONFIG_DIR" "$INSTALLER_DIR"
touch "$LOGFILE"

log "Struktura katalogów gotowa."

# -----------------------------------------------
# Autodetekcja Raspberry Pi
# -----------------------------------------------
echo -e "${BLUE}Wykrywanie Raspberry Pi...${RESET}"

PI_MODEL=$(tr -d '\0' </proc/device-tree/model)
echo -e "${GREEN}Wykryto: ${YELLOW}$PI_MODEL${RESET}"
log "Model: $PI_MODEL"

# Słabe modele: Zero / Zero W / Zero 2 W / Pi 1
if [[ "$PI_MODEL" == *"Zero"* ]] || [[ "$PI_MODEL" == *"Model A"* ]] || [[ "$PI_MODEL" == *"Model B Rev 1."* ]]; then
echo -e "${YELLOW}Wykryto słabszy model Raspberry Pi.${RESET}"
log "Wykryto słabszy model Raspberry Pi."
read -p "Instalować GStreamer? (t/n): " GST_CHOICE
[[ "$GST_CHOICE" = "t" ]] && INSTALL_GST=1 || INSTALL_GST=0
else
echo -e "${GREEN}Wydajny model Raspberry Pi.${RESET}"
log "Wydajny model Raspberry Pi."
INSTALL_GST=1
fi

pause_step

# -----------------------------------------------
# 1. Aktualizacja systemu
# -----------------------------------------------
echo -e "${BLUE}Krok 1: Aktualizacja systemu${RESET}"
(sudo apt update && sudo apt upgrade -y) &
spinner $!
log "System zaktualizowany."
pause_step

# -----------------------------------------------
# 2. Instalacja pakietów
# -----------------------------------------------
echo -e "${BLUE}Krok 2: Instalacja pakietów${RESET}"
(sudo apt install -y git python3 python3-pip python3-venv \
mpd mpc alsa-utils i2c-tools jq curl wget unzip sox) &
spinner $!
log "Pakiety zainstalowane."
pause_step

# -----------------------------------------------
# 3. Instalacja bibliotek Python
# -----------------------------------------------
echo -e "${BLUE}Krok 3: Instalacja bibliotek Python${RESET}"
(pip3 install --break-system-packages \
python-mpd2 RPi.GPIO pillow adafruit-circuitpython-ssd1306 requests) &
spinner $!
log "Biblioteki Python zainstalowane (z użyciem --break-system-packages)."
pause_step

# -----------------------------------------------
# 4. Instalacja GStreamera
# -----------------------------------------------
if [ "$INSTALL_GST" = "1" ]; then
echo -e "${BLUE}Instalacja GStreamera${RESET}"
(sudo apt install -y gstreamer1.0-tools gstreamer1.0-plugins-base \
gstreamer1.0-plugins-good gstreamer1.0-plugins-bad) &
spinner $!
log "GStreamer zainstalowany."
else
log "GStreamer pominięty."
fi
pause_step

# -----------------------------------------------
# 5. Tworzenie gpio.json
# -----------------------------------------------
echo -e "${BLUE}Krok 5: Tworzenie gpio.json${RESET}"

cat <<EOF > "$GPIO_FILE"
{
"version": "$SOFT_VERSION",

"i2c": {
"enabled": true,
"sda": 2,
"scl": 3
},

"i2s": {
"enabled": true,
"dac_overlay": "hifiberry-dac",
"bck": 18,
"lrck": 19,
"din": 21
},

"oled": {
"type": "ssd1306/ssd1309",
"address": "0x3C",
"width": 128,
"height": 64
}
}
EOF

log "gpio.json utworzony."
pause_step

# -----------------------------------------------
# 6. Synchronizacja config.txt
# -----------------------------------------------
echo -e "${BLUE}Krok 6: Synchronizacja config.txt${RESET}"

CHANGES=0

if ensure_line "dtoverlay=hifiberry-dac" "$CONFIG_TXT"; then
CHANGES=1
fi
if ensure_line "dtparam=i2c_arm=on" "$CONFIG_TXT"; then
CHANGES=1
fi
if ensure_line "dtparam=i2s=on" "$CONFIG_TXT"; then
CHANGES=1
fi

# Wyłączenie wbudowanego audio, jeśli włączone
if grep -q "^dtparam=audio=on" "$CONFIG_TXT"; then
sudo sed -i 's/^dtparam=audio=on/#dtparam=audio=on/' "$CONFIG_TXT"
echo -e "${YELLOW}Wyłączono wbudowane audio (dtparam=audio=on).${RESET}"
log "Wyłączono wbudowane audio (dtparam=audio=on)."
CHANGES=1
fi

if [ $CHANGES -eq 0 ]; then
echo -e "${GREEN}config.txt aktualny (${CONFIG_TXT}).${RESET}"
log "$(basename "$CONFIG_TXT") aktualny."
else
echo -e "${YELLOW}config.txt zaktualizowany (${CONFIG_TXT}).${RESET}"
log "$(basename "$CONFIG_TXT") zaktualizowany."
fi

pause_step

# -----------------------------------------------
# 7. Restart MPD
# -----------------------------------------------
echo -e "${BLUE}Krok 7: Restart MPD${RESET}"
sudo systemctl restart mpd
log "MPD uruchomiony."
pause_step

# -----------------------------------------------
# 8. Autodetekcja DAC
# -----------------------------------------------
echo -e "${BLUE}Krok 8: Autodetekcja DAC${RESET}"
if aplay -l | grep -qi "sndrpihifiberry"; then
echo -e "${GREEN}Wykryto DAC: PCM5102A (sndrpihifiberry).${RESET}"
log "Wykryto DAC: PCM5102A"
else
echo -e "${RED}Nie wykryto DAC!${RESET}"
log "Nie wykryto DAC!"
fi
pause_step

# -----------------------------------------------
# 9. Autodetekcja OLED
# -----------------------------------------------
echo -e "${BLUE}Krok 9: Autodetekcja OLED${RESET}"
if sudo i2cdetect -y 1 | grep -q "3c"; then
echo -e "${GREEN}Wykryto OLED SSD1306/SSD1309 (0x3C).${RESET}"
log "OLED wykryty."
else
echo -e "${RED}OLED nie wykryty!${RESET}"
log "OLED nie wykryty."
fi
pause_step

# -----------------------------------------------
# 10. Dodanie stacji radiowej
# -----------------------------------------------
echo -e "${BLUE}Krok 10: Dodanie stacji radiowej${RESET}"

RADIO_URL="http://stream.rcs.revma.com/ye5kghkgcm0uv"
RADIO_NAME="Radio 357"

# Sprawdź, czy stacja już jest w playliście
if mpc playlist | grep -q "$RADIO_URL"; then
echo -e "${YELLOW}Stacja radiowa już istnieje w playliście – pomijam dodawanie.${RESET}"
log "Stacja radiowa już istnieje – pominięto dodanie."
RADIO_NEW=0
else
mpc clear
mpc add "$RADIO_URL"
mpc save radio
echo -e "${GREEN}Dodano stację: $RADIO_NAME.${RESET}"
log "Dodano Radio 357."
RADIO_NEW=1
fi

# Jeśli to pierwsza instalacja (nowo dodana stacja) – uruchom radio na 30%
if [ "$RADIO_NEW" -eq 1 ]; then
mpc volume 30
mpc play
log "Rozpoczęto odtwarzanie radia na 30%."
else
log "Odtwarzanie radia nie zostało wznowione (ponowna instalacja)."
fi

pause_step

# -----------------------------------------------
# 11. Test odtwarzania DAC (test.wav 800 Hz / 0.5 s)
# -----------------------------------------------
echo -e "${BLUE}Krok 11: Test odtwarzania DAC${RESET}"

MEDIA_DIR="$STREAMER_DIR/media"
TEST_WAV="$MEDIA_DIR/test.wav"

# Katalog media
if [ ! -d "$MEDIA_DIR" ]; then
mkdir -p "$MEDIA_DIR"
log "Utworzono katalog media: $MEDIA_DIR"
fi

# Generowanie test.wav, jeśli brak
if [ ! -f "$TEST_WAV" ]; then
log "Generuję test.wav (800 Hz, 0.5 s)."
sox -n -r 48000 -b 16 -c 1 "$TEST_WAV" synth 0.5 sine 800
fi

# Zatrzymanie MPD, żeby nie blokował ALSA
mpc stop >/dev/null 2>&1
sudo systemctl stop mpd

# Test DAC
echo -e "${YELLOW}Odtwarzam test.wav na DAC (hw:0,0)...${RESET}"
aplay "$TEST_WAV" -D hw:0,0
log "Test odtwarzania DAC zakończony."

pause_step

# -----------------------------------------------
# 12. change_log
# -----------------------------------------------
echo -e "${BLUE}Krok 12: Aktualizacja change_log${RESET}"

TEMP_CHANGELOG=$(mktemp)

cat <<EOF > "$TEMP_CHANGELOG"
0.04d – Poprawki instalatora, config.txt i testu DAC
- Wykrywanie /boot/firmware/config.txt vs /boot/config.txt.
- Włączenie I2C i I2S bez raspi-config.
- Wyłączenie wbudowanego audio (dtparam=audio=on).
- Dodanie generowania test.wav (800 Hz, 0.5 s) i testu DAC.
- Logika radia: 30% głośności, wyłączone po instalacji, brak auto-play przy ponownej instalacji.

0.04a–0.04c – Wersje robocze instalatora
- Iteracyjne poprawki logiki instalacji i detekcji.
- Uspójnienie struktury katalogów i logowania.

0.03a – Wykrywanie SSD1306/SSD1309 + poprawki instalatora
- Dodano wykrywanie OLED SSD1306/SSD1309.
- Spinner we wszystkich instalacjach.
- gpio.json jako źródło parametrów.
- Synchronizacja config.txt tylko przy zmianach.

0.02a – Instalator startowy
- Instalacja MPD, MPC, Python, bibliotek.
- Autodetekcja Raspberry Pi.
- Autodetekcja DAC i OLED.
- Tworzenie struktury katalogów.
- Dodanie polskiej stacji radiowej.
- Test odtwarzania.

0.01a – Koncept streamera
- Założenia: OLED, DAC I2S, enkodery, przyciski.
- Filozofia: modularność, dokumentacja, automatyzacja.
- Plan: daemon MPD + OLED.
- Wersja koncepcyjna, nigdy nie wydana.

EOF

if [ -f "$CHANGELOG" ]; then
cat "$CHANGELOG" >> "$TEMP_CHANGELOG"
fi

mv "$TEMP_CHANGELOG" "$CHANGELOG"
log "change_log zaktualizowany."
pause_step

# -----------------------------------------------
# 13. Przeniesienie instalatora
# -----------------------------------------------
echo -e "${BLUE}Porządkowanie instalatora...${RESET}"

SCRIPT_NAME="$(basename "$0")"
CURRENT_PATH="$(realpath "$0")"
TARGET_PATH="$INSTALLER_DIR/$SCRIPT_NAME"

if [ "$CURRENT_PATH" != "$TARGET_PATH" ]; then
cp "$CURRENT_PATH" "$TARGET_PATH"
rm "$CURRENT_PATH"
log "Instalator przeniesiony do: $TARGET_PATH"
else
log "Instalator już w katalogu docelowym."
fi

pause_step

# -----------------------------------------------
# 14. Zakończenie – radio wyłączone
# -----------------------------------------------
mpc stop >/dev/null 2>&1

echo ""
echo -e "${GREEN}=============================================="
echo -e " INSTALACJA ZAKOŃCZONA SUKCESEM"
echo -e " Log: $LOGFILE"
echo -e "==============================================${RESET}"
echo ""

log "=== Instalacja zakończona pomyślnie ==="
