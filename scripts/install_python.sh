#!/bin/bash
set -e

echo "[install_python] Instaluję biblioteki Python..."

# Zależności systemowe potrzebne do Pillow i kompilacji niektórych pakietów
sudo apt install -y python3-pip python3-venv build-essential libjpeg-dev zlib1g-dev

# Uaktualnij pip/setuptools wheel (globalnie)
sudo -H python3 -m pip install --upgrade pip setuptools wheel

# Instalacja bibliotek wymaganych przez projekt
# --break-system-packages pozostawiamy jeśli system wymaga (Debian/Ubuntu pip policy)
sudo -H python3 -m pip install --break-system-packages \
    RPi.GPIO \
    smbus2 \
    pillow \
    python-mpd2 \
    luma.oled

echo "[install_python] Gotowe."
