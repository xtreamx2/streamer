# Changelog — Raspberry Pi Audio Streamer

Format zgodny z [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Wersjonowanie zgodne z `0.xxx` (pre‑alpha).

---

## [0.011a] - 2026-02-11
### Dodano
- EQ
- Web server na porcie 8080

###
- nadal problemy z Enkoderem i EQ

## [0.010a] — 2026‑02‑10
### Dodano
- Utworzono pełną strukturę projektu (`audio/`, `ui/`, `hardware/`, `utils/`, `scripts/`).
- Dodano instalator `install.sh` z wyborem trybu (instalacja/aktualizacja).
- Dodano logger z przełącznikiem `ENABLE_LOGGER`.
- Dodano inteligentne wykrywanie sprzętu (DAC, OLED, BT, Wi‑Fi).
- Dodano bezpieczne restartowanie usług (tylko jeśli istnieją).
- Dodano komplet skryptów instalacyjnych w `scripts/`.

### Zmieniono
- kompletnie przebudowano projekt od nowa
- Uproszczono logikę instalatora — jedno pytanie na start.
- Ujednolicono komunikaty instalatora (OK / WARN / ERROR).

### Znane problemy
- Brak pełnej konfiguracji CamillaDSP (placeholder).
- Brak usługi OLED (zostanie dodana po implementacji UI).

---

## [0.000] — 2026‑02‑01
### Start projektu
- Utworzenie repozytorium.
- Wstępne założenia funkcjonalne.
