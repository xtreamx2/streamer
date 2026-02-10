#!/usr/bin/env bash

# ============================================
#  streamer - installer / updater (branch Second)
#  tryb 1: pełna instalacja
#  tryb 2: aktualizacja (update only)
# ============================================

set -euo pipefail

# ---------- helpers ----------

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') | $*"
}

run_safe() {
  if ! bash -c "$*"; then
    log "(!) Command failed (kontynuuję): $*"
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
    sudo systemctl restart "$svc" || log "(!) Nie udało się zrestartować $svc"
  else
    log "[..] Włączam i uruchamiam $svc"
    sudo systemctl enable --now "$svc" || log "(!) Nie udało się włączyć/uruchomić $svc"
  fi
}

ensure_git_clone() {
  local repo_url="$1"
  local branch="$2"
  local dest="$3"

  if [ -d "$dest/.git" ]; then
    log "Sprawdzam repozytorium w $dest..."
    if ! (cd "$dest" && git fsck --full >/dev/null 2>&1); then
      log "(!) Repozytorium uszkodzone. Usuwam i klonuję ponownie."
      rm -rf "$dest"
    else
      log "[OK] Repozytorium wygląda dobrze. Aktualizuję..."
      if ! (cd "$dest" && git fetch --all --prune && git reset --hard "origin/$branch"); then
        log "(!) Aktualizacja nie powiodła się. Usuwam i klonuję ponownie."
        rm -rf "$dest"
      fi
    fi
  fi

  if [ ! -d "$dest" ]; then
    log "Klonuję repozytorium $repo_url (branch: $branch) do $dest..."
    git clone --depth 1 --branch "$branch" "$repo_url" "$dest"
  fi
}

install_python_deps() {
  log "[PY] Instaluję zależności Python..."

  sudo apt update
  sudo apt install -y python3-pip python3-venv build-essential libjpeg-dev zlib1g-dev

  sudo -H python3 -m pip install --upgrade pip setuptools wheel

  sudo -H python3 -m pip install --break-system-packages \
    RPi.GPIO \
    smbus2 \
    pillow \
    python-mpd2 \
    luma.oled

  log "[PY] Zależności Python gotowe."
}

install_oled_service() {
  local user_name="$1"
  local repo_dir="$2"

  local oled_script="$repo_dir/oled/oled.py"

  if [ ! -f "$oled_script" ]; then
    log "[-] Brak skryptu OLED ($oled_script) — pomijam instalację usługi OLED."
    return 0
  fi

  log "[OLED] Tworzę usługę systemd..."

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

  log "[OLED] Plik usługi utworzony."
}

run_config_scripts() {
  log "Konfiguracja audio (I2S)..."
  run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_audio.sh)"

  log "Konfiguracja I2C..."
  run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_i2c.sh)"

  log "Konfiguracja OLED..."
  run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_oled.sh)"

  log "Konfiguracja MPD..."
  run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_mpd.sh)"

  log "Konfiguracja Bluetooth..."
  run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_bt.sh)"

  log "Konfiguracja CamillaDSP..."
  run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/configure_camilladsp.sh)"
}

restart_all_services() {
  log "Przeładowanie systemd i zbiorczy restart usług..."
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

# ---------- main ----------

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
  log "=== TRYB: INSTALACJA ==="

  read -r -p "Czy zaktualizować system (apt update/upgrade)? [y/N]: " UPD
  if [[ "$UPD" =~ ^[Yy]$ ]]; then
    log "Aktualizacja systemu..."
    run_safe "sudo apt update && sudo apt upgrade -y"
  fi

  log "Instalacja pakietów systemowych..."
  run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/install_packages.sh)"

  install_python_deps

  run_config_scripts

  log "Pobieranie / aktualizacja repozytorium..."
  ensure_git_clone "$REPO_URL" "$BRANCH" "$DEST_DIR"

  install_oled_service "$USER_NAME" "$DEST_DIR"

  restart_all_services

  log "=============================================="
  log " INSTALACJA ZAKOŃCZONA. Jeśli zmieniano dtoverlay/dtparam, zrób reboot."
  log "=============================================="
  exit 0

elif [[ "$MODE" == "2" ]]; then
  log "=== TRYB: AKTUALIZACJA ==="

  log "Pobieranie / aktualizacja repozytorium..."
  ensure_git_clone "$REPO_URL" "$BRANCH" "$DEST_DIR"

  install_oled_service "$USER_NAME" "$DEST_DIR"

  restart_all_services

  log "=============================================="
  log " AKTUALIZACJA ZAKOŃCZONA."
  log "=============================================="
  exit 0

else
  log "Nieprawidłowy wybór trybu: $MODE"
  exit 1
fi
