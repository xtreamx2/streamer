
## v0.10.4.0 — 2026-03-11

### Projekt
- Nazwa projektu zmieniona na **PylonisAmp**
- Licencja zmieniona na **GNU GPL v3.0**
- Dodany plik LICENSE.md

### Naprawione
- `api/meters` — pobiera z aktywnego źródła (nie zawsze radio), 16 pasm spectrum
- UART — ping/pong co 8s; `active` = true tylko gdy RP2040 odpowiada
- Bitrate FLAC — szuka `nominal-bitrate`/`maximum-bitrate` gdy `bitrate` jest puste
- Codec display — skraca długie nazwy do skrótu z nawiasów np. "Free Lossless Audio Codec (FLAC)" → "FLAC"
- `_save_config` — debounce 5s dla EQ/gain/last_source (ochrona karty SD)
- EQ save 500 — `active_source` (property) zamiast `active_source()` (błąd wywołania)
- `_meterBusy` guard — przeniesiony do scope globalnego
- `loadUserPresetNames` — usunięty duplikat wywołania

### Nowe
- Gain per wejście (-10..+6 dB) — suwaki w Settings → "Gain wejść"
- Auto Gain — przy CLIP obniża gain o 1 dB i zapisuje per source
