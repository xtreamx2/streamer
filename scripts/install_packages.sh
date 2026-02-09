#!/bin/bash
set -e

echo "[install_packages] Instaluję pakiety systemowe..."

sudo apt install -y \
    mpd mpc \
    python3 python3-pip python3-venv \
    git i2c-tools alsa-utils \
    curl wget unzip

# pakiety usunięte
# bluez bluealsa bluealsa-aplay
# camilladsp
