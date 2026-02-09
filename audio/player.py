from mpd import MPDClient

class Player:
    def __init__(self):
        self.client = MPDClient()
        self.client.connect("localhost", 6600)

    def play_radio(self, url):
        self.client.clear()
        self.client.add(url)
        self.client.play()

    def stop(self):
        self.client.stop()
