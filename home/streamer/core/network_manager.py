#!/usr/bin/env python3
"""
Network Manager — WiFi przez nmcli (NetworkManager).
Scan, connect, status, aktualne IP.
"""

import subprocess
import logging
import re
from typing import List, Optional

log = logging.getLogger(__name__)


def _run(cmd: list, timeout: int = 15) -> tuple:
    """Uruchom polecenie, zwróć (stdout, stderr, returncode)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return '', 'timeout', -1
    except FileNotFoundError:
        return '', 'nmcli not found', -1


class NetworkManager:

    def get_status(self) -> dict:
        """Zwróć status połączenia sieciowego (WiFi lub Ethernet)."""
        # Aktywne połączenia
        stdout, _, rc = _run(['nmcli', '-t', '-f',
                              'DEVICE,TYPE,STATE,CONNECTION',
                              'device'])
        result = {
            'connected': False,
            'ssid':      '',
            'ip':        '',
            'signal':    None,
            'interface': '',
        }
        if rc != 0:
            return result

        # Szukaj najpierw WiFi, potem Ethernet
        wifi_line = None
        eth_line  = None
        for line in stdout.splitlines():
            parts = line.split(':')
            if len(parts) < 3:
                continue
            device   = parts[0]
            dev_type = parts[1]
            state    = parts[2]
            if 'connected' not in state.lower():
                continue
            if dev_type not in ('wifi', 'ethernet'):
                continue
            if dev_type == 'wifi' and wifi_line is None:
                wifi_line = [device, dev_type, state] + parts[3:]
            elif dev_type == 'ethernet' and eth_line is None:
                eth_line = [device, dev_type, state] + parts[3:]

        chosen = wifi_line or eth_line
        if chosen:
            dev_type = chosen[1]
            result['connected']  = True
            result['interface'] = chosen[0]
            result['ssid']      = chosen[3] if len(chosen) > 3 and dev_type == 'wifi' else ''
            result['ip']        = self._get_ip(chosen[0])
            result['signal']    = self._get_signal(chosen[0]) if dev_type == 'wifi' else None
        else:
            # Fallback gdy nmcli nie parsuje — sprawdź bezpośrednio IP
            ip = self._get_ip('eth0')
            if not ip:
                ip = self._get_ip('wlan0')
            if ip:
                result['connected']  = True
                result['ip']         = ip
                result['interface']  = self._get_interface()

        return result

    def scan(self) -> List[dict]:
        """Skanuj dostępne sieci WiFi."""
        # Odśwież listę
        _run(['nmcli', 'device', 'wifi', 'rescan'], timeout=5)

        stdout, _, rc = _run(['nmcli', '-t', '-f',
                              'SSID,SIGNAL,SECURITY,IN-USE',
                              'device', 'wifi', 'list'])
        networks = []
        seen = set()
        if rc != 0:
            return networks

        for line in stdout.splitlines():
            parts = line.split(':')
            if len(parts) < 4:
                continue
            ssid     = parts[0]
            signal   = self._safe_int(parts[1], 0)
            security = parts[2]
            in_use   = parts[3] == '*'

            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            networks.append({
                'ssid':     ssid,
                'signal':   signal,
                'security': security or 'Open',
                'in_use':   in_use,
            })

        # Sortuj: aktywne pierwsze, potem po sile sygnału
        networks.sort(key=lambda n: (not n['in_use'], -n['signal']))
        return networks

    def connect(self, ssid: str, password: str = '') -> dict:
        """Połącz z siecią WiFi."""
        if password:
            cmd = ['nmcli', 'device', 'wifi', 'connect', ssid,
                   'password', password]
        else:
            cmd = ['nmcli', 'device', 'wifi', 'connect', ssid]

        stdout, stderr, rc = _run(cmd, timeout=30)
        if rc == 0:
            return {'status': 'connected', 'ssid': ssid}
        else:
            return {'status': 'error', 'message': stderr or stdout}

    def disconnect(self) -> dict:
        """Rozłącz aktywne WiFi."""
        stdout, stderr, rc = _run(['nmcli', 'device', 'disconnect', 'wlan0'])
        if rc == 0:
            return {'status': 'disconnected'}
        return {'status': 'error', 'message': stderr}

    def get_ip(self, interface: str = 'wlan0') -> Optional[str]:
        return self._get_ip(interface)

    # ── Helpers ────────────────────────────────────────────────

    def _get_ip(self, interface: str) -> str:
        # Sprawdź podany interface
        stdout, _, rc = _run(['ip', '-4', 'addr', 'show', interface])
        if rc == 0:
            m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', stdout)
            if m:
                return m.group(1)
        # Fallback: znajdź IP na dowolnym aktywnym interfejsie (eth0, wlan0)
        for iface in ['eth0', 'wlan0', 'end0']:
            stdout, _, rc = _run(['ip', '-4', 'addr', 'show', iface])
            if rc == 0:
                m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', stdout)
                if m and not m.group(1).startswith('127.'):
                    return m.group(1)
        return ''

    def _get_interface(self) -> str:
        """Zwróć nazwę aktywnego interfejsu sieciowego."""
        for iface in ['eth0', 'wlan0', 'end0']:
            stdout, _, rc = _run(['ip', '-4', 'addr', 'show', iface])
            if rc == 0:
                m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', stdout)
                if m and not m.group(1).startswith('127.'):
                    return iface
        return ''

    def _get_ip_legacy(self, interface: str) -> str:
        stdout, _, rc = _run(['ip', '-4', 'addr', 'show', interface])
        if rc != 0:
            return ''
        m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', stdout)
        return m.group(1) if m else ''

    def _get_signal(self, interface: str) -> Optional[int]:
        stdout, _, rc = _run(['nmcli', '-t', '-f', 'SIGNAL',
                              'device', 'wifi'])
        if rc == 0:
            for line in stdout.splitlines():
                try:
                    return int(line.strip())
                except ValueError:
                    continue
        return None

    def _safe_int(self, s: str, default: int = 0) -> int:
        try:
            return int(s)
        except (ValueError, TypeError):
            return default
