"""
PylonisAmp — CD Manager
Detekcja napędu CD/DVD przez pyudev.
Emituje eventy: cd_drive_added, cd_drive_removed, cd_disc_inserted, cd_disc_ejected
"""
import logging
import threading
try:
    import pyudev
    PYUDEV_OK = True
except ImportError:
    PYUDEV_OK = False

log = logging.getLogger('cd_manager')

class CDManager:
    def __init__(self, on_event=None):
        self._on_event = on_event  # callback(event, data)
        self._drive = None         # /dev/sr0
        self._disc_ready = False
        self._running = False
        self._thread = None

    def start(self):
        if not PYUDEV_OK:
            log.warning("pyudev nie zainstalowane — detekcja CD wyłączona")
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor, daemon=True)
        self._thread.start()
        log.info("CD monitor started")

    def stop(self):
        self._running = False

    @property
    def drive_present(self):
        return self._drive is not None

    @property
    def disc_ready(self):
        return self._disc_ready

    def _monitor(self):
        context = pyudev.Context()
        # Sprawdź istniejące urządzenia przy starcie
        for dev in context.list_devices(subsystem='block', DEVTYPE='disk'):
            if dev.get('ID_TYPE') == 'cd':
                self._drive = dev.device_node
                log.info(f"CD drive found at start: {self._drive}")
                self._check_disc(dev)
                if self._on_event:
                    self._on_event('cd_drive_added', {'drive': self._drive})

        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by('block')
        for device in iter(monitor.poll, None):
            if not self._running:
                break
            if device.get('ID_TYPE') != 'cd':
                continue
            action = device.action
            if action == 'add':
                self._drive = device.device_node
                log.info(f"CD drive added: {self._drive}")
                if self._on_event:
                    self._on_event('cd_drive_added', {'drive': self._drive})
            elif action == 'remove':
                log.info(f"CD drive removed: {self._drive}")
                self._drive = None
                self._disc_ready = False
                if self._on_event:
                    self._on_event('cd_drive_removed', {})
            elif action == 'change':
                self._check_disc(device)

    def _check_disc(self, device):
        # ID_CDROM_MEDIA=1 gdy płyta jest włożona
        media = device.get('ID_CDROM_MEDIA') == '1'
        if media and not self._disc_ready:
            self._disc_ready = True
            log.info("CD disc inserted")
            if self._on_event:
                self._on_event('cd_disc_inserted', {'drive': self._drive})
        elif not media and self._disc_ready:
            self._disc_ready = False
            log.info("CD disc ejected")
            if self._on_event:
                self._on_event('cd_disc_ejected', {})
