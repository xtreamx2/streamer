#!/bin/bash
set -e

echo "[configure_audio] Konfiguruję I2S + rpi-dac..."

# Bookworm używa nowej ścieżki:
CONFIG="/boot/firmware/config.txt"

# ================================
# 1. Usuń stare wpisy DAC
# ================================
sudo sed -i '/dtoverlay=hifiberry-dacplus/d' "$CONFIG"
sudo sed -i '/dtoverlay=rpi-dac/d' "$CONFIG"
sudo sed -i '/dtparam=i2s=on/d' "$CONFIG"

# ================================
# 2. Dodaj właściwy overlay
# ================================
echo "dtoverlay=rpi-dac" | sudo tee -a "$CONFIG" >/dev/null
echo "dtparam=i2s=on" | sudo tee -a "$CONFIG" >/dev/null

echo "[configure_audio] Ustawiono:"
echo "  dtoverlay=rpi-dac"
echo "  dtparam=i2s=on"

echo "[configure_audio] Restart wymagany, aby DAC został wykryty."
