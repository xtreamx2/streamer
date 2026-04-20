"""
PylonisAmp — Cover Manager
Pobiera okładki albumów i loga stacji radiowych.

Priorytet:
  1. MusicBrainz Cover Art Archive
  2. iTunes Search API
  3. Last.fm API
  4. Logo stacji radiowej (gdy brak artysty/tytułu)
  5. placeholder (None)

Cache: streamer/covers/{hash}.jpg  (240×240 JPEG)
"""

import os
import hashlib
import logging
import requests
from pathlib import Path
from PIL import Image
from io import BytesIO

log = logging.getLogger('cover_manager')

COVERS_DIR  = Path(__file__).parent.parent / 'covers'
COVER_SIZE  = (240, 240)
JPEG_QUALITY = 95
HTTP_TIMEOUT = 10  # sekundy

COVERS_DIR.mkdir(exist_ok=True)


# ── Główny interfejs ─────────────────────────────────────────────────────────

def get_cover(artist: str, title: str, station_name: str = '') -> str | None:
    """
    Zwróć ścieżkę do pliku okładki (240×240 JPEG).
    Jeśli nie ma w cache — pobierz i zapisz.
    Zwróć None jeśli nie udało się pobrać.
    """
    cover_id = _make_id(artist, title, station_name)
    cache_path = COVERS_DIR / f'{cover_id}.jpg'

    if cache_path.exists():
        log.debug(f'Cover cache hit: {cover_id}')
        return str(cache_path)

    log.info(f'Cover cache miss: {cover_id} — pobieranie...')
    img_url = None

    if artist and title:
        # Szukaj okładki albumu
        img_url = (_try_musicbrainz(artist, title)
                or _try_itunes(artist, title)
                or _try_lastfm(artist, title))
    
    if not img_url and station_name:
        # Brak okładki — spróbuj logo stacji
        img_url = _try_station_logo(station_name)

    if not img_url:
        log.debug(f'Brak okładki dla: {artist} — {title} / {station_name}')
        return None

    return _download_and_cache(img_url, cache_path)

def get_cover_url(artist: str, title: str, station_name: str = '') -> str | None:
    """Zwróć URL do serwowania przez /api/cover — relative path."""
    path = get_cover(artist, title, station_name)
    if not path:
        return None
    return f'/api/cover/{os.path.basename(path)}'


def cover_id_for(artist: str, title: str, station_name: str = '') -> str:
    return _make_id(artist, title, station_name)


# ── Źródła ─────────────────────────────────────────────────────────────────

def _try_musicbrainz(artist: str, title: str) -> str | None:
    """MusicBrainz Cover Art Archive."""
    try:
        # Szukaj nagrania
        url = 'https://musicbrainz.org/ws/2/recording'
        params = {
            'query': f'recording:"{title}" AND artist:"{artist}"',
            'fmt':   'json',
            'limit': 5,
        }
        headers = {'User-Agent': 'PylonisAmp/1.0 (pylonisamp@localhost)'}
        r = requests.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT)
        if r.status_code != 200:
            return None

        data = r.json()
        recordings = data.get('recordings', [])

        for rec in recordings:
            for release in rec.get('releases', []):
                rid = release.get('id')
                if not rid:
                    continue
                # Sprawdź Cover Art Archive
                ca_url = f'https://coverartarchive.org/release/{rid}/front-250'
                try:
                    cr = requests.head(ca_url, timeout=HTTP_TIMEOUT, allow_redirects=True)
                    if cr.status_code == 200:
                        log.debug(f'MusicBrainz cover: {ca_url}')
                        return ca_url
                except Exception:
                    continue
    except Exception as e:
        log.debug(f'MusicBrainz error: {e}')
    return None

def _try_itunes(artist: str, title: str) -> str | None:
    """iTunes Search API."""
    try:
        r = requests.get(
            'https://itunes.apple.com/search',
            params={'term': f'{artist} {title}', 'media': 'music', 'limit': 3},
            timeout=HTTP_TIMEOUT
        )
        if r.status_code != 200:
            return None
        results = r.json().get('results', [])
        for item in results:
            art = item.get('artworkUrl100', '')
            if art:
                # Zamień 100x100 na 240x240
                art = art.replace('100x100', '240x240')
                log.debug(f'iTunes cover: {art}')
                return art
    except Exception as e:
        log.debug(f'iTunes error: {e}')
    return None

def _try_lastfm(artist: str, title: str) -> str | None:
    """Last.fm API (bez klucza — public endpoint)."""
    try:
        r = requests.get(
            'https://ws.audioscrobbler.com/2.0/',
            params={
                'method':  'track.getInfo',
                'artist':  artist,
                'track':   title,
                'api_key': 'LASTFM_API_KEY_PLACEHOLDER',
                'format':  'json',
            },
            timeout=HTTP_TIMEOUT
        )
        if r.status_code != 200:
            return None
        data = r.json()
        images = data.get('track', {}).get('album', {}).get('image', [])
        # Wybierz największy rozmiar
        for img in reversed(images):
            url = img.get('#text', '')
            if url and 'noimage' not in url:
                log.debug(f'Last.fm cover: {url}')
                return url
    except Exception as e:
        log.debug(f'Last.fm error: {e}')
    return None

def _try_station_logo(station_name: str) -> str | None:
    """
    Pobierz logo stacji radiowej.
    Używa RadioBrowser API — darmowe, bez klucza.
    """
    try:
        r = requests.get(
            'https://de1.api.radio-browser.info/json/stations/byname/' + 
            requests.utils.quote(station_name),
            params={'limit': 3},
            headers={'User-Agent': 'PylonisAmp/1.0'},
            timeout=HTTP_TIMEOUT
        )
        if r.status_code != 200:
            return None
        stations = r.json()
        for station in stations:
            favicon = station.get('favicon', '')
            if favicon and favicon.startswith('http'):
                log.debug(f'Station logo: {favicon}')
                return favicon
    except Exception as e:
        log.debug(f'Station logo error: {e}')
    return None


# ── Cache helpers ───────────────────────────────────────────────────────────

def _make_id(artist: str, title: str, station: str) -> str:
    """Generuj unikalny ID dla kombinacji artysta+tytuł lub stacja."""
    key = f'{artist.lower()}|{title.lower()}|{station.lower()}'
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _download_and_cache(url: str, path: Path) -> str | None:
    """Pobierz obraz, przeskaluj do 240×240, zapisz jako JPEG."""
    try:
        r = requests.get(url, timeout=HTTP_TIMEOUT, stream=True)
        if r.status_code != 200:
            return None

        img = Image.open(BytesIO(r.content)).convert('RGB')
        img = img.resize(COVER_SIZE, Image.LANCZOS)
        img.save(str(path), 'JPEG', quality=JPEG_QUALITY)
        log.info(f'Cover saved: {path.name}')

        return str(path)
    except Exception as e:
        log.warning(f'Cover download error ({url}): {e}')
        return None


def cleanup_cache(max_mb: int = 500):
    """Usuń najstarsze okładki gdy cache przekracza max_mb MB."""
    files = sorted(COVERS_DIR.glob('*.jpg'), key=lambda f: f.stat().st_mtime)
    total = sum(f.stat().st_size for f in files)
    limit = max_mb * 1024 * 1024
    while total > limit and files:
        f = files.pop(0)
        total -= f.stat().st_size
        f.unlink()
        log.info(f'Cover cache evicted: {f.name}')
