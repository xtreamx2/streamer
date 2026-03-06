#!/bin/bash
set -e

echo "[configure_mpd] Konfiguruję MPD..."

sudo systemctl stop mpd

sudo sed -i 's/^audio_output.*/audio_output {\
    type "alsa"\
    name "PCM5122"\
    device "hw:0,0"\
}/' /etc/mpd.conf

sudo systemctl enable mpd
