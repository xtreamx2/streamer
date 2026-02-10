#!/bin/bash
set -e

echo "[install_python] Instaluję biblioteki Python..."

sudo apt install -y python3-pip python3-venv build-essential libjpeg-dev zlib1g-dev

sudo -H python3 -m pip install --break-system-packages --upgrade pip setuptools wheel

sudo -H python3 -m pip install --break-system-packages \
    RPi.GPIO \
    smbus2 \
    pillow \
    python-mpd2 \
    luma.oled
    
sudo apt install -y python3-flask
