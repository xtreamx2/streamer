#!/usr/bin/env python3
import numpy as np
import time
import random
import math
import os
import subprocess
from typing import Tuple, Optional

class VUMeter:
    """VU Meter with attack/decay + peak hold + interpolation"""
    
    def __init__(self, bands=32, attack_ms=50, decay_ms=200, peak_hold_s=1.5):
        self.bands = bands
        self.attack_coef = np.exp(-1/(attack_ms/1000 * 20))
        self.decay_coef = np.exp(-1/(decay_ms/1000 * 20))
        self.peak_decay = 1/(peak_hold_s * 20)
        self.levels = np.zeros(bands)
        self.peaks = np.zeros(bands)
        self.peak_timers = np.zeros(bands)
    
    def update(self, amplitudes):
        """Update VU levels with attack/decay + peak hold"""
        amplitudes = np.clip(amplitudes, -60, 0)
        for i in range(self.bands):
            # Attack/decay
            if amplitudes[i] > self.levels[i]:
                self.levels[i] = self.levels[i] * self.attack_coef + amplitudes[i] * (1 - self.attack_coef)
            else:
                self.levels[i] = self.levels[i] * self.decay_coef + amplitudes[i] * (1 - self.decay_coef)
            # Peak hold
            if amplitudes[i] > self.peaks[i]:
                self.peaks[i] = amplitudes[i]
                self.peak_timers[i] = 0
            else:
                self.peak_timers[i] += 1/20
                if self.peak_timers[i] >= 1.5:
                    self.peaks[i] = max(self.peaks[i] - 0.5, self.levels[i])
        return self.levels.copy(), self.peaks.copy()
    
    def interpolate_to_64(self, levels_32):
        """32 bands → 64 bands (linear interpolation)"""
        result = []
        for i in range(len(levels_32)):
            result.append(levels_32[i])
            if i < len(levels_32) - 1:
                result.append((levels_32[i] + levels_32[i+1]) / 2)
        return np.array(result)

# Global instance
vu_meter = VUMeter(bands=32)

def _dbfs_from_pcm16(x: np.ndarray) -> float:
    # x: int16 samples
    x = x.astype(np.float32) / 32768.0
    rms = np.sqrt(np.mean(np.square(x)) + 1e-12)
    db = 20.0 * np.log10(rms + 1e-12)
    return float(np.clip(db, -60.0, 0.0))

def _read_arecord_chunk(
    device: str,
    rate: int,
    channels: int,
    seconds: float,
) -> Optional[np.ndarray]:
    """Reads raw PCM16 from arecord and returns int16 array shaped (n, channels).

    Returns None if arecord is not available or fails.
    """
    frames = max(256, int(rate * seconds))
    bytes_to_read = frames * channels * 2
    cmd = [
        "arecord",
        "-D", device,
        "-q",
        "-f", "S16_LE",
        "-r", str(rate),
        "-c", str(channels),
        "-t", "raw",
        "-d", str(max(1, int(np.ceil(seconds)))),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, check=False)
        if proc.returncode != 0 or not proc.stdout:
            return None
        raw = proc.stdout[-bytes_to_read:]
        if len(raw) < channels * 2:
            return None
        data = np.frombuffer(raw, dtype=np.int16)
        if data.size < channels:
            return None
        data = data[: (data.size // channels) * channels]
        return data.reshape(-1, channels)
    except FileNotFoundError:
        return None
    except Exception:
        return None

def _spectrum_32_from_pcm(
    pcm: np.ndarray,
    rate: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute 32 log-spaced bands for L/R in dBFS-ish range [-60..0]."""
    if pcm.ndim != 2 or pcm.shape[1] < 2:
        x = pcm[:, 0] if pcm.ndim == 2 else pcm
        l = x
        r = x
    else:
        l = pcm[:, 0]
        r = pcm[:, 1]

    def _bands(x):
        xf = x.astype(np.float32) / 32768.0
        n = int(2 ** np.ceil(np.log2(max(1024, xf.size))))
        win = np.hanning(min(xf.size, n))
        xs = xf[: win.size] * win
        spec = np.fft.rfft(xs, n=n)
        mag = np.abs(spec) + 1e-12
        freqs = np.fft.rfftfreq(n, d=1.0 / rate)

        fmin, fmax = 20.0, min(20000.0, rate / 2.0 - 1.0)
        edges = np.logspace(np.log10(fmin), np.log10(max(fmin * 1.1, fmax)), num=33)
        out = np.empty(32, dtype=np.float32)
        for i in range(32):
            lo, hi = edges[i], edges[i + 1]
            mask = (freqs >= lo) & (freqs < hi)
            if not np.any(mask):
                out[i] = -60.0
            else:
                v = np.mean(mag[mask])
                # Normalize roughly to dbfs scale
                db = 20.0 * np.log10(v + 1e-12)
                out[i] = np.clip(db, -60.0, 0.0)
        return out

    return _bands(l), _bands(r)

def get_vu_data(mode='vu'):
    """VU/Spectrum.

    - If ALSA/arecord is available (typowo Raspberry Pi), czyta próbki z loopback
      i liczy prawdziwy RMS/FFT.
    - Jeśli nie (np. Windows dev), wraca do symulacji, ale zachowuje tryb.
    """
    mode = mode if mode in ("vu", "spectrum") else "vu"

    device = os.environ.get("VU_ARECORD_DEVICE", "hw:Loopback,1,0")
    rate = int(os.environ.get("VU_RATE", "48000"))
    channels = 2
    seconds = float(os.environ.get("VU_CHUNK_S", "0.08"))

    pcm = _read_arecord_chunk(device=device, rate=rate, channels=channels, seconds=seconds)

    if pcm is None:
        # Fallback: simulated (deterministic-ish) but mode-aware
        t = time.time()
        amplitudes = []
        for i in range(32):
            freq = 20 * (2 ** (i / 32 * 10))
            if freq < 200:
                base = random.uniform(-22, -8)
            elif freq < 2000:
                base = random.uniform(-38, -18)
            else:
                base = random.uniform(-50, -28)
            modulation = 3 * math.sin(t * 2 + i * 0.3)
            amplitudes.append(base + modulation)
        amplitudes = np.array(amplitudes, dtype=np.float32)

        if mode == "vu":
            levels, peaks = vu_meter.update(amplitudes)
        else:
            levels = amplitudes
            peaks = amplitudes

        return {
            "vu_l": levels.tolist(),
            "vu_r": levels.tolist(),
            "peak_l": peaks.tolist(),
            "peak_r": peaks.tolist(),
            "timestamp": time.time(),
            "source": "simulated",
        }

    if mode == "vu":
        l_db = _dbfs_from_pcm16(pcm[:, 0])
        r_db = _dbfs_from_pcm16(pcm[:, 1])
        # Fill 32 bands with same VU level (classic VU), smoothing handled by vu_meter
        amplitudes = np.array([max(l_db, r_db)] * 32, dtype=np.float32)
        levels, peaks = vu_meter.update(amplitudes)
        # Split L/R as identical for now (VU, not spectrum)
        return {
            "vu_l": levels.tolist(),
            "vu_r": levels.tolist(),
            "peak_l": peaks.tolist(),
            "peak_r": peaks.tolist(),
            "timestamp": time.time(),
            "source": f"arecord:{device}",
        }

    # Spectrum
    l32, r32 = _spectrum_32_from_pcm(pcm, rate=rate)
    return {
        "vu_l": l32.tolist(),
        "vu_r": r32.tolist(),
        "peak_l": l32.tolist(),
        "peak_r": r32.tolist(),
        "timestamp": time.time(),
        "source": f"arecord:{device}",
    }
