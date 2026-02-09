#!/bin/bash
set -e

echo "[clone_repo] Pobieram projekt z GitHub..."

cd /home/$USER

if [ -d "streamer" ]; then
    echo "[clone_repo] Katalog streamer już istnieje — pomijam klonowanie."
else
    git clone https://github.com/<repo>/streamer.git
fi
