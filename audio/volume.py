from mpd import MPDClient

class Volume:
    def __init__(self):
        self.client = MPDClient()
        self.client.connect("localhost", 6600)

    def set(self, value):
        self.client.setvol(value)
