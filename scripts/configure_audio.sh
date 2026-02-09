#!/bin/bash
set -e

echo "[configure_audio] Konfiguruję I2S + rpi-dac..."

CONFIG="/boot/config.txt"

# Usuń stare overlaye DAC
sudo sed -i '/dtoverlay=hifiberry-dacplus/d' "$CONFIG"
sudo sed -i '/dtoverlay=rpi-dac/d' "$CONFIG"
sudo sed -i '/dtparam=i2s=on/d' "$CONFIG"

# Dodaj nowe wpisy
echo "dtoverlay=rpi-dac" | sudo tee -a "$CONFIG" >/dev/null
echo "dtparam=i2s=on" | sudo tee -a "$CONFIG" >/dev/null

echo "[configure_audio] Ustawiono:"
echo "  dtoverlay=rpi-dac"
echo "  dtparam=i2s=on"
echo "[configure_audio] Restart wymagany, aby DAC został wykryty."
