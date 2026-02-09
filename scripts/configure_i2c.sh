#!/bin/bash
set -e

echo "[configure_i2c] Włączam I2C..."

CONFIG="/boot/firmware/config.txt"

# Usuń stare wpisy
sudo sed -i '/dtparam=i2c_arm=on/d' "$CONFIG"
sudo sed -i '/dtoverlay=i2c1/d' "$CONFIG"

# Dodaj poprawną konfigurację I2C1 na pinach 2/3
echo "dtparam=i2c_arm=on"        | sudo tee -a "$CONFIG" >/dev/null
echo "dtoverlay=i2c1,pins_2_3"  | sudo tee -a "$CONFIG" >/dev/null

echo "[configure_i2c] Ustawiono:"
echo "  dtparam=i2c_arm=on"
echo "  dtoverlay=i2c1,pins_2_3"
echo "[configure_i2c] Restart wymagany, aby I2C zostało aktywowane."

# Załaduj moduły I2C teraz
sudo modprobe i2c-bcm2835 || true
sudo modprobe i2c-dev || true

# Upewnij się, że ładują się przy starcie
echo "i2c-bcm2835" | sudo tee /etc/modules-load.d/i2c.conf >/dev/null
echo "i2c-dev"     | sudo tee -a /etc/modules-load.d/i2c.conf >/dev/null
