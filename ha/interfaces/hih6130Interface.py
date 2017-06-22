import time
import math
from ha import *

# HIH-6130/6131 humidity sensor

class HIH6130Interface(Interface):
    objectArgs = ["interface", "event"]
    def __init__(self, name, interface, addr=0x27):
        Interface.__init__(self, name, interface)
        self.addr = addr

    def read(self, addr):
        debug('debugHIH6130', self.name, "read", addr)
        try:
#            self.interface.writeQuick(self.addr)
#            time.sleep(0.050)
            data = self.interface.readBlock((self.addr, 0), 4)
            status = (data[0] & 0xc0) >> 6
            humidity = (((data[0] & 0x3f) << 8) + data[1]) *100 / 16383
            humidity = ((((data[0] & 0x3F) * 256) + data[1]) * 100.0) / 16383.0
            temp = (((data[2] & 0xFF) * 256) + (data[3] & 0xFC)) / 4
            tempC = (temp / 16384.0) * 165.0 - 40.0
            tempF = tempC * 1.8 + 32
            dewpointC = 243.04*(math.log(humidity/100)+((17.625*tempC)/(243.04+tempC)))/(17.625-math.log(humidity/100)-((17.625*tempC)/(243.04+tempC)))
            dewpointF = dewpointC * 1.8 + 32
            debug("debugHumidity", "humidity:", humidity, "tempC:", tempC, "tempF:", tempF, "dewpointC:", dewpointC, "dewpointF:", dewpointF)
            if addr == "humidity":
                return humidity
            elif addr == "temp":
                return tempF
            elif addr == "dewpoint":
                return dewpointF
            else:
                return 0
        except:
            return 0

