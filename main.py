from utils.logger import setup_logger
from ui.display import Display
from ui.encoder import Encoder
from ui.menu import Menu
from audio.player import Player
from audio.volume import Volume
import config

def main():
    log = setup_logger()
    log.info("Streamer start")

    display = Display()
    player = Player()
    volume = Volume()
    menu = Menu(display, player, volume)

    Encoder(
        config.GPIO_ENCODER_A,
        config.GPIO_ENCODER_B,
        config.GPIO_ENCODER_SW,
        callback_rotate=menu.rotate,
        callback_press=menu.press
    )

    display.text("Ready")

    while True:
        pass

if __name__ == "__main__":
    main()
