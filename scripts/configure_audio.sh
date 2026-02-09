#!/bin/bash
set -e

echo "[configure_audio] Konfiguruję I2S + rpi-dac..."

CONFIG="/boot/firmware/config.txt"

# Czyścimy stare wpisy DAC
sudo sed -i '/dtoverlay=hifiberry-dacplus/d' "$CONFIG"
sudo sed -i '/dtoverlay=rpi-dac/d' "$CONFIG"
sudo sed -i '/dtparam=i2s=on/d' "$CONFIG"

# Dodajemy DAC PO I2C (I2C ustawia configure_i2c.sh)
echo "dtoverlay=rpi-dac" | sudo tee -a "$CONFIG" >/dev/null
echo "dtparam=i2s=on"    | sudo tee -a "$CONFIG" >/dev/null

echo "[configure_audio] Ustawiono:"
echo "  dtoverlay=rpi-dac"
echo "  dtparam=i2s=on"
echo "[configure_audio] Restart wymagany, aby DAC został wykryty."
