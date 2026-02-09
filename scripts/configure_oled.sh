#!/bin/bash
set -e

echo "[configure_oled] Konfiguruję OLED (I2C)..."

CONFIG="/boot/firmware/config.txt"

# ================================
# 1. Włącz I2C
# ================================
sudo sed -i '/dtparam=i2c_arm=on/d' "$CONFIG"
echo "dtparam=i2c_arm=on" | sudo tee -a "$CONFIG" >/dev/null

# ================================
# 2. Instalacja zależności
# ================================
sudo apt install -y i2c-tools python3-smbus python3-pil

# ================================
# 3. Sprawdzenie magistrali
# ================================
if [ ! -e /dev/i2c-1 ]; then
    echo "[configure_oled] I2C nieaktywne — wymagany restart."
    exit 0
fi

# ================================
# 4. Wykrywanie OLED
# ================================
ADDR=$(i2cdetect -y 1 | grep -oE '3c|3d' | head -n 1)

if [ -z "$ADDR" ]; then
    echo "[configure_oled] [-] OLED nie wykryty — pomijam konfigurację."
    exit 0
fi

echo "[configure_oled] [OK] Wykryto OLED na adresie 0x$ADDR."

# ================================
# 5. Zapis konfiguracji OLED
# ================================
sudo mkdir -p /etc/streamer
echo "oled_address=0x$ADDR" | sudo tee /etc/streamer/oled.conf >/dev/null

echo "[configure_oled] OLED gotowy."
