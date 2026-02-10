#!/usr/bin/env bash
# Robust installer for streamer (branch: Second)
# - single daemon-reload and grouped restarts
# - tolerant to missing hardware
# - auto-fix corrupt git by recloning
# - create oled.service only if oled.py exists
# - safe logging and non-fatal checks

# -----------------------
# Helpers
# -----------------------
log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') | $*"
}

# Run a command but don't exit script on failure; log result
run_safe() {
  if ! bash -c "$*"; then
    log "(!) Command failed: $*"
    return 1
  fi
  return 0
}

# Restart or enable service only if unit file exists
restart_service_if_exists() {
  local svc="$1"
  if ! systemctl list-unit-files --type=service | awk '{print $1}' | grep -qx "$svc"; then
    log "[-] $svc: brak jednostki, pomijam."
    return 0
  fi

  # If active -> restart, else enable+start
  if systemctl is-active --quiet "$svc"; then
    log "[..] Restartuję $svc"
    sudo systemctl restart "$svc" || log "(!) Nie udało się zrestartować $svc"
  else
    log "[..] Włączam i uruchamiam $svc"
    sudo systemctl enable --now "$svc" || log "(!) Nie udało się włączyć/uruchomić $svc"
  fi
}

# Detect functions should never abort installation
detect_safe() {
  local name="$1"; shift
  if ! "$@"; then
    log "[-] Detekcja $name: brak lub błąd — pomijam."
    return 1
  else
    log "[OK] Detekcja $name: OK."
    return 0
  fi
}

# Ensure git clone is healthy; if corrupt -> remove and reclone
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
    if ! git clone --depth 1 --branch "$branch" "$repo_url" "$dest"; then
      log "(!) Klonowanie nie powiodło się."
      return 1
    fi
  fi
  return 0
}

# -----------------------
# Start instalacji
# -----------------------
log "=== Uruchomiono instalator ==="

# Użytkownik wykonujący instalację (używamy literalnej nazwy w plikach systemd)
USER_NAME="$(whoami)"
HOME_DIR="$(eval echo ~"$USER_NAME")"
REPO_URL="https://github.com/xtreamx2/streamer"
BRANCH="Second"
DEST_DIR="$HOME_DIR/streamer"

# Opcjonalna aktualizacja systemu
read -p "Czy zaktualizować system? [y/N]: " UPD
if [[ "$UPD" =~ ^[Yy]$ ]]; then
  log "Aktualizacja systemu..."
  sudo apt update && sudo apt upgrade -y || log "(!) Aktualizacja systemu nie powiodła się."
fi

# Instalacja pakietów (podskrypt)
log "Instalacja pakietów..."
run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/install_packages.sh)"

# Konfiguracje (uruchamiamy podskrypty, ale nie pozwalamy im restartować globalnie)
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

log "Instalacja Python..."
run_safe "bash <(curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/scripts/install_python.sh)"

# Pobierz/aktualizuj repo (bez przerywania instalacji)
log "Pobieranie projektu..."
if ! ensure_git_clone "$REPO_URL" "$BRANCH" "$DEST_DIR"; then
  log "(!) Nie udało się pobrać repozytorium. Kontynuuję, ale niektóre funkcje mogą być niedostępne."
fi

# Wykrywanie sprzętu (detekcje nie przerywają instalacji)
log "Wykrywanie sprzętu..."
detect_safe "DAC" bash -c 'lsmod | grep -qi snd_soc || true'
detect_safe "OLED" bash -c 'i2cdetect -y 1 >/dev/null 2>&1 || true'
detect_safe "Bluetooth" bash -c 'lsusb | grep -qi Bluetooth || true'
detect_safe "WiFi" bash -c 'ip link show wlan0 >/dev/null 2>&1 || true'

# -----------------------
# Instalacja usługi OLED (tylko jeśli skrypt istnieje w repo)
# -----------------------
OLED_SCRIPT="$DEST_DIR/oled/oled.py"
if [ -f "$OLED_SCRIPT" ]; then
  log "Instalacja usługi OLED..."
  sudo tee /etc/systemd/system/oled.service >/dev/null <<EOF
[Unit]
Description=OLED Display Service
After=network.target syslog.target dev-i2c-1.device

[Service]
Type=simple
ExecStart=/usr/bin/python3 $OLED_SCRIPT
Restart=always
User=$USER_NAME

[Install]
WantedBy=multi-user.target
EOF
  log "[OK] Plik usługi OLED utworzony."
else
  log "[-] Brak skryptu OLED ($OLED_SCRIPT) — pomijam instalację usługi OLED."
fi

# -----------------------
# Zbiorcze przeładowanie systemd i restart usług
# -----------------------
log "Przeładowanie systemd i zbiorczy restart usług (jeśli istnieją)..."
sudo systemctl daemon-reload

SERVICES_TO_CHECK=(
  "mpd.service"
  "bluealsa.service"
  "camilladsp.service"
  "oled.service"
)

for s in "${SERVICES_TO_CHECK[@]}"; do
  restart_service_if_exists "$s"
done

log "=============================================="
log " Instalacja zakończona. Jeśli zmieniałeś dtoverlay/dtparam, uruchom ponownie RPi."
log "=============================================="

exit 0
