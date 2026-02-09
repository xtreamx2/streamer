class Menu:
    def __init__(self, display, player, volume):
        self.display = display
        self.player = player
        self.volume = volume
        self.volume_level = 50

    def rotate(self, direction):
        self.volume_level = max(0, min(100, self.volume_level + direction))
        self.volume.set(self.volume_level)
        self.display.text(f"Volume: {self.volume_level}")

    def press(self):
        self.player.play_radio("http://stream.rcs.revma.com/ypqt40u0x1zuv")
        self.display.text("Playing radio")
