#!/usr/bin/env python3
import pyvisa as visa
import sys
import time

# Alpha experiment

# Make the pyvisa resource manager
rm = visa.ResourceManager()
# Get the USB device, e.g. 'USB0::0x1AB1::0x0588::DS1ED141904883'
instruments = rm.list_resources()
usb = list(filter(lambda x: 'USB' in x, instruments))

print("USB instrument list:")
print(usb)

# Appears that the one with "DM" in it is the multimeter
mm_address = ""
for address in usb :
    if "DM" in address :
        mm_address = address
if not mm_address :
    print("Did not find a multimeter!")
    exit(1)

meter = rm.open_resource(mm_address, timeout=2000, chunk_size=1024000) # bigger timeout for long mem

# Clear
meter.write("*RST")
time.sleep(3)
print(meter.query('*IDN?'))

# Looking for DC voltage
meter.write(":function:voltage:DC")
print(meter.query(":MEAS:VOLT:DC?"))

# Release meter for next call
rm.close()
meter.close()
