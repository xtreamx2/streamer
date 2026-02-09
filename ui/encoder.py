import RPi.GPIO as GPIO

class Encoder:
    def __init__(self, pin_a, pin_b, pin_sw, callback_rotate, callback_press):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin_a, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(pin_b, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(pin_sw, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        self.pin_a = pin_a
        self.pin_b = pin_b
        self.pin_sw = pin_sw
        self.callback_rotate = callback_rotate
        self.callback_press = callback_press

        GPIO.add_event_detect(pin_a, GPIO.FALLING, callback=self._rotary)
        GPIO.add_event_detect(pin_sw, GPIO.FALLING, callback=self._press, bouncetime=300)

    def _rotary(self, channel):
        if GPIO.input(self.pin_b) == 0:
            self.callback_rotate(+1)
        else:
            self.callback_rotate(-1)

    def _press(self, channel):
        self.callback_press()
