#!/usr/bin/env bash

# streamer installer / updater (branch Second)

set -euo pipefail

# ---------- konfiguracja logów ----------

DEBUG_LOG=1   # 1 = zapisuj debug do install.log, 0 = tylko streamer_install.log

LOG_FILE="$HOME/streamer_install.log"
DEBUG_FILE="$HOME/install.log"

touch "$LOG_FILE"
if [[ "$DEBUG_LOG" == "1" ]]; then
    touch "$DEBUG_FILE"
fi

# ---------- kolory ----------

GREEN="\e[32m"
RED="\e[31m"
YELLOW="\e[33m"
BLUE="\e[34m"
RESET="\e[0m"

log() {
    local msg="$1"
    local type="${2:-INFO}"

    case "$type" in
        OK)   prefix="${GREEN}[OK]${RESET}" ;;
        ERR)  prefix="${RED}[ERROR]${RESET}" ;;
        WARN) prefix="${YELLOW}[-]${RESET}" ;;
        *)    prefix="${BLUE}[..]${RESET}" ;;
    esac

    echo -e "$prefix $msg"
    echo "$(date '+%Y-%m-%d %H:%M:%S') | $prefix $msg" >> "$LOG_FILE"

    if [[ "$DEBUG_LOG" == "1" ]]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') | $msg" >> "$DEBUG_FILE"
    fi
}

run_safe() {
    local cmd="$*"
    log "$cmd" "INFO"
    if ! bash -c "$cmd"; then
        log "Błąd: $cmd" "ERR"
        return 1
    fi
    return 0
}

restart_service_if_exists() {
    local svc="$1"

    if ! systemctl list-unit-files --type=service | awk '{print $1}' | grep -qx "$svc"; then
        log "[$svc] brak jednostki, pomijam." "WARN"
        return 0
    fi

    if systemctl is-active --quiet "$svc"; then
        log "[$svc] restartuję..." "INFO"
        if ! sudo systemctl restart "$svc"; then
            log "[$svc] nie udało się zrestartować" "ERR"
        else
            log "[$svc] zrestartowano" "OK"
        fi
    else
        log "[$svc] włączam i uruchamiam..." "INFO"
        if ! sudo systemctl enable --now "$svc"; then
            log "[$svc] nie udało się włączyć/uruchomić" "ERR"
        else
            log "[$svc] włączona i uruchomiona" "OK"
        fi
    fi
}

ensure_git_clone() {
    local repo_url="$1"
    local branch="$2"
    local dest="$3"

    if [ -d "$dest/.git" ]; then
        log "[clone_repo] sprawdzam repozytorium w $dest..." "INFO"
        if ! (cd "$dest" && git fsck --full >/dev/null 2>&1); then
            log "[clone_repo] repozytorium uszkodzone, usuwam i klonuję ponownie" "WARN"
            rm -rf "$dest"
        else
            log "[clone_repo] repozytorium OK, aktualizuję..." "INFO"
            if ! (cd "$dest" && git fetch --all --prune && git reset --hard "origin/$branch"); then
                log "[clone_repo] aktualizacja nie powiodła się, usuwam i klonuję ponownie" "WARN"
                rm -rf "$dest"
            fi
        fi
    fi

    if [ ! -d "$dest" ]; then
        log "[clone_repo] klonuję $repo_url (branch: $branch) do $dest..." "INFO"
        git clone --depth 1 --branch "$branch" "$repo_url" "$dest"
        log "[clone_repo] repozytorium pobrane" "OK"
    else
        log "[clone_repo] repozytorium istnieje i zostało zaktualizowane" "OK"
    fi
}

install_python_deps() {
    log "[install_python] instaluję biblioteki Python..." "INFO"

    sudo apt update
    sudo apt install -y python3-pip python3-venv build-essential libjpeg-dev zlib1g-dev

    sudo -H python3 -m pip install --break-system-packages --upgrade pip setuptools wheel

    sudo -H python3 -m pip install --break-system-packages \
        RPi.GPIO \
        smbus2 \
        pillow \
        python-mpd2 \
        luma.oled

    log "[install_python] biblioteki Python zainstalowane" "OK"
}

install_oled_service() {
    local user_name="$1"
    local repo_dir="$2"

    local oled_script="$repo_dir/oled/oled.py"

    if [ ! -f "$oled_script" ]; then
        log "[oled] brak skryptu ($oled_script) — pomijam usługę" "WARN"
        return 0
    fi

    log "[oled] tworzę usługę systemd..." "INFO"

    sudo tee /etc/systemd/system/oled.service >/dev/null <<EOF
[Unit]
Description=OLED Display Service
After=network.target syslog.target dev-i2c-1.device

[Service]
Type=simple
ExecStart=/usr/bin/python3 $oled_script
Restart=always
RestartSec=2
User=$user_name

[Install]
WantedBy=multi-user.target
EOF

    log "[oled] plik usługi utworzony" "OK"
}
install_web_service() {
    local user_name="$1"

    log "[web] tworzę usługę systemd..." "INFO"

    sudo tee /etc/systemd/system/streamer-web.service >/dev/null <<EOF
[Unit]
Description=Streamer Web Interface
After=network.target

[Service]
User=$user_name
WorkingDirectory=/home/$user_name/streamer/web
ExecStart=/usr/bin/python3 /home/$user_name/streamer/web/app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    log "[web] plik usługi utworzony" "OK"
}

run_config_scripts() {
    log "[configure_audio] konfiguracja audio (I2S)..." "INFO"
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_audio.sh)"

    log "[configure_i2c] konfiguracja I2C..." "INFO"
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_i2c.sh)"

    log "[configure_oled] konfiguracja OLED..." "INFO"
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_oled.sh)"

    log "[configure_mpd] konfiguracja MPD..." "INFO"
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_mpd.sh)"

    log "[configure_bt] konfiguracja Bluetooth..." "INFO"
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_bt.sh)"

    log "[configure_camilladsp] konfiguracja CamillaDSP..." "INFO"
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_camilladsp.sh)"
}

restart_all_services() {
    log "[services] przeładowanie systemd..." "INFO"
    sudo systemctl daemon-reload

    local services=(
        "mpd.service"
        "bluealsa.service"
        "camilladsp.service"
        "oled.service"
        "streamer-web.service"
    )

    for s in "${services[@]}"; do
        restart_service_if_exists "$s"
    done
}

# ---------- main ----------

log "=== streamer install/update (branch Second) ===" "INFO"

USER_NAME="$(whoami)"
HOME_DIR="$(eval echo ~"$USER_NAME")"
REPO_URL="https://github.com/xtreamx2/streamer"
BRANCH="Second"
DEST_DIR="$HOME_DIR/streamer"

echo "Wybierz tryb:"
echo "1) Instalacja (fresh)"
echo "2) Aktualizacja (update only)"
read -r -p "Wybierz [1/2]: " MODE

if [[ "$MODE" == "1" ]]; then
    log "[mode] TRYB: INSTALACJA" "INFO"

    read -r -p "Czy zaktualizować system (apt update/upgrade)? [y/N]: " UPD
    if [[ "$UPD" =~ ^[Yy]$ ]]; then
        log "[system] aktualizacja systemu..." "INFO"
        run_safe "sudo apt update && sudo apt upgrade -y"
    fi

    log "[install_packages] instalacja pakietów systemowych..." "INFO"
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/install_packages.sh)"

    install_python_deps

    run_config_scripts

    log "[clone_repo] pobieranie / aktualizacja repozytorium..." "INFO"
    ensure_git_clone "$REPO_URL" "$BRANCH" "$DEST_DIR"

    install_oled_service "$USER_NAME" "$DEST_DIR"
    install_web_service "$USER_NAME"

    restart_all_services

    log "INSTALACJA ZAKOŃCZONA. Jeśli zmieniano dtoverlay/dtparam, wykonaj reboot." "OK"
    log "Logi: $LOG_FILE (normal), $DEBUG_FILE (debug, DEBUG_LOG=$DEBUG_LOG)" "INFO"
    exit 0

elif [[ "$MODE" == "2" ]]; then
    log "[mode] TRYB: AKTUALIZACJA" "INFO"

    log "[clone_repo] pobieranie / aktualizacja repozytorium..." "INFO"
    ensure_git_clone "$REPO_URL" "$BRANCH" "$DEST_DIR"

    install_oled_service "$USER_NAME" "$DEST_DIR"
    install_web_service "$USER_NAME"

    restart_all_services

    log "AKTUALIZACJA ZAKOŃCZONA." "OK"
    log "Logi: $LOG_FILE (normal), $DEBUG_FILE (debug, DEBUG_LOG=$DEBUG_LOG)" "INFO"
    exit 0

else
    log "[mode] nieprawidłowy wybór trybu: $MODE" "ERR"
    exit 1
fi
