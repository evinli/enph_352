#!/usr/bin/env python3

import numpy as np
import string
import sys
import time
import pyvisa as visa

# Based on examples in e.g.
# https://gist.github.com/prhuft/8d961e2983bfdf8fdf1effcc1aae61a9
# https://gist.github.com/pklaus/7e4cbac1009b668eafab
# Programming guide for this oscilloscope:
# https://beyondmeasure.rigoltech.com/acton/attachment/1579/f-af444326-0551-4fd5-a277-bf8fff6f53cb/1/-/-/-/-/DS1000Z-E_ProgrammingGuide_EN.pdf

# Make the pyvisa resource manager
rm = visa.ResourceManager()
# Get the USB device, e.g. 'USB0::0x1AB1::0x0588::DS1ED141904883'
instruments = rm.list_resources()
usb = list(filter(lambda x: 'USB' in x, instruments))
# if len(usb) != 1:
#     print('Bad instrument list', instruments)
#     sys.exit(-1)
print("Will open instrument",usb[0])
scope = rm.open_resource(usb[0], timeout=2000, chunk_size=1024000) # bigger timeout for long mem

# Run
scope.write(":RUN")
# Set your trigger and let's turn it on.
# Your options are AUTO, NORM, and SING
# You probably want NORM for physics
#scope.write(":TRIG:SWEEP NORM")
#scope.write(":TFOR")
try:
    while True:
        scope.write(":MEAS:SOUR CHAN2")
        Vavg=scope.query(":MEAS:ITEM? VAVG")
        print('VAVG = {0} V'.format(Vavg.strip()))
        time.sleep(1)
except KeyboardInterrupt:
   print('keyboard interrupt')
# Release scope for next call
rm.close()
scope.close()
