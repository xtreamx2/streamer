#!/bin/bash
# Universal Radio Player - 10 copies loop (no metadata stop!)

STREAM_URL="$1"
COPIES="${2:-10}"

if [ -z "$STREAM_URL" ]; then
    echo "Usage: $0 <stream_url> [copies]"
    exit 1
fi

mpc clear >/dev/null 2>&1

for i in $(seq 1 $COPIES); do
    mpc add "$STREAM_URL" >/dev/null 2>&1
done

mpc consume off >/dev/null 2>&1
mpc single off >/dev/null 2>&1
mpc repeat on >/dev/null 2>&1
mpc play >/dev/null 2>&1
