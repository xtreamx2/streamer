import re
#!/usr/bin/env python3
"""
Źródło: Radio internetowe (GStreamer souphttpsrc + decodebin + EQ + alsasink).
v0.10.3.10 — naprawiony stop/start pipeline (race condition przy przełączaniu).
"""

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GLib

import threading
import logging
import time
from typing import Optional
from .base import AudioSource

Gst.init(None)
log = logging.getLogger(__name__)

EQ_BANDS      = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000]
EQ_BAND_NAMES = ['60Hz','170Hz','310Hz','600Hz','1kHz','3kHz','6kHz','12kHz','14kHz','16kHz']
FLAT_PRESET   = [0.0] * 10


def _log_bands(gst_vals: list, n_out: int = 32,
               f_min: float = 20.0, f_max: float = 20000.0,
               sample_rate: int = 44100) -> list:
    """Mapuj liniowe pasma GStreamer na n_out pasm logarytmicznych 20-20000 Hz."""
    import math
    n_in = len(gst_vals)
    hz_per_band = (sample_rate / 2.0) / n_in
    result = []
    for i in range(n_out):
        f_lo = f_min * (f_max / f_min) ** (i / n_out)
        f_hi = f_min * (f_max / f_min) ** ((i + 1) / n_out)
        idx_lo = max(0, int(f_lo / hz_per_band))
        idx_hi = min(n_in - 1, int(f_hi / hz_per_band))
        if idx_lo == idx_hi:
            val = gst_vals[idx_lo]
        else:
            # Maksimum z zakresu (bardziej czytelne niż średnia)
            val = max(gst_vals[idx_lo:idx_hi + 1])
        result.append(max(-60.0, min(0.0, val)))
    return result


class RadioSource(AudioSource):
    SOURCE_ID   = 'radio'
    SOURCE_NAME = 'Internet Radio'
    AVAILABLE   = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_url        = ''
        self._current_title      = ''
        self._station_name       = ''
        self._artist             = ''
        self._stream_codec       = ''
        self._stream_bitrate_kbps = None
        self._stream_rate        = None
        self._stream_channels    = None
        self._stream_bit_depth   = None
        self._decoder_caps       = ''
        self._volume             = 75
        self._eq_gains           = FLAT_PRESET[:]
        self._pipeline: Optional[Gst.Pipeline] = None
        self._eq_el:    Optional[Gst.Element]  = None
        self._vol_el:   Optional[Gst.Element]  = None
        self._reconnect_url      = ''
        self._lock               = threading.Lock()
        self._play_pending       = None   # URL do zagrania po zatrzymaniu
        self._level_rms          = (0.0, 0.0)   # (L, R) RMS dB, aktualizowane przez GStreamer
        self._level_peak         = (0.0, 0.0)
        self._spectrum_bands     = [-60.0] * 32   # 32 pasma LOG 20-20000 Hz
        self._direct             = False            # bypass EQ+loudness
        self._pregain            = 0.0              # gain per source w dB
        self._on_clip            = None             # callback przy CLIP

        # GLib MainLoop w osobnym wątku — wymagany przez GStreamer bus callbacks
        self._loop = GLib.MainLoop()
        threading.Thread(target=self._loop.run, daemon=True, name='gst-loop').start()

    # ── AudioSource interface ──────────────────────────────────

    def activate(self) -> bool:
        self._active = True
        self._set_state('idle')
        return True

    def deactivate(self):
        self._active = False
        self._reconnect_url = ''
        self._play_pending  = None
        self._stop_pipeline()
        self._set_state('stopped')

    def get_status(self) -> dict:
        return {
            'source':      self.SOURCE_ID,
            'state':       self._state,
            'url':         self._current_url,
            'title':       self._current_title,
            'artist':      self._artist,
            'station':     self._station_name,
            'volume':      self._volume,
            'eq':          self._eq_gains[:],
            'eq_bands':    EQ_BAND_NAMES,
            'stream': {
                'codec':         self._stream_codec,
                'bitrate_kbps':  self._stream_bitrate_kbps,
                'bit_depth':     self._stream_bit_depth,
                'sample_rate':   self._stream_rate,
                'channels':      self._stream_channels,
                'decoder_caps':  self._decoder_caps,
            },
        }

    # ── Public API ─────────────────────────────────────────────

    def play(self, url: str, station_name: str = ''):
        log.info(f"Radio play: {url}")
        self._station_name  = station_name
        self._current_title = ''
        self._stream_codec  = ''
        self._stream_bitrate_kbps = None
        self._reconnect_url = url
        self._stop_pipeline()
        # Krótka przerwa żeby ALSA zdążyła zwolnić urządzenie
        time.sleep(0.3)
        self._start_pipeline(url)

    def stop(self):
        log.info("Radio stop")
        self._reconnect_url = ''
        self._play_pending  = None
        self._stop_pipeline()
        self._set_state('stopped')

    def set_volume(self, vol: int):
        self._volume = max(0, min(100, vol))
        if self._vol_el:
            self._vol_el.set_property('volume', self._volume / 100.0)

    def get_spectrum(self) -> list:
        """Zwróć 32 pasma FFT w dB [-60..0]."""
        return [round(v, 1) for v in self._spectrum_bands]

    def get_level(self) -> dict:
        """Zwróć aktualny poziom audio (RMS + peak) w dB. -60 = cisza."""
        return {
            'rms_l':  round(self._level_rms[0],  1),
            'rms_r':  round(self._level_rms[1],  1),
            'peak_l': round(self._level_peak[0], 1),
            'peak_r': round(self._level_peak[1], 1),
        }

    def set_eq_gains(self, gains: list):
        if len(gains) == 10:
            self._eq_gains = [max(-24.0, min(12.0, g)) for g in gains]
            self._apply_eq()

    # ── Pipeline ───────────────────────────────────────────────

    def _build_pipeline(self, url: str) -> Gst.Pipeline:
        pipe = Gst.Pipeline.new('radio')

        src      = Gst.ElementFactory.make('souphttpsrc',       'src')
        decode   = Gst.ElementFactory.make('decodebin',         'decode')
        convert  = Gst.ElementFactory.make('audioconvert',      'convert')
        resample = Gst.ElementFactory.make('audioresample',     'resample')
        level    = Gst.ElementFactory.make('level',             'level')
        spectrum = Gst.ElementFactory.make('spectrum',          'spectrum')
        eq       = Gst.ElementFactory.make('equalizer-10bands', 'eq')
        vol      = Gst.ElementFactory.make('volume',            'volume')
        sink     = Gst.ElementFactory.make('alsasink',          'sink')

        if not all([src, decode, convert, resample, level, eq, vol, sink]):
            raise RuntimeError("GStreamer: brakujące elementy pipeline")

        # level: przed EQ/vol — mierzy surowy sygnał wejściowy
        level.set_property('interval',      40_000_000)   # 40ms
        level.set_property('peak-ttl',               0)   # brak hold w GStreamer — JS robi własny peak hold
        level.set_property('post-messages', True)

        if spectrum:
            spectrum.set_property('bands',           512)  # wysoka rozdzielczość → mapowanie log w Python
            spectrum.set_property('interval',   40_000_000)
            spectrum.set_property('threshold',        -60)
            spectrum.set_property('post-messages',   True)
            spectrum.set_property('message-magnitude', True)
            spectrum.set_property('message-phase',    False)

        src.set_property('location',    url)
        src.set_property('user-agent',  "Mozilla/5.0 StreamPlayer/3.0")
        src.set_property('timeout',     15)
        src.set_property('retries',     3)
        src.set_property('iradio-mode', True)

        sink.set_property('device', self.alsa_device)
        resample.set_property('quality', 10)

        # Pipeline: src → decode → convert → resample → level → [spectrum →] eq → vol → sink
        elements = [src, decode, convert, resample, level, eq, vol, sink]
        if spectrum:
            elements.insert(elements.index(eq), spectrum)
        for el in elements:
            pipe.add(el)

        src.link(decode)
        convert.link(resample)
        resample.link(level)
        if spectrum:
            level.link(spectrum)
            spectrum.link(eq)
        else:
            level.link(eq)
        eq.link(vol)
        vol.link(sink)

        decode.connect('pad-added', self._on_pad_added, convert)

        self._eq_el  = eq
        self._vol_el = vol
        self._apply_eq()
        self._apply_volume()
        self._level_rms     = (0.0, 0.0)
        self._level_peak    = (0.0, 0.0)
        self._spectrum_bands = [-60.0] * 32

        bus = pipe.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self._on_bus_message)

        return pipe

    def _on_pad_added(self, decode, pad, convert):
        caps = pad.get_current_caps()
        if caps:
            s = caps.get_structure(0)
            name = s.get_name()
            if name.startswith('audio/'):
                try:
                    if s.has_field('rate'):
                        self._stream_rate = int(s.get_value('rate'))
                    if s.has_field('channels'):
                        self._stream_channels = int(s.get_value('channels'))
                    # bit depth z formatu np. audio/x-raw,format=S16LE
                    if s.has_field('format'):
                        fmt = str(s.get_value('format'))
                        m = __import__('re').search(r'S(\d+)', fmt)
                        if m:
                            self._stream_bit_depth = int(m.group(1))
                    self._decoder_caps = name
                except Exception:
                    pass
                sink_pad = convert.get_static_pad('sink')
                if not sink_pad.is_linked():
                    pad.link(sink_pad)
                    log.info(f"Decoder: {name}")

    def _on_bus_message(self, bus, msg):
        t = msg.type
        if t == Gst.MessageType.EOS:
            log.info("EOS — reconnect")
            self._schedule_reconnect()

        elif t == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            log.warning(f"GST error: {err.message}")
            self._set_state('buffering')
            self._schedule_reconnect()

        elif t == Gst.MessageType.STATE_CHANGED:
            if msg.src == self._pipeline:
                _, new, _ = msg.parse_state_changed()
                if new == Gst.State.PLAYING:
                    self._set_state('playing')
                elif new == Gst.State.PAUSED:
                    if self._state not in ('buffering',):
                        self._set_state('paused')

        elif t == Gst.MessageType.TAG:
            tags = msg.parse_tag()
            artist = None
            title  = None
            ok_a, v_a = tags.get_string('artist')
            ok_t, v_t = tags.get_string('title')
            if ok_a and v_a and v_a.strip():
                artist = v_a.strip()
            if ok_t and v_t and v_t.strip():
                title = v_t.strip()

            if artist or title:
                display = ''
                if artist:
                    display = artist
                if title:
                    display = f"{display} — {title}" if display else title
                if display and display != self._current_title:
                    self._artist = artist or ''
                    self._current_title = display
                    log.info(f"Title: {display}")
                    self._set_meta({
                        'title':   display,
                        'artist':  self._artist,
                        'station': self._station_name,
                    })

            ok_c, v_c = tags.get_string('audio-codec')
            if ok_c and v_c and v_c.strip():
                self._stream_codec = v_c.strip()

            # Próbuj różnych tagów bitrate (FLAC używa nominal-bitrate lub maximum-bitrate)
            bitrate_raw = None
            for tag_name in ('bitrate', 'nominal-bitrate', 'maximum-bitrate', 'minimum-bitrate'):
                try:
                    ok_br, v_br = tags.get_uint(tag_name)
                    if ok_br and v_br and v_br > 1000:
                        bitrate_raw = v_br
                        break
                except Exception:
                    pass
            if bitrate_raw:
                self._stream_bitrate_kbps = max(1, int(bitrate_raw // 1000))

        elif t == Gst.MessageType.ELEMENT:
            s = msg.get_structure()
            if s and s.get_name() == 'spectrum':
                try:
                    raw = s.to_string()
                    import re as _re
                    m = _re.search(r'magnitude=[(]float[)][{]([^}]+)[}]', raw)
                    if m:
                        vals = [float(x.strip()) for x in m.group(1).split(',') if x.strip()]
                        if len(vals) >= 32:
                            self._spectrum_bands = _log_bands(vals)
                        else:
                            self._spectrum_bands = [max(-60.0, min(0.0, v)) for v in vals[:32]]
                except Exception:
                    pass
            elif s and s.get_name() == 'level':
                # Sprawdz CLIP (peak >= 0dBFS)
                try:
                    peak = s.get_value('peak')
                    if peak and any(float(p) >= -0.1 for p in peak):
                        if self._on_clip:
                            self._on_clip(self.SOURCE_ID)
                except Exception:
                    pass
                try:
                    rms  = s.get_value('rms')
                    peak = s.get_value('peak')
                    rms_l  = float(rms[0])  if len(rms)  > 0 else -60.0
                    rms_r  = float(rms[1])  if len(rms)  > 1 else rms_l
                    peak_l = float(peak[0]) if len(peak) > 0 else -60.0
                    peak_r = float(peak[1]) if len(peak) > 1 else peak_l
                    self._level_rms  = (max(-60.0, rms_l),  max(-60.0, rms_r))
                    self._level_peak = (max(-60.0, peak_l), max(-60.0, peak_r))
                except Exception:
                    pass

        elif t == Gst.MessageType.BUFFERING:
            pct = msg.parse_buffering()
            if pct < 100:
                self._set_state('buffering')
                if self._pipeline:
                    self._pipeline.set_state(Gst.State.PAUSED)
            else:
                self._set_state('playing')
                if self._pipeline:
                    self._pipeline.set_state(Gst.State.PLAYING)

    def _schedule_reconnect(self):
        url = self._reconnect_url
        if url:
            GLib.timeout_add(500, self._do_reconnect, url)

    def _do_reconnect(self, url: str) -> bool:
        if self._reconnect_url != url:
            return False  # URL zmieniony — porzuć ten reconnect
        log.info(f"Reconnect: {url}")
        self._stop_pipeline()
        time.sleep(0.3)
        if self._reconnect_url == url:  # Sprawdź ponownie po sleep
            self._start_pipeline(url)
        return False

    def _start_pipeline(self, url: str):
        self._current_url = url
        try:
            self._pipeline = self._build_pipeline(url)
            ret = self._pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                log.error("Pipeline: nie można uruchomić")
                self._set_state('error')
            else:
                self._set_state('buffering')
        except Exception as e:
            log.error(f"Pipeline build error: {e}")
            self._set_state('error')

    def _stop_pipeline(self):
        with self._lock:
            if self._pipeline:
                p = self._pipeline
                self._pipeline = None
                self._eq_el    = None
                self._vol_el   = None
                # Ustaw NULL i poczekaj na potwierdzenie
                p.set_state(Gst.State.NULL)
                p.get_state(timeout=Gst.SECOND * 2)  # czekaj max 2s

    def set_pregain(self, gain_db: float):
        """Ustaw pre-gain (wzmocnienie/tlumienie przed EQ) w dB."""
        self._pregain = max(-10.0, min(6.0, float(gain_db)))
        if self._vol_el:
            # Skaluj volume przez pregain: vol_linear * 10^(gain_db/20)
            import math
            factor = 10 ** (self._pregain / 20.0)
            base_vol = self._volume / 100.0
            self._vol_el.set_property('volume', min(1.0, base_vol * factor))

    def _apply_volume(self):
        import math
        if self._vol_el:
            factor = 10 ** (self._pregain / 20.0)
            self._vol_el.set_property('volume', min(1.0, (self._volume / 100.0) * factor))

    def set_direct(self, enabled: bool):
        """Tryb Direct: bypass EQ (flat) i ignoruj loudness."""
        self._direct = enabled
        self._apply_eq()

    def _apply_eq(self):
        if self._eq_el:
            if self._direct:
                # Bypass — wszystkie pasma na 0
                for i in range(10):
                    self._eq_el.set_property(f'band{i}', 0.0)
            else:
                for i, gain in enumerate(self._eq_gains):
                    self._eq_el.set_property(f'band{i}', float(gain))

    def _apply_volume(self):
        if self._vol_el:
            self._vol_el.set_property('volume', self._volume / 100.0)
