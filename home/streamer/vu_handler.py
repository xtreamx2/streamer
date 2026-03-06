#!/usr/bin/env python3
import numpy as np
import time
import random
import math

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

def get_vu_data(mode='vu'):
    """Generate VU or Spectrum data (simulated)"""
    import random, math, time
    t = time.time()
    
    # Generuj dane (na start – losowe, później prawdziwe z audio)
    amplitudes = []
    for i in range(32):
        freq = 20 * (2 ** (i/32 * 10))
        if freq < 200:
            base = random.uniform(-20, -5)
        elif freq < 2000:
            base = random.uniform(-35, -15)
        else:
            base = random.uniform(-45, -25)
        modulation = 3 * math.sin(t * 2 + i * 0.3)
        amplitudes.append(base + modulation)
    
    amplitudes = np.array(amplitudes)
    
    if mode == 'vu':
        levels, peaks = vu_meter.update(amplitudes)
    else:
        # Spectrum: instant, bez smoothing
        levels = amplitudes
        peaks = amplitudes
    
    levels_64 = vu_meter.interpolate_to_64(levels)
    peaks_64 = vu_meter.interpolate_to_64(peaks)
    
    return {
        "vu_l": levels_64[:32].tolist(),
        "vu_r": levels_64[32:].tolist(),
        "peak_l": peaks_64[:32].tolist(),
        "peak_r": peaks_64[32:].tolist(),
        "timestamp": time.time()
    }
