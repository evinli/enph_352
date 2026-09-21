#!/usr/bin/env python3

import numpy as np
import sys
import pyvisa as visa
from matplotlib import pyplot as plt
import argparse
import time

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
def get_data(scope,mdepth) :
    print("About to fetch data in {0} points...".format(mdepth))
    fulldata = []
    points_list = list(range(489, mdepth, 489))
    points_list.append(mdepth)
    for thisindex, endpoint in enumerate(points_list) :
        if thisindex != 0 :
            startpoint = points_list[thisindex-1]+1
        else :
            startpoint = 1
        scope.write(":WAV:STAR {0}".format(startpoint))
        scope.write(":WAV:STOP {0}".format(endpoint)) # 489 is the maximum distance between start and end
        try :
          rawdata = scope.query_binary_values(':WAV:DATA?', datatype = 'I', container = np.array)
        except :
          # fill it with zeros ?
          print("Data collection failed for points",startpoint,endpoint)
          # Killing as it was interfering with trace sizes
          rawdata = []
          #rawdata = np.zeros(489)
        fulldata = np.append(fulldata,rawdata)
        # NOTE: 
        # After retrieving data, you will get a crash if you
        # attempt to check :WAV:STOP. It is fine before, but
        # broken after. You can still set it but you can't read it.
    # Need to convert to real voltage values.
    # Using the scale info has proven confusing, so we'll actually just take the maximum
    # and minimum in the channel.
    #scope.write(":MEAS:SOUR {0}".format(channel))
    vmin = float(scope.query(":MEAS:VMIN?").strip())
    vmax = float(scope.query(":MEAS:VMAX?"))
    if len(fulldata)==0 :
        return fulldata
    
    # But if we got something, we can try to normalise it
    rawmin = np.amin(fulldata)
    rawmax = np.amax(fulldata)
    slope = (vmax - vmin)/(rawmax - rawmin)
    intercept = vmin - slope*rawmin
    normalised_data = fulldata*slope + intercept

    return normalised_data


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
time.sleep(1)

# Grab the raw data from channel
scope.write(":STOP")

# Get the various time info
timescale = float(scope.query(":TIM:SCAL?"))
timeoffset = float(scope.query(":TIM:OFFS?"))

# Check the sample rate
sample_rate = scope.query(':ACQ:SRAT?')

# Note: not :WAV:POIN:MODE, which is for other DS1000-series Rigol scopes
# Byte return format is a value between 0 and 255
scope.write(":WAV:SOUR {0}".format(args.readChannel))

# Try to make this not gigantic
scope.write(":ACQ:MDEP 6000")

# Get the trace
mdepth = int(float(sample_rate)*timescale*12.) # This is the true mdepth, regardless of what we set
tracedata = get_data(scope,mdepth)
print(tracedata)

# We know the time increment between all our measurements and the offset of the first value,
# so we can make a time axis for our data.
time_axis = np.linspace(timeoffset - 6 * timescale, timeoffset + 6 * timescale, num=len(tracedata))

# Turn back on
scope.write(":RUN")

# Release scope for next call
scope.close()
rm.close()

# If requested, format and save everything to an output file
#save all of our voltages that were stored in myArray
if args.outputFile :
    fname1 = '{0}-Voltages.dat'.format(args.outputFile)
    np.savetxt(fname1, tracedata, delimiter=",")
    print('saved to',fname1)
    #save the time axis array as well. We'll need this
    fname2 = '{0}-Times.dat'.format(args.outputFile)
    np.savetxt(fname2, time_axis, delimiter=",")
    print('saved to',fname2)
