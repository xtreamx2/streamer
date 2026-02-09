#!/bin/bash
set -e

echo "[clone_repo] Pobieram projekt z GitHub..."

REPO_URL="https://github.com/xtreamx2/streamer.git"
TARGET_DIR="/home/$USER/streamer"
BRANCH="Second"

# Jeśli repo istnieje → aktualizacja
if [ -d "$TARGET_DIR/.git" ]; then
    echo "[clone_repo] Repozytorium już istnieje — aktualizuję."
    cd "$TARGET_DIR"
    git fetch
    git checkout "$BRANCH"
    git pull
else
    echo "[clone_repo] Klonuję repozytorium (gałąź: $BRANCH)..."
    git clone -b "$BRANCH" "$REPO_URL" "$TARGET_DIR"
fi
