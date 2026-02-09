#!/bin/bash
set -e

###############################################
#   Raspberry Pi Audio Streamer Installer
###############################################

# --- Logger ---
ENABLE_LOGGER=1   # 1 = logger aktywny, 0 = logger wyłączony
LOGFILE="/home/$USER/streamer_install.log"

log() {
    if [ "$ENABLE_LOGGER" -eq 1 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') | $1" | tee -a "$LOGFILE"
    else
        echo "$1"
    fi
}

log "=== Uruchomiono instalator ==="

###############################################
#   Wybór trybu
###############################################

echo "=============================================="
echo "      Raspberry Pi Audio Streamer Installer"
echo "=============================================="
echo "Wybierz tryb:"
echo "1) Instalacja (pełna konfiguracja)"
echo "2) Aktualizacja (git pull + restart usług)"
read -p "Wybór [1/2]: " MODE

log "Wybrany tryb: $MODE"

###############################################
#   Funkcje pomocnicze
###############################################

service_exists() {
    systemctl list-unit-files | grep -q "$1"
}

restart_service_if_exists() {
    if service_exists "$1"; then
        log "[OK] Restart: $1"
        sudo systemctl restart "$1" || log "[!] Błąd restartu: $1"
    else
        log "[-] Usługa $1 nie istnieje — pomijam."
    fi
}

detect_dac() {
    if aplay -l 2>/dev/null | grep -q "sndrpihifiberry"; then
        log "[OK] Wykryto DAC PCM5122."
        return 0
    else
        log "[!] BŁĄD: Nie wykryto DAC PCM5122!"
        log "    - Sprawdź połączenia I2S"
        log "    - Sprawdź overlay w /boot/config.txt"
        return 1
    fi
}

detect_oled() {
    if i2cdetect -y 1 | grep -q "3c"; then
        log "[OK] Wykryto OLED (0x3C)."
        return 0
    else
        log "[-] OLED nie wykryty — pomijam konfigurację ekranu."
        return 1
    fi
}

detect_bt() {
    if lsusb | grep -qi "Bluetooth"; then
        log "[OK] Wykryto adapter Bluetooth USB."
        return 0
    else
        log "[-] Brak adaptera Bluetooth — pomijam BlueALSA."
        return 1
    fi
}

detect_wifi() {
    if iwconfig 2>/dev/null | grep -q "wlan0"; then
        log "[OK] Wykryto Wi-Fi."
        return 0
    else
        log "[-] Brak Wi-Fi — radio internetowe może nie działać."
        return 1
    fi
}

###############################################
#   TRYB AKTUALIZACJI
###############################################

if [ "$MODE" = "2" ]; then
    log "=== TRYB AKTUALIZACJI ==="

    if [ ! -d "/home/$USER/streamer" ]; then
        log "[!] Błąd: katalog /home/$USER/streamer nie istnieje!"
        exit 1
    fi

    cd /home/$USER/streamer
    log "Pobieram zmiany z GitHub..."
    git pull

    log "Wykrywanie sprzętu..."
    detect_dac
    detect_oled
    detect_bt
    detect_wifi

    log "Restart usług..."
    restart_service_if_exists "mpd.service"
    restart_service_if_exists "bluealsa.service"
    restart_service_if_exists "camilladsp.service"
    restart_service_if_exists "oled.service"

    log "=== Aktualizacja zakończona ==="
    exit 0
fi

###############################################
#   TRYB INSTALACJI
###############################################

log "=== TRYB INSTALACJI ==="

read -p "Czy zaktualizować system? [y/N]: " UPD
if [[ "$UPD" =~ ^[Yy]$ ]]; then
    log "Aktualizacja systemu..."
    sudo apt update
    sudo apt upgrade -y
fi

log "Instalacja pakietów..."
bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/install_packages.sh)

log "Konfiguracja audio..."
bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_audio.sh)

log "Konfiguracja MPD..."
bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_mpd.sh)

log "Konfiguracja Bluetooth..."
bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_bt.sh)

log "Konfiguracja CamillaDSP..."
bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_camilladsp.sh)

log "Instalacja Python..."
bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/install_python.sh)

log "Pobieranie projektu..."
bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/clone_repo.sh)

log "Wykrywanie sprzętu..."
detect_dac
detect_oled
detect_bt
detect_wifi

log "Restart usług..."
restart_service_if_exists "mpd.service"
restart_service_if_exists "bluealsa.service"
restart_service_if_exists "camilladsp.service"
restart_service_if_exists "oled.service"

log "=============================================="
log " Instalacja zakończona — uruchom ponownie RPi."
log "=============================================="
