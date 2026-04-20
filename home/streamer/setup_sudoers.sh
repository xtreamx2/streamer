#!/bin/bash
# Uruchom raz jako root żeby dodać uprawnienia dla streamera
echo "tom ALL=(ALL) NOPASSWD: /bin/systemctl start bluealsa-aplay, /bin/systemctl stop bluealsa-aplay" \
  | sudo tee /etc/sudoers.d/streamer-bluealsa
sudo chmod 440 /etc/sudoers.d/streamer-bluealsa
echo "OK"
