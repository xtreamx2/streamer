#!/usr/bin/env bash

# streamer installer / updater (branch Second)

set -euo pipefail

LOG_FILE="/var/log/streamer_install.log"

log() {
    local msg="$*"
    echo "$(date '+%Y-%m-%d %H:%M:%S') | $msg"
    echo "$(date '+%Y-%m-%d %H:%M:%S') | $msg" >> "$LOG_FILE"
}

run_safe() {
    local cmd="$*"
    log "[..] $cmd"
    if ! bash -c "$cmd"; then
        log "[!] Błąd: $cmd"
        return 1
    fi
    return 0
}

restart_service_if_exists() {
    local svc="$1"

    if ! systemctl list-unit-files --type=service | awk '{print $1}' | grep -qx "$svc"; then
        log "[-] $svc: brak jednostki, pomijam."
        return 0
    fi

    if systemctl is-active --quiet "$svc"; then
        log "[..] Restartuję $svc"
        if ! sudo systemctl restart "$svc"; then
            log "[!] Nie udało się zrestartować $svc"
        else
            log "[OK] Zrestartowano $svc"
        fi
    else
        log "[..] Włączam i uruchamiam $svc"
        if ! sudo systemctl enable --now "$svc"; then
            log "[!] Nie udało się włączyć/uruchomić $svc"
        else
            log "[OK] $svc włączona i uruchomiona"
        fi
    fi
}

ensure_git_clone() {
    local repo_url="$1"
    local branch="$2"
    local dest="$3"

    if [ -d "$dest/.git" ]; then
        log "[clone_repo] Sprawdzam repozytorium w $dest..."
        if ! (cd "$dest" && git fsck --full >/dev/null 2>&1); then
            log "[clone_repo] (!) Repozytorium uszkodzone. Usuwam i klonuję ponownie."
            rm -rf "$dest"
        else
            log "[clone_repo] Repozytorium OK. Aktualizuję..."
            if ! (cd "$dest" && git fetch --all --prune && git reset --hard "origin/$branch"); then
                log "[clone_repo] (!) Aktualizacja nie powiodła się. Usuwam i klonuję ponownie."
                rm -rf "$dest"
            fi
        fi
    fi

    if [ ! -d "$dest" ]; then
        log "[clone_repo] Klonuję $repo_url (branch: $branch) do $dest..."
        git clone --depth 1 --branch "$branch" "$repo_url" "$dest"
        log "[clone_repo] [OK] Repozytorium pobrane."
    else
        log "[clone_repo] [OK] Repozytorium już istnieje i zostało zaktualizowane."
    fi
}

install_python_deps() {
    log "[install_python] Instaluję biblioteki Python..."

    sudo apt update
    sudo apt install -y python3-pip python3-venv build-essential libjpeg-dev zlib1g-dev

    sudo -H python3 -m pip install --break-system-packages --upgrade pip setuptools wheel

    sudo -H python3 -m pip install --break-system-packages \
        RPi.GPIO \
        smbus2 \
        pillow \
        python-mpd2 \
        luma.oled

    log "[install_python] [OK] Biblioteki Python zainstalowane."
}

install_oled_service() {
    local user_name="$1"
    local repo_dir="$2"

    local oled_script="$repo_dir/oled/oled.py"

    if [ ! -f "$oled_script" ]; then
        log "[oled] [-] Brak skryptu OLED ($oled_script) — pomijam instalację usługi."
        return 0
    fi

    log "[oled] Tworzę usługę systemd..."

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

    log "[oled] [OK] Plik usługi OLED utworzony."
}

run_config_scripts() {
    log "[configure_audio] Konfiguracja audio (I2S)..."
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_audio.sh)"

    log "[configure_i2c] Konfiguracja I2C..."
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_i2c.sh)"

    log "[configure_oled] Konfiguracja OLED..."
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_oled.sh)"

    log "[configure_mpd] Konfiguracja MPD..."
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_mpd.sh)"

    log "[configure_bt] Konfiguracja Bluetooth..."
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_bt.sh)"

    log "[configure_camilladsp] Konfiguracja CamillaDSP..."
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_camilladsp.sh)"
}

restart_all_services() {
    log "[services] Przeładowanie systemd..."
    sudo systemctl daemon-reload

    local services=(
        "mpd.service"
        "bluealsa.service"
        "camilladsp.service"
        "oled.service"
    )

    for s in "${services[@]}"; do
        restart_service_if_exists "$s"
    done
}

# ---------------- main ----------------

log "=== streamer install/update (branch Second) ==="

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
    log "[mode] TRYB: INSTALACJA"

    read -r -p "Czy zaktualizować system (apt update/upgrade)? [y/N]: " UPD
    if [[ "$UPD" =~ ^[Yy]$ ]]; then
        log "[system] Aktualizacja systemu..."
        run_safe "sudo apt update && sudo apt upgrade -y"
    fi

    log "[install_packages] Instalacja pakietów systemowych..."
    run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/install_packages.sh)"

    install_python_deps

    run_config_scripts

    log "[clone_repo] Pobieranie / aktualizacja repozytorium..."
    ensure_git_clone "$REPO_URL" "$BRANCH" "$DEST_DIR"

    install_oled_service "$USER_NAME" "$DEST_DIR"

    restart_all_services

    log "=============================================="
    log " [OK] INSTALACJA ZAKOŃCZONA."
    log " Jeśli zmieniano dtoverlay/dtparam, wykonaj reboot."
    log " Log: $LOG_FILE"
    log "=============================================="
    exit 0

elif [[ "$MODE" == "2" ]]; then
    log "[mode] TRYB: AKTUALIZACJA"

    log "[clone_repo] Pobieranie / aktualizacja repozytorium..."
    ensure_git_clone "$REPO_URL" "$BRANCH" "$DEST_DIR"

    install_oled_service "$USER_NAME" "$DEST_DIR"

    restart_all_services

    log "=============================================="
    log " [OK] AKTUALIZACJA ZAKOŃCZONA."
    log " Log: $LOG_FILE"
    log "=============================================="
    exit 0

else
    log "[mode] Nieprawidłowy wybór trybu: $MODE"
    exit 1
fi
