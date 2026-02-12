#!/bin/bash
set -e

echo "=== Aktualizacja systemu ==="
apt update
apt upgrade -y

echo "=== Instalacja MPD ==="
apt install -y mpd mpc

echo "=== Instalacja Snapcast (opcjonalnie) ==="
# apt install -y snapserver snapclient

echo "=== Instalacja CamillaDSP (Rust) ==="
wget https://github.com/HEnquist/camilladsp/releases/latest/download/camilladsp-linux-aarch64.tar.gz
rm -f camilladsp
tar xvf camilladsp-linux-aarch64.tar.gz
cp camilladsp /usr/local/bin/
chmod +x /usr/local/bin/camilladsp

echo "=== Instalacja bibliotek do I2C, OLED, GPIO ==="
echo "=== Instalacja bibliotek do I2C, OLED, GPIO ==="
apt install -y python3 python3-pip python3-smbus i2c-tools python3-rpi.gpio
pip3 install --break-system-packages adafruit-circuitpython-ssd1306

echo "=== Tworzenie katalogów projektu ==="
mkdir -p /opt/streamer
mkdir -p /opt/streamer/www
mkdir -p /opt/streamer/daemon

echo "=== Pobieranie plików projektu z GitHub ==="
git clone https://github.com/xtreamx2/streamer.git /opt/streamer

echo "=== Instalacja usług systemd ==="
cp /opt/streamer/systemd/mpd.service /etc/systemd/system/
cp /opt/streamer/systemd/camilladsp.service /etc/systemd/system/
cp /opt/streamer/systemd/daemon.service /etc/systemd/system/
cp /opt/streamer/systemd/www.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable mpd
systemctl enable camilladsp
systemctl enable daemon
systemctl enable www

echo "=== Instalacja zakończona ==="
