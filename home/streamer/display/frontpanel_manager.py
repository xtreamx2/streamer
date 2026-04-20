#!/usr/bin/env python3
"""
USB Manager — komunikacja JSON z panelem RP2040.
Wersja: v0.2.20 (RAW RGB565 + UTF-8)
"""

import serial
import json
import threading
import time
import logging
import re
import os
import struct
import qoi
from PIL import Image
from modules.cover_manager import get_cover

log = logging.getLogger(__name__)

def safe_text(text):
    if not text: return ""
    return str(text).strip()

class FrontpanelManager:
    def __init__(self, source_manager, port='/dev/ttyACM0', baud=1000000):
        self.port = port
        self.baud = baud
        self.sm = source_manager
        self.serial = None
        self.running = False
        self.last_cover_path = None
        self.viz_modes = ['spectrum', 'uv', 'none']
        self.current_viz_mode_idx = 0
        self.last_reconnect_attempt = 0
        self._lock = threading.Lock()

    def start(self):
        self.running = True
        # Wątek do odbierania zdarzeń (np. dotyk) - musi działać niezależnie od wysyłania
        threading.Thread(target=self._read_loop, daemon=True, name="FP-Read").start()
        # Wątek do cyklicznego wysyłania widma
        threading.Thread(target=self._send_loop, daemon=True, name="FP-Spectrum").start()
        log.info(f"FrontpanelManager uruchomiony na port USB: {self.port} (Baud: {self.baud})")

    def stop(self):
        self.running = False
        if self.serial:
            self.serial.close()

    def _read_loop(self):
        while self.running:
            try:
                if not self.serial or not self.serial.is_open:
                    now = time.time()
                    if now - self.last_reconnect_attempt < 10:
                        time.sleep(1)
                        continue
                    self.last_reconnect_attempt = now
                    try:
                        self.serial = serial.Serial(self.port, self.baud, timeout=0, write_timeout=0)
                        log.info(f"Połączono z ekranem Pico na {self.port}!")
                        self.send_current_state()
                    except Exception:
                        self.serial = None
                        continue
                line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    self._handle_incoming(line)
            except Exception as e:
                log.error(f"Błąd USB Pico: {e}")
                self.serial = None
                time.sleep(2)

    def _send_loop(self):
        """Pętla wysyłająca dane widma (ograniczona do ~30 FPS dla oszczędności CPU)."""
        while self.running:
            start_time = time.time()
            if self.sm and self.sm.active_source and hasattr(self.sm.active_source, 'get_spectrum'):
                try:
                    spectrum = self.sm.active_source.get_spectrum()
                    if spectrum:
                        self.send_meters(spectrum)
                except Exception: pass
            
            # Limit do ~30 FPS (1/30 = 0.033s)
            elapsed = time.time() - start_time
            wait = 0.033 - elapsed
            if wait > 0:
                time.sleep(wait)

    def _handle_incoming(self, line):
        try:
            data = json.loads(line)
            evt = data.get('evt')
            if evt == 'ready':
                self.send_current_state()
                if self.last_cover_path and os.path.exists(self.last_cover_path):
                    self.send_cover_to_pico(self.last_cover_path)
            elif evt == 'touch':
                # Przełącz tryb wizualizacji po dotknięciu ekranu
                self.current_viz_mode_idx = (self.current_viz_mode_idx + 1) % len(self.viz_modes)
                log.info(f"Touch event: zmiana trybu viz na {self.viz_modes[self.current_viz_mode_idx]}")
                self.send_current_state()
        except Exception as e:
            log.error(f"Błąd podczas obsługi danych przychodzących: {e}")

    def send_current_state(self):
        if not self.sm: return
        active_src = self.sm.active_source
        status = active_src.get_status() if active_src else {}
        
        artist = safe_text(status.get('artist', ''))
        title = safe_text(status.get('title', ''))

        # Usuń powtórzony tekst artysty z tytułu, jeśli występuje (np. "Artysta - Tytuł")
        if artist and title.lower().startswith(artist.lower()):
            # Szukamy separatora po imieniu artysty
            cleaned_title = title[len(artist):].strip()
            if cleaned_title.startswith('-') or cleaned_title.startswith(':'):
                title = cleaned_title[1:].strip()
            elif not cleaned_title:
                title = artist # Jeśli tytuł był identyczny z artystą
            else:
                title = cleaned_title

        msg = {
            "cmd": "state",
            "station": safe_text(status.get('station', 'RADIO')),
            "volume": self.sm.get_volume(),
            "title": title,
            "artist": artist,
            "time": status.get('time', '00:00'),
            "mode": self.viz_modes[self.current_viz_mode_idx]
        }
        self._send(msg)

    def send_cover_to_pico(self, path):
        """Wysyła okładkę w osobnym wątku, aby nie blokować pętli głównej."""
        if not self.serial or not self.serial.is_open: return
        self.last_cover_path = path
        threading.Thread(target=self._do_send_cover, args=(path,), daemon=True).start()

    def _do_send_cover(self, path):
        try:
            log.debug(f"Rozpoczęto kompresję QOI obrazu: {path}")
            img = Image.open(path).convert('RGBA')
            # Bilinear jest szybszy od Lanczos na RPi3
            img = img.resize((240, 240), Image.Resampling.BILINEAR)
            
            import numpy as np
            pixel_data = np.array(img)
            qoi_data = qoi.encode(pixel_data)

            with self._lock:
                log.info(f"Wysyłam QOI: {len(qoi_data)} bajtów")
                self._send_locked({"cmd": "img_qoi", "size": len(qoi_data)})
                
                chunk_size = 4096
                for i in range(0, len(qoi_data), chunk_size):
                    if not self.serial or not self.serial.is_open: return
                    try:
                        if self.serial.out_waiting > 2048:
                            log.critical("Buffer overflow! Resetting.")
                            self.serial.reset_output_buffer()
                            break
                        
                        chunk = qoi_data[i:i+chunk_size]
                        self.serial.write(chunk)
                        self.serial.flush()
                        time.sleep(0.0005)
                    except (serial.SerialException, OSError) as e:
                        log.error(f"Serial error: {e}")
                        self.serial = None
                        return
                
                self._send_locked({"cmd": "img_end"})
            log.debug("Transfer obrazu zakończony.")

        except Exception as e:
            log.error(f"Błąd przetwarzania okładki: {e}")

    def send_meters(self, data: list):
        self._send({"cmd": "meters", "data": data})

    def _send(self, msg_dict):
        with self._lock:
            self._send_locked(msg_dict)

    def _send_locked(self, msg_dict):
        # FUTURE v0.3 - ENCODER & MENU
        if not self.serial or not self.serial.is_open:
            return

        try:
            if self.serial.out_waiting > 2048:
                log.critical(f"Buffer overflow in _send_locked: {self.serial.out_waiting}. Resetting.")
                self.serial.reset_output_buffer()
                return

            # ensure_ascii=False dla poprawnej obsługi UTF-8
            payload = json.dumps(msg_dict, ensure_ascii=False).encode('utf-8') + b'\n'
            log.debug(f"Serial write: {payload[:50]}...")
            self.serial.write(payload)
            self.serial.flush()
        except (serial.SerialException, OSError) as e:
            log.warning(f"Połączenie utracone (Pico) podczas wysyłania JSON: {e}")
            try:
                self.serial.close()
            except:
                pass
            self.serial = None
        except Exception as e:
            log.error(f"Błąd wysyłania JSON: {e}")
