from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306

class Display:
    def __init__(self):
        serial = i2c(port=1, address=0x3C)
        self.device = ssd1306(serial)

    def text(self, msg, line=0):
        from luma.core.render import canvas
        with canvas(self.device) as draw:
            draw.text((0, line * 12), msg, fill=255)
