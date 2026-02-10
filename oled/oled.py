#!/usr/bin/env python3
# Minimalny testowy skrypt OLED — wyświetla "OK"
import time
try:
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
    from PIL import Image, ImageDraw, ImageFont
    serial = i2c(port=1, address=0x3c)
    device = ssd1306(serial)
    img = Image.new("1", device.size)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((0, 0), "OLED OK", font=font, fill=255)
    device.display(img)
    time.sleep(5)
except Exception as e:
    # Jeśli biblioteki nie są dostępne, wypisz błąd i zakończ
    print("OLED test failed:", e)
    raise
