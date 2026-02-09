#!/bin/bash
set -e

echo "[configure_camilladsp] Instaluję i konfiguruję CamillaDSP..."

# ================================
# 1. Pobranie CamillaDSP
# ================================
LATEST_URL=$(curl -s https://api.github.com/repos/HEnquist/camilladsp/releases/latest \
    | grep browser_download_url \
    | grep arm64.deb \
    | cut -d '"' -f 4)

echo "[configure_camilladsp] Pobieram: $LATEST_URL"
wget -q "$LATEST_URL" -O /tmp/camilladsp.deb

sudo apt install -y /tmp/camilladsp.deb
rm /tmp/camilladsp.deb

# ================================
# 2. Katalog konfiguracyjny
# ================================
sudo mkdir -p /etc/camilladsp

cat <<EOF | sudo tee /etc/camilladsp/config.yml
version: 1
pipeline:
  - type: Gain
    gain: 0
EOF

# ================================
# 3. Usługa systemd
# ================================
cat <<EOF | sudo tee /etc/systemd/system/camilladsp.service
[Unit]
Description=CamillaDSP Audio Processor
After=sound.target

[Service]
ExecStart=/usr/bin/camilladsp -p /etc/camilladsp/config.yml
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable camilladsp
sudo systemctl restart camilladsp

echo "[configure_camilladsp] CamillaDSP gotowy."
