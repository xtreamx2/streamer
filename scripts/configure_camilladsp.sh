#!/bin/bash
set -e

echo "[configure_camilladsp] Konfiguruję CamillaDSP..."

sudo mkdir -p /etc/camilladsp

# Domyślny config (placeholder)
cat <<EOF | sudo tee /etc/camilladsp/config.yml
# Minimalny config CamillaDSP
version: 1
pipeline:
  - type: Gain
    gain: 0
EOF

sudo systemctl enable camilladsp
