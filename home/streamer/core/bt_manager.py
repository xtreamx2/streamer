#!/usr/bin/env python3
"""
Bluetooth Manager — fasada nad BluetoothSource.
Udostępnia API dla routes.py: scan, pair, connect, disconnect, list.
Obsługuje też auto-connect przy starcie.
"""

import logging
import threading
from typing import Optional, List
from sources.bluetooth import BluetoothSource

log = logging.getLogger(__name__)


class BTManager:
    def __init__(self, bt_source: BluetoothSource):
        self._src = bt_source
        self._scan_thread: Optional[threading.Thread] = None
        self._scanning = False

    def get_paired(self) -> List[dict]:
        return self._src.get_paired_devices()

    def scan_async(self, duration: int = 10, callback=None):
        """Skanuj w tle, wywołaj callback(devices) po zakończeniu."""
        if self._scanning:
            return
        self._scanning = True
        def _do():
            try:
                devices = self._src.scan_devices(duration)
                if callback:
                    callback(devices)
            finally:
                self._scanning = False
        self._scan_thread = threading.Thread(target=_do, daemon=True, name='bt-scan')
        self._scan_thread.start()

    def pair(self, mac: str) -> bool:
        return self._src.pair_device(mac)

    def connect(self, mac: str) -> bool:
        return self._src.connect_device(mac)

    def disconnect(self, mac: str):
        self._src.disconnect_device(mac)

    def remove(self, mac: str):
        self._src.remove_device(mac)

    def set_mode(self, mode: str):
        """'sink' lub 'source'."""
        self._src.set_mode(mode)

    @property
    def scanning(self) -> bool:
        return self._scanning

    @property
    def mode(self) -> str:
        return self._src._mode

    @property
    def connected_device(self) -> Optional[str]:
        return self._src._connected_dev
