#!/usr/bin/env python3
import time
import os
import sys

BASE_DIR = os.path.join(os.path.expanduser("~"), "streamer")
sys.path.append(os.path.join(BASE_DIR, "hardware"))

from buttons import Buttons


def main():
    print("[input_daemon] start")

    # Callbacki — na razie tylko logi
    def on_rotate(direction):
        print(f"[input_daemon] rotate: {direction}")

    def on_click():
        print("[input_daemon] click")

    # Inicjalizacja hardware
    btn = Buttons(
        on_rotate=on_rotate,
        on_click=on_click
    )

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        btn.cleanup()
        print("[input_daemon] stop")


if __name__ == "__main__":
    main()
