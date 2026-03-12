# 🎵 Tom's Streamer Audio

**Data ukończenia:** 2026-03-05 
**Status:** ✅ ALPHA COMPLETE
**Wersja:** v0.10.3.22 (Alpha)

## 🚀 Cechy Główne
- [x] MPD + Internet Radio Streaming ✅
- [x] Flask WWW UI (Port 8000) ✅
- [x] Documentation

## 🔜 v0.10.5 Roadmap
- [x] EQ Sliders w UI ✅
- [x] Bluetooth jako źródło audio ✅
- [x] Selector źródeł (Radio/BT/Analog) ✅
- [ ] Phase 2: RP2040 + LCD Touch Interface (Brak hardware jeszcze)

## 📖 Opis

Internet Radio Streamer z EQ) i WWW UI (Flask).

**Hardware:**
- Raspberry Pi 3
- PCM5102 DAC (I2S)
- Słuchawki głośniki

**Software:**
- GStreamer (Music Player Daemon with EQ 10-band
- Flask + SocketIO (WWW UI)
- ALSA Loopback (audio chain)

## ✅ Working Features

| Feature | Status | Notes |
|---------|--------|-------|
| MPD streaming | ✅ | Internet radio |
| Flask WWW UI | ✅ | Port 8000 |
| Radio CRUD | ✅ | Add/delete/favorites |
| VU Meter | ⚠️ | wirk but not good |
| Theme toggle | ⚠️ | Dark only |

**Known issues:**
- Spectrum analiser - not working
- RP2040 + LCD hardware UI (Phase 2)

✅ VU Meter - czytelny layout (2 słupki, poziomo)
✅ Gradient colors - niebieski→żółty→czerwony
✅ VU/Spectrum toggle - przełącznik działa (analizator już nie)
✅ Radio CRUR + favorites - działa
✅ EQ - działa (10-band)
✅ Flask API - działa
✅ Backup + README - gotowe

Hi-Res Internet Radio Streamer with EQ

## 📁 Project Structure

- streamer/
- ├── api/
- │   ├── app.py          # Flask + SocketIO, punkt wejściowy
- │   └── routes.py       # REST API /api/*
- ├── core/
- │   ├── source_manager.py   # przełączanie źródeł
- │   ├── eq_manager.py       # EQ per źródło, presety
- │   ├── uart_manager.py     # JSON UART ↔ RP2040
- │   ├── bt_manager.py       # BlueZ fasada
- │   └── network_manager.py  # nmcli WiFi
- ├── sources/
- │   ├── base.py             # klasa bazowa
- │   ├── radio.py            # ✅ Internet radio (GStreamer)
- │   ├── bluetooth.py        # ✅ A2DP sink + source (BlueZ)
- │   ├── analog.py           # 🔲 Phono / Line (szkielet)
- │   └── digital.py          # 🔲 S/PDIF (szkielet)
- ├── web/
- │   └── templates/
- │       └── index.html      # Web UI
- ├── radio/
- │   └── stations.json
- ├── config.json
- ├── requirements.txt
- └── streamer.service

## 🔧 Quick Start
```bash
# 1. Zależności systemowe
sudo apt update
sudo apt install python3-gi python3-gi-cairo \
  gir1.2-gstreamer-1.0 \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly gstreamer1.0-alsa gstreamer1.0-libav \
  python3-dbus bluetooth bluez

# 2. Zależności Python
pip3 install -r requirements.txt --break-system-packages

# 3. Konfiguracja
cp streamer.service /etc/systemd/system/
# Edytuj: User=tom, WorkingDirectory, ALSA_DEVICE, UART_PORT

# 4. Uruchomienie
sudo systemctl daemon-reload
sudo systemctl enable streamer
sudo systemctl start streamer
```

##
🚀 Phase 2 (TODO)
RP2040 + LCD hardware UI
UART communication (RP ↔ Pi)
Physical encoders + buttons
IR remote control
Analog input (PCM1808)
##

📊 Changelog

PylonisAmp v0.10.4.16:
- Shutdown - naprawiony, pojawia się obok Reboot w sekcji "System" w Settings
- Phono - pointer-events:none + opacity:0.4 — nie można kliknąć
- Stare wejście "Line" - usunięte, zostają tylko Line In 1 i Line In 2
- Zakładka IN - wszystkie karty wycieniowane, cursor:not-allowed, bez onclick
- Spectrum po powrocie - showPage('amplifier') jawnie restartuje RAF spectrum jeśli _meterMode === 'spectrum'

PylonisAmp v0.10.4.15 - zbudowany czysto od v0.10.4.12, tylko 4 zmiany:
- Shutdown - przycisk w Settings, endpoint /api/system/shutdown
- Phono disabled - wycieniowany, cursor:not-allowed
- Line In 1, Line In 2, USB - dodane jako disabled po S/PDIF
- meter_mode - zapisywany w config.json, przywracany po starcie. VU/Spectrum jako radio buttons

PylonisAmp v0.10.4.14 - budowany od czystej bazy v0.10.4.12:
Nawigacja naprawiona - brak duplikacji buttonów
VU/Spectrum - radio buttons, stan zapisywany jako meter_mode w config.json, przywracany po starcie
- showPage - stop/start spectrum przy zmianie podstrony
- Shutdown - przycisk w Settings (pomarańczowy)
- Phono/Line In 1/2/USB/S-PDIF - wszystkie wycieniowane (opacity:0.4, pointer-events:none, kursor "zabroniony")
- Ikony - bez zmian (artystyczne zostawiamy na osobną sesję gdy będzie stabilna baza)

PylonisAmp v0.10.4.13 - BUG (HTML error):
- Przełącznik VU/Spectrum usunięty z wnętrza panelu - sterowanie tylko przez chipy na górze. Stan zapisywany w config.json jako meter_mode ('vu'/'spectrum'/'off'), przywracany po załadowaniu strony
- Shutdown - przycisk w Settings obok Reboot, pomarańczowy, pyta o potwierdzenie, pokazuje "Wyłączanie..."
- Wejścia analog - Phono/Line wycieniowane z podpisem "wkrótce", S/PDIF już był disabled
- Ikony źródeł - artystyczne SVG: płyta winylowa z fioletową poświatą, antena z neonami, pastylka BT, TOSLINK z laserem

PylonisAmp v0.10.4.12:
- VU/Spectrum — radio buttons — kliknięcie jednego wyłącza drugi, można też kliknąć aktywny żeby schować wskaźniki
- Phono i Line — wycieniowane (opacity: 0.35, pointer-events: none, podpis "wkrótce") — czekają na PCM1808
- S/PDIF — już był wycieniowany klasą disabled

PylonisAmp v0.10.4.11:
- 30fps — timer co 33ms, fetch timeout 80ms
- Peak hold — 800ms hold, 60 dB/s opadanie (było ~12 dB/s)
- Skala logarytmiczna — etykiety na precyzyjnych pozycjach: -60 · -18 · -12 · -6 · -3 · 0
- Gradient — żółty przy -17 dBFS (≈0 VU), czerwony od -4 dBFS
- Nazwa — PylonisAmp wszędzie

PylonisAmp v0.10.4.10 - bump minorowy bo zmian dużo:
- Przełącznik VU/Spectrum po powrocie ze strony - showPage('amplifier') teraz jawnie resetuje timer i RAF, potem wywołuje initMeterMode() + startSpectrum(). To był główny bug
- VU peak hold - opadanie clampowane do -60 dBFS (nie mogło spaść w nieskończoność), obia kanały mają pełną logikę
- Pierwsze pasma spectrum - zamiast czystego max() używa teraz 70% max + 30% średnia - mniej szarpane przejścia między grupami
- UART - connected zamiast active

PylonisAmp v0.10.4.7-9:
- Spectrum 32 pasm - wszystkie 32 wyświetlane. Pasma 25-32 (16-22 kHz)
- Autogain - dodany do /api/status, UI odczytuje stan po załadowaniu strony
- UART - pokazuje connected (port otwarty) zamiast active (wymaga pong od RP2040)

PylonisAmp v0.10.4.6:
- VU metr — teraz prawdziwa skala VU:
- 0 VU = -18 dBFS (standard broadcasting/recording)
- Zakres: -20 VU do +5 VU
- Etykiety: -20, -10, -7, -3, 0, +3 VU
- Gradient: niebieski poniżej 0 VU, żółty przy 0 VU, czerwony od +3 VU

Spectrum — 24 z 32 pasm (0–16.5 kHz):
- GStreamer nadal liczy 32 pasma liniowo
- Ostatnie 8 (16.5–22 kHz) są odcinane bo tam nic nie ma w muzyce
- Wszystkie 24 aktywne pasma będą wypełnione

PylonisAmp v0.10.4.5:
- Skala VU: -48..0 dBFS - zamiast -60..0 — bardziej zgodna z profesjonalnymi VU metrami. Trance przy -7dB RMS będzie na ~85% - to poprawne, ta muzyka jest masterowana bardzo głośno (loudness war)
- Znaczniki - zaktualizowane: -48, -30, -15, -9, -3, 0
- Gradient - przesunięty: żółty od -9dB, pomarańcz od -5dB, czerwony od -2dB
- GStreamer peak-ttl = 0 - brak podwójnego hold (GStreamer + JS), teraz tylko JS robi hold

PylonisAmp v0.10.4.4:
- 32 pasma - n=32 zahardkodowane w canvas draw, Array zamiast TypedArray
- Codec - przywrócona pełna nazwa "Free Lossless Audio Codec (FLAC)"
- Bit depth - 44.1 kHz/16bit (wyciągane z GStreamer caps S16LE)
- Peak hold naprawiony - prosta logika: opadanie 1.5 dB per tick (~120ms) = ~12.5 dB/s, bez błędów akumulacji czasu
- Cache buster - meta tag z wersją wymusza nowy JS

PylonisAmp v0.10.4.3:
- VU peak hold - naprawiony błąd w algorytmie opadania (mnożnik * 0.01 powodował że peak prawie nigdy nie opadał). Teraz: hold 1.5s, opadanie ~18 dB/s
- Spectrum 32 pasm - canvas rysuje zawsze n=32, restart RAF przy każdym powrocie na stronę
- Gradient - progi jak w v0.10.4.2

PylonisAmp v0.10.4.2:
- 32 pasma -  spectrum (GStreamer + API + JS)
- Gradient VU i Spectrum - nowe progi: niebieski do -23dB, żółty od -15dB, pomarańcz od -7dB, czerwony od -3dB, mocny czerwony przy 0dB (clip)

PylonisAmp v0.10.4.1:
- naprawiony przełącznik VU/Spectrum - Problem polegał na tym że _specDraw (canvas animation loop przez requestAnimationFrame) zatrzymywał się gdy canvas był ukryty

PylonisAmp v0.10.4.0 - PylonisAmp:
- Spectrum - api/meters pobiera teraz z aktywnego źródła (wcześniej zawsze z radio nawet gdy nieaktywne), 16 pasm
- Bitrate - szuka nominal-bitrate/maximum-bitrate dla FLAC; codec "Free Lossless Audio Codec (FLAC)" → "FLAC"
- UART ping/pong - co 8s wysyła {"cmd":"ping"} do RP2040, oczekuje {"evt":"pong"}; active=true tylko gdy odpowiedź przyszła w ostatnich 30s. Wymaga aktualizacji firmware RP2040 żeby odpowiadał na ping.
- Nazwa - PylonisAmp, licencja GPL v3, CHANGELOG.md

```
Zmiana nazwy projektu na PylonisAmp - połączenie "kolumny głośnikowe + ucho + oraz wzmacniacz"
```

v0.10.3.35:
- EQ save
- Spectrum/VU - naprawiony regex w initMeterMode, timeout skrócony do 500ms
- SD card - _save_config(debounce=True) dla EQ/gain/last_source — max 1 zapis co 5s; volume zapisuje natychmiast
- Bitrate FLAC - teraz próbuje bitrate, nominal-bitrate, maximum-bitrate po kolei
- Mono - usunięty z UI całkowicie

v0.10.3.34:
EQ save 500 - active_id() nie istniało, zastąpione active_source().SOURCE_ID
werkzeug logi - wyciszone (tylko WARNING+), błędy będą widoczne w journalctl
loadUserPresetNames - usunięty duplikat
Gain per wejście - suwaki -10..+6 dB w Settings → "Gain wejść"
Auto Gain - przywrócony z nową logiką CLIP

v0.10.3.33:
- 500 na /api/status - _last_rx był niezdefiniowany w __init__, stąd AttributeError
- _meterBusy guard - przeniesiony do scope globalnego, teraz naprawdę blokuje kolejne requesty
- Auto Gain - przywrócony z etykietą i opisem; logika: przy CLIP (peak ≥ -0.1 dBFS) obniża gain o 1dB i zapisuje
- Gain per wejście - suwaki -10..+6 dB w sekcji "Gain wejść" w Settings; stosowany jako pre-gain przy każdym przełączeniu źródła
- Naprawione etykiety Mono w ustawieniach

v0.10.3.32 - bug APP (część modułów zaliczyło crash):
- VU - RMS bar bezpośrednio (bez smoothing) = dynamiczne
- User1/User2 preset - PRESETS w JS ma user1/user2, loadUserPresetNames() wczytuje gains z serwera, saveUserPreset aktualizuje lokalnie po zapisie
- Auto Gain - usunięty z UI (nie był zaimplementowany)
- UART status - active zamiast connected — OK tylko gdy RP2040 przysłał dane w ostatnich 30s
- WiFi toggle - przyciski w Network page

v0.10.3.31:
- Edit → Direct - przycisk naprawiony (był zduplikowany w pliku)
- VU peak - teraz śledzi max RMS (nie surowy peak z GStreamer który zawsze jest blisko 0dB), płynne RMS bar, 2s hold
- IP - eth0 ma priorytet nad wlan0
- WiFi - przyciski "WiFi OFF/ON" i "Rozłącz" w Network page
- streamer.service - wersja aktualizowana automatycznie

v0.10.3.30:
- ERR_CONNECTION_RESET - initMeterMode z 2s opóźnieniem, serwer ma czas się uruchomić
- Peak hold - timestamp-based (1.5s hold, potem płynne opadanie), nie zależy od szybkości animacji
- Spectrum - warunek hasFft sprawdza czy jakiekolwiek pasmo > -58 (nie tylko pierwsze)
- streamer.service - wersja zsynchronizowana z app.py, usunięty zduplikowany After=

v0.10.3.29 - bug APP (nie włącza się):
- Direct - przycisk zastępuje Edit w sekcji EQ; aktywny = bypass EQ (wszystkie pasma 0) + ignoruje loudness
- User 1 / User 2 - presety EQ w ustawieniach; "Save →" zapisuje bieżące nastawy, "Rename" zmienia nazwę
- initMeterMode - spectrum/VU włącza się automatycznie przy ładowaniu strony

'''
loudness w tym projekcie jest tylko jako preset EQ (zestaw gainów) - nie jest jeszcze stosowany jako dodatkowa korekta na bieżący preset.
'''

v0.10.3.25-28:
- ciągła poprawa spectrum analizator
- spectrum 16 pasm zamiast 32 (string ~590 znaków, mieści się w to_string()), czysty regex parse.
- spectrum fix: zamiast get_value('magnitude') (które crashuje na GstValueList), parsujemy structure.to_string() przez regex.

v0.10.3.24:
- VU zawieszanie - _meterBusy guard - pomija request jeśli poprzedni nie wrócił, eliminuje kolejkowanie
- Peak hold - JS-owy hold 1.5s + płynne opadanie 0.8dB/frame, niezależny od serwera
- Pipeline - level+spectrum przed EQ/vol (surowy sygnał)

v0.10.3.23:
- Pipeline - level i spectrum przeniesione przed EQ/vol — mierzą surowy sygnał, nie zależą od głośności
- Peak-ttl - skrócony do 100ms (szybsze opadanie)

v0.10.3.22:
- Zakładka -Streamer · TrancePulse dla radia (nazwa stacji), Streamer · Bluetooth dla BT itd.
- Stream info -kHz i Stereo/ch z GStreamer - BUG
- Spectrum - element teraz w prawidłowym miejscu pipeline, powinien wysyłać dane
- IP - zawsze pobiera z eth0 pierwszego
- Zakładka - Streamer · TrancePulse
- Stream info - kHz i Stereo już w poprzedniej wersji

v0.10.3.21:
- Meters - jeden endpoint /api/meters zamiast dwóch, polling co 100ms — koniec z ERR_CONNECTION_RESET
- BT/Radio konflikt ALSA - bluealsa-aplay automatycznie zatrzymywany gdy radio aktywne, wznawiany gdy BT aktywne
- Spectrum - te same dane, ale teraz serwer nie pada pod obciążeniem

v0.10.3.20:
- IP - fallback na eth0/wlan0/end0, zwraca IP niezależnie od interfejsu
- Spectrum - prawdziwy FFT z GStreamer spectrum element (32 pasma), endpoint /api/spectrum, canvas rysuje realne dane
- VU polling - 80ms zamiast 60ms

v0.10.3.19 changelog: 
Bugfix:
- usunięty subprocess bluealsa-aplay z kodu, audio BT obsługuje teraz systemowy serwis.
Podsumowanie stanu BT:
- bluealsa.service -daemon BlueZ A2DP
- bluealsa-aplay.service -przekazuje audio na hw:sndrpihifiberry,0 (skonfigurowany przez override)
- Streamer -obsługuje tylko parowanie/connect przez D-Bus, audio zostawia systemowi

v0.10.3.18 changelog:
- Stacja - przywracana przy starcie zawsze, oraz automatycznie gdy przełączasz z BT/innego źródła na radio
- Głośność - przywracana do wszystkich sources przy starcie
- Śmieciowy katalog - usunięty z paczki (usuń też na malinie: rm -rf "/home/$USER/streamer/{core,sources,api,web")

v0.10.3.17 changelog:
- Stacja - przywracana zawsze przy starcie, niezależnie od last_source
- BT audio - bluealsa-aplay w pętli wątkowej, automatycznie restartuje gdy telefon zaczyna/kończy grać
- Spectrum - usunięty roundRect (niekompatybilny ze starszym Chromium), naprawiony rozmiar canvas

v0.10.3.16 changelog:
- Spectrum/VU - chip VU domyślnie on, container widoczny od startu
- IP - usunięte błędne pole IP4 z nmcli
- BT audio - bluealsa-aplay uruchamiany jako subprocess przy activate, zatrzymywany przy deactivate

v0.10.3.15 changelog:
- Peak hold - marker przeniesiony poza maskę CSS, biały z glow, widoczny
- Spectrum - 32 pasma animowane przez requestAnimationFrame, kształt EQ-like (basy/górne wzmocnione), peak ticki białe, ten sam gradient co VU, płynne opadanie

v0.10.3.14 changelog:
- Gradient zawsze rozłożony na całej szerokości tracku (niebieski → żółty → czerwony)
- Ciemna maska CSS ::after odkrywa gradient proporcjonalnie do poziomu
- Peak marker biały z delikatnym glow
- Brak JS manipulacji kolorem — wszystko w CSS

v0.10.3.10 changelog:
- Sieć - naprawiony parser nmcli (obsługuje connected (externally))
- Loudness - endpoint /api/setting + zapis w config + przywracanie przy starcie
- Ostatnia stacja radiowa - przywracana automatycznie po restarcie
- BT - auto-trust przy connect

v0.10.3 changelog:
New:
- parowanie BT
- W-Fi conect

Bugfix:
- Sieć — usunięte hardkodowane dane, dynamiczne ID, filtr BT z listy urządzeń
- Głośność — była zapisywana ale teraz też last_station_id jest zapisywane przy każdym play
- Ostatnia stacja — przywracana automatycznie przy starcie
- Loudness — prawdziwy endpoint /api/setting, zapisywany w config, przywracany przy starcie
- BT connect — auto-trust przed połączeniem

v0.10.2 changelog:
Bugfix:
- problemy z interface
- czasami apka zailcza crush
- znikające podstrony

v0.10.1 changelog:
- interfejs WWW.
- działa Radio
- uruchomiona obsługa bluetooth
- stabilne 60° na procesorze (optymalna praca)

bug:
- problemy z interface
- czasami apka zailcza crush
- znikające podstrony
