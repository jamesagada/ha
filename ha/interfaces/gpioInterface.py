
import RPi.GPIO as gpio
from ha import *

# available GPIO pins
if int(gpio.RPI_INFO['REVISION'], 16) < 0x0010:
    bcmPins = [4, 17, 18, 22, 23, 24, 25, 27] # A/B
else:
    bcmPins = [4, 5, 6, 12, 13, 16, 17, 18, 22, 23, 24, 25, 26, 27] # B+

gpioInterface = None

# initial interrupt callback routine that is called when an interrupt pin goes low
def interruptCallback(pin):
    debug('debugGPIO', "interruptCallback", "pin:", pin)
    try:
        sensor = gpioInterface.sensorAddrs[pin]
        debug('debugGPIO', gpioInterface.name, "notifying", sensor.name)
        sensor.notify()
        if sensor.interrupt:
            state = gpio.input(pin)
            debug('debugGPIO', gpioInterface.name, "calling", sensor.name, state)
            sensor.interrupt(sensor, state)
    except KeyError:
        debug('debugGPIO', gpioInterface.name, "no sensor for interrupt on pin", pin)

# Interface to direct GPIO
class GPIOInterface(Interface):
    def __init__(self, name, interface=None, event=None, input=[], output=[]):
        Interface.__init__(self, name, interface=interface, event=event)
        global gpioInterface
        gpioInterface = self
        self.input = input
        self.output = output

    def start(self):
        gpio.setwarnings(False)
        gpio.setmode(gpio.BCM)
        # set I/O direction of pins
        for pin in self.input:
            if pin in bcmPins:
                debug('debugGPIO', self.name, "setup", pin, gpio.IN)
                gpio.setup(pin, gpio.IN, pull_up_down=gpio.PUD_UP)
                gpio.add_event_detect(pin, gpio.FALLING, callback=interruptCallback)
            else:
                debug('debugGPIO', self.name, "ignoring", pin)
        for pin in self.output:               # output pin
            if pin in bcmPins:
                debug('debugGPIO', self.name, "setup", pin, gpio.OUT)
                gpio.setup(pin, gpio.OUT)
                debug('debugGPIO', self.name, "write", pin, 0)
                gpio.output(pin, 0)
            else:
                debug('debugGPIO', self.name, "ignoring", pin)

    def read(self, addr):
        value = gpio.input(addr)
        debug('debugGPIO', self.name, "read", "addr:", addr, "value:", value)
        return value

    def write(self, addr, value):
        debug('debugGPIO', self.name, "write", "addr:", addr, "value:", value)
        gpio.output(addr, value)
