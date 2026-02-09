#!/bin/bash
set -e

echo "[install_python] Instaluję biblioteki Python..."

python3 -m pip install --break-system-packages \
    RPi.GPIO \
    smbus2 \
    pillow \
    mpd2
