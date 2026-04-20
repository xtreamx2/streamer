#!/usr/bin/env python3
"""
Źródło: Bluetooth A2DP — sink (telefon → RPi) i source (RPi → głośnik BT).
Używa BlueZ przez D-Bus (dbus-python).
"""

import dbus
import dbus.mainloop.glib
import dbus.service
import subprocess
import threading
import logging
import time
from typing import Optional
from gi.repository import GLib
from .base import AudioSource

log = logging.getLogger(__name__)

BUS_NAME   = 'org.bluez'
ADAPTER    = '/org/bluez/hci0'
IFACE_ADAPTER  = 'org.bluez.Adapter1'
IFACE_DEVICE   = 'org.bluez.Device1'
IFACE_MEDIA    = 'org.bluez.Media1'
IFACE_PROPS    = 'org.freedesktop.DBus.Properties'
IFACE_OBJMGR   = 'org.freedesktop.DBus.ObjectManager'


AGENT_PATH = '/com/streamer/agent'


class AutoAcceptAgent(dbus.service.Object):
    """BT agent który automatycznie akceptuje parowanie."""

    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Release(self): pass

    @dbus.service.method('org.bluez.Agent1', in_signature='os', out_signature='')
    def AuthorizeService(self, device, uuid): pass

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='s')
    def RequestPinCode(self, device): return '0000'

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='u')
    def RequestPasskey(self, device): return dbus.UInt32(0)

    @dbus.service.method('org.bluez.Agent1', in_signature='ouq', out_signature='')
    def DisplayPasskey(self, device, passkey, entered): pass

    @dbus.service.method('org.bluez.Agent1', in_signature='os', out_signature='')
    def DisplayPinCode(self, device, pincode): pass

    @dbus.service.method('org.bluez.Agent1', in_signature='ou', out_signature='')
    def RequestConfirmation(self, device, passkey):
        log.info(f"BT auto-confirm passkey {passkey} for {device}")
        return  # auto-accept

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='')
    def RequestAuthorization(self, device): pass

    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Cancel(self): pass

class BluetoothSource(AudioSource):
    SOURCE_ID   = 'bluetooth'
    SOURCE_NAME = 'Bluetooth'
    AVAILABLE   = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._mode           = 'sink'
        self._connected_dev  = None
        self._connected_name = ''
        self._playing_title  = ''
        self._bus: Optional[dbus.SystemBus] = None
        self._scan_active    = False
        self._glib_loop      = None

        try:
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            self._bus = dbus.SystemBus()
            self._register_agent()
            # GLib main loop — wymagany żeby BT agent odbierał callbacki
            self._glib_loop = GLib.MainLoop()
            t = threading.Thread(target=self._glib_loop.run, daemon=True)
            t.start()
            log.info("GLib main loop started for BT agent")
        except Exception as e:
            log.warning(f"BlueZ D-Bus init failed: {e}")

    def _register_agent(self):
        try:
            agent = AutoAcceptAgent(self._bus, AGENT_PATH)
            mgr = dbus.Interface(
                self._bus.get_object(BUS_NAME, '/org/bluez'),
                'org.bluez.AgentManager1')
            mgr.RegisterAgent(AGENT_PATH, 'NoInputNoOutput')
            mgr.RequestDefaultAgent(AGENT_PATH)
            log.info("BT auto-accept agent registered")
        except Exception as e:
            log.warning(f"BT agent register failed: {e}")

    # ── AudioSource interface ──────────────────────────────────

    def activate(self) -> bool:
        log.info(f"Bluetooth activate, mode={self._mode}")
        self._active = True
        try:
            self._set_discoverable(True)
            self._set_pairable(True)
            self._auto_connect()
            self._set_state('idle')
            return True
        except Exception as e:
            log.error(f"BT activate error: {e}")
            self._set_state('error')
            return False

    def deactivate(self):
        log.info("Bluetooth deactivate")
        self._active = False
        self._set_discoverable(False)
        self._set_state('stopped')

    def get_status(self) -> dict:
        return {
            'source':    self.SOURCE_ID,
            'state':     self._state,
            'mode':      self._mode,
            'connected': self._connected_dev,
            'device_name': self._connected_name,
            'title':     self._playing_title,
        }

    # ── Public API ─────────────────────────────────────────────

    def set_mode(self, mode: str):
        """Przełącz tryb: 'sink' (odbieranie) lub 'source' (nadawanie)."""
        if mode not in ('sink', 'source'):
            return
        self._mode = mode
        log.info(f"BT mode → {mode}")

    def get_paired_devices(self) -> list:
        """Zwróć listę sparowanych urządzeń (Paired=True)."""
        devices = []
        if not self._bus:
            return devices
        try:
            mgr = dbus.Interface(self._bus.get_object(BUS_NAME, '/'),
                                 IFACE_OBJMGR)
            objs = mgr.GetManagedObjects()
            for path, ifaces in objs.items():
                dev = ifaces.get(IFACE_DEVICE)
                if dev is None:
                    continue
                paired = bool(dev.get('Paired', False))
                if not paired:
                    continue  # pomijaj niesparowane
                devices.append({
                    'mac':       str(dev.get('Address', '')),
                    'name':      str(dev.get('Name', 'Unknown')),
                    'connected': bool(dev.get('Connected', False)),
                    'paired':    True,
                    'trusted':   bool(dev.get('Trusted', False)),
                    'icon':      str(dev.get('Icon', 'audio-card')),
                    'path':      str(path),
                })
        except Exception as e:
            log.error(f"get_paired_devices: {e}")
        return devices

    def scan_devices(self, duration: int = 10) -> list:
        """Skanuj pobliskie urządzenia BT przez `duration` sekund."""
        if not self._bus:
            return []
        try:
            adapter = dbus.Interface(
                self._bus.get_object(BUS_NAME, ADAPTER), IFACE_ADAPTER)
            adapter.StartDiscovery()
            self._scan_active = True
            time.sleep(duration)
            adapter.StopDiscovery()
            self._scan_active = False
        except Exception as e:
            log.error(f"BT scan error: {e}")
        return self.get_paired_devices()

    def pair_device(self, mac: str) -> bool:
        """Sparuj urządzenie o podanym MAC."""
        if not self._bus:
            return False
        try:
            dev_path = self._mac_to_path(mac)
            dev = dbus.Interface(
                self._bus.get_object(BUS_NAME, dev_path), IFACE_DEVICE)
            dev.Pair()
            # trust + connect
            props = dbus.Interface(
                self._bus.get_object(BUS_NAME, dev_path), IFACE_PROPS)
            props.Set(IFACE_DEVICE, 'Trusted', dbus.Boolean(True))
            dev.Connect()
            self._connected_dev  = mac
            self._connected_name = self._get_device_name(dev_path)
            self._set_state('connected')
            log.info(f"Paired & connected: {mac}")
            return True
        except Exception as e:
            log.error(f"Pair failed {mac}: {e}")
            return False

    def connect_device(self, mac: str) -> bool:
        """Połącz wcześniej sparowane urządzenie."""
        if not self._bus:
            return False
        try:
            dev_path = self._mac_to_path(mac)
            # Upewnij się że urządzenie jest trusted
            props = dbus.Interface(
                self._bus.get_object(BUS_NAME, dev_path), IFACE_PROPS)
            props.Set(IFACE_DEVICE, 'Trusted', dbus.Boolean(True))
            dev = dbus.Interface(
                self._bus.get_object(BUS_NAME, dev_path), IFACE_DEVICE)
            dev.Connect()
            self._connected_dev  = mac
            self._connected_name = self._get_device_name(dev_path)
            self._set_state('connected')
            log.info(f"Connected: {mac}")
            return True
        except Exception as e:
            log.error(f"Connect failed {mac}: {e}")
            return False

    def disconnect_device(self, mac: str):
        """Rozłącz urządzenie."""
        if not self._bus:
            return
        try:
            dev = dbus.Interface(
                self._bus.get_object(BUS_NAME, self._mac_to_path(mac)),
                IFACE_DEVICE)
            dev.Disconnect()
            if self._connected_dev == mac:
                self._connected_dev  = None
                self._connected_name = ''
            self._set_state('idle')
        except Exception as e:
            log.error(f"Disconnect failed {mac}: {e}")

    def remove_device(self, mac: str):
        """Usuń parowanie urządzenia."""
        if not self._bus:
            return
        try:
            adapter = dbus.Interface(
                self._bus.get_object(BUS_NAME, ADAPTER), IFACE_ADAPTER)
            adapter.RemoveDevice(self._mac_to_path(mac))
        except Exception as e:
            log.error(f"Remove device failed {mac}: {e}")

    # ── Helpers ────────────────────────────────────────────────

    def _mac_to_path(self, mac: str) -> str:
        """AA:BB:CC:DD:EE:FF → /org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"""
        return f"{ADAPTER}/dev_{mac.replace(':', '_')}"

    def _get_device_name(self, path: str) -> str:
        try:
            props = dbus.Interface(
                self._bus.get_object(BUS_NAME, path), IFACE_PROPS)
            return str(props.Get(IFACE_DEVICE, 'Name'))
        except Exception:
            return 'Unknown'

    def _set_discoverable(self, enable: bool):
        if not self._bus:
            return
        try:
            props = dbus.Interface(
                self._bus.get_object(BUS_NAME, ADAPTER), IFACE_PROPS)
            props.Set(IFACE_ADAPTER, 'Discoverable', dbus.Boolean(enable))
            if enable:
                props.Set(IFACE_ADAPTER, 'DiscoverableTimeout', dbus.UInt32(0))
        except Exception as e:
            log.warning(f"set_discoverable: {e}")

    def _set_pairable(self, enable: bool):
        if not self._bus:
            return
        try:
            props = dbus.Interface(
                self._bus.get_object(BUS_NAME, ADAPTER), IFACE_PROPS)
            props.Set(IFACE_ADAPTER, 'Pairable', dbus.Boolean(enable))
        except Exception as e:
            log.warning(f"set_pairable: {e}")

    def _auto_connect(self):
        """Próbuj połączyć ostatnio używane urządzenie."""
        for dev in self.get_paired_devices():
            if dev.get('trusted') and not dev.get('connected'):
                try:
                    self.connect_device(dev['mac'])
                    break
                except Exception:
                    pass
