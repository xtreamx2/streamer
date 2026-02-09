#!/bin/bash
set -e

echo "[configure_camilladsp] Instaluję i konfiguruję CamillaDSP..."

# ================================
# 0. Sprawdzenie czy już jest
# ================================
if command -v camilladsp >/dev/null 2>&1; then
    echo "[configure_camilladsp] CamillaDSP już jest zainstalowany — pomijam instalację."
else
    echo "[configure_camilladsp] CamillaDSP nie znaleziony — instaluję najnowszą wersję."

    # ================================
    # 1. Instalacja rustup (Rust 1.82+)
    # ================================
    if ! command -v rustup >/dev/null 2>&1; then
        echo "[configure_camilladsp] Instaluję rustup (Rust 1.82+)..."
        curl https://sh.rustup.rs -sSf | sh -s -- -y
        source $HOME/.cargo/env
    else
        echo "[configure_camilladsp] rustup już zainstalowany."
        source $HOME/.cargo/env
    fi

    rustup update stable

    # ================================
    # 2. Pobranie źródeł (tylko raz)
    # ================================
    if [ ! -d "/home/$USER/camilladsp" ]; then
        echo "[configure_camilladsp] Pobieram repozytorium..."
        git clone https://github.com/HEnquist/camilladsp /home/$USER/camilladsp
    else
        echo "[configure_camilladsp] Repozytorium już istnieje — aktualizuję."
        cd /home/$USER/camilladsp
        git pull
    fi

    # ================================
    # 3. Kompilacja
    # ================================
    cd /home/$USER/camilladsp
    echo "[configure_camilladsp] Kompiluję CamillaDSP..."
    cargo build --release

    # ================================
    # 4. Instalacja binarki
    # ================================
    sudo cp target/release/camilladsp /usr/bin/
fi

# ================================
# 5. Katalog konfiguracyjny
# ================================
sudo mkdir -p /etc/camilladsp

cat <<EOF | sudo tee /etc/camilladsp/config.yml
version: 1
pipeline:
  - type: Gain
    gain: 0
EOF

# ================================
# 6. Usługa systemd
# ================================
cat <<EOF | sudo tee /etc/systemd/system/camilladsp.service
[Unit]
Description=CamillaDSP Audio Processor
After=sound.target

[Service]
ExecStart=/usr/bin/camilladsp -p /etc/camilladsp/config.yml
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable camilladsp
sudo systemctl restart camilladsp

echo "[configure_camilladsp] CamillaDSP gotowy."
