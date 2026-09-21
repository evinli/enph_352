#!/usr/bin/env python3
# updated January 20th, 2023 by JW

import pyvisa as visa
import argparse
import time

# sys.exit('This code is provided as a start.  Copy to your workspace and edit it')

# Based on examples in e.g.
# https://gist.github.com/prhuft/8d961e2983bfdf8fdf1effcc1aae61a9
# https://gist.github.com/pklaus/7e4cbac1009b668eafab
# https://www.codeproject.com/Articles/869421/Interfacing-Rigol-Oscilloscopes-with-C

# Programming guide for this oscilloscope:
# https://beyondmeasure.rigoltech.com/acton/attachment/1579/f-af444326-0551-4fd5-a277-bf8fff6f53cb/1/-/-/-/-/DS1000Z-E_ProgrammingGuide_EN.pdf

parser = argparse.ArgumentParser(description='Process settings.')
parser.add_argument('--triggerLevel', type=float, help='Change trigger level')
parser.add_argument('--triggerChannel', type=str, help="Change channel on which you're triggering")
parser.add_argument('--readChannel', type=str, default='CHAN1',help='Channel to read trace from (default CHAN1)')
parser.add_argument('--outputFile', type=str, help='Save trace to file with given name')

args = parser.parse_args()
print(args)

# Since we can only collect a bit of data at a time on these scopes,
# walk through the size of the trace samples and accumulate them here.

# Make the pyvisa resource manager
rm = visa.ResourceManager()
# Get the USB device, e.g. 'USB0::0x1AB1::0x0588::DS1ED141904883'
instruments = rm.list_resources()
usbs = list(filter(lambda x: 'USB' in x, instruments))
scope_address = ""
for address in usbs :
    if "::DS" in address :
        scope_address = address
if not scope_address :
    print("Could not find address of scope!")
    exit(1)

print("Will open instrument",scope_address)

scope = rm.open_resource(scope_address, timeout=2000, chunk_size=1024000)

# Ensure scope running
scope.write(":RUN")

# Set trigger channel
if (args.triggerChannel) :
    print("You requested to set the trigger channel to",args.triggerChannel)
    scope.write(":TRIG:EDG:SOUR {0}".format(args.triggerChannel))
    print("Source is now",scope.query(":TRIG:EDG:SOUR?"))

# Sets trigger level.
if (args.triggerLevel) :
    scope.write(":TRIG:EDG:LEV {0}".format(args.triggerLevel))

# Wait a second to make sure we trigger
time.sleep(0.1)

# Check the sample rate
sample_rate = scope.query(':ACQ:SRAT?')
timescale = float(scope.query(":TIM:SCAL?"))

# Note: not :WAV:POIN:MODE, which is for other DS1000-series Rigol scopes
# Byte return format is a value between 0 and 255

#  Important:  The scope has different commands for which channel to get a trace from
#                                               and which channel to measure from !!
#______________________

scope.write(":WAV:SOUR {0}".format(args.readChannel))
scope.write(":MEAS:SOUR {0}".format(args.readChannel))

# Try for now, at least
scope.write(":ACQ:MDEP 6000")


# You will need to change this based on what you
# think is appropriate to measure
# See the programming guide above.
vavg = float(scope.query(":MEAS:VAVG?"))
print(f'Average voltage is %f V' %(vavg))

# Release scope for next call
scope.close()
rm.close()
