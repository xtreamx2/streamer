#!/bin/bash
# Radio Watchdog v5 - auto-recover bez user intervention

LOGFILE=~/streamer/logs/watchdog.log
PIDFILE=~/streamer/logs/watchdog.pid
CHECK_INTERVAL=5  # Co ile sekund sprawdzać

echo $$ > $PIDFILE
log() { echo "[$(date '+%H:%M:%S')] $1" >> $LOGFILE; }

log "=== Watchdog v5 started ==="

while true; do
    # Sprawdź czy MPD gra
    if ! mpc status | grep -q "\[playing\]"; then
        log "⚠️  NOT playing! Auto-recover..."
        
        # Pobierz aktualny URL z playlisty
        CURRENT_URL=$(mpc playlist | head -1)
        
        if [ -n "$CURRENT_URL" ]; then
            # Uruchom skrypt z 10 kopiami
            /home/tom/streamer/radio_play.sh "$CURRENT_URL" 10
            log "✅ Recovered with: $CURRENT_URL"
        else
            log "❌ No URL in playlist!"
        fi
    fi
    
    sleep $CHECK_INTERVAL
done
