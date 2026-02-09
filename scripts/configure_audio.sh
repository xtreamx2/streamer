#!/bin/bash
set -e

echo "[configure_audio] Konfiguruję I2S + PCM5122..."

sudo sed -i '/dtparam=i2s=on/d' /boot/config.txt
sudo sed -i '/dtoverlay=hifiberry-dacplus/d' /boot/config.txt

echo "dtparam=i2s=on" | sudo tee -a /boot/config.txt
echo "dtoverlay=hifiberry-dacplus" | sudo tee -a /boot/config.txt
