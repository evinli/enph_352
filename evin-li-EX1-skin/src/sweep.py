"""
sweep.py - This script is intended to run on a rpi and collects data over a range of input frequencies.
"""

from pathlib import Path
import sys
import os 
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT)) # Add PROJECT_ROOT to PATH

import pyvisa
import time
from datetime import datetime
import numpy as np
from common.scpi_instruments import HP33120A, DS1202ZE

"""
Note that this script will only work if the function generator input is connected 
to channel 1 of the oscilloscope. This is because the scope's :autoscale functionality
always triggers on channel 1.

TODO "pyvisa-py.protocols.rpc.RPCError: wrong xid in reply" if ctrl-c while running query
""" 

timestamp = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
material = 'air'
output_file_name = Path(PROJECT_ROOT) / 'data/{}_{}.csv'.format(timestamp, material)
# Create directory if it doesn't exist
os.makedirs(os.path.dirname(output_file_name), exist_ok=True)

def main():
    scope, fgen = initialize_instruments(scope_num=2) 
    vpp = 8  # V
    start_freq = 50e3 # Hz
    end_freq = 80e3 # Hz

    with open(output_file_name, "w+") as f:
        f.write("Freq (Hz),Vpp_RX (V),Vpp_TX (V),Phase_Shift (deg)\n")
        
        # Sample every 1Hz
        num_points = int((end_freq - start_freq) / 1e3)
        for freq in np.linspace(start_freq, end_freq, num_points):
            print("Taking measurements for {:.00E} Hz".format(freq))
            
            # Set function generator
            fgen.write("APPL:SIN {:.0E}, {:.1f}, 0.0".format(freq, vpp))

            # Autoscale and measure
            autoscale(scope)

            # Adjust time scale to store more data in visible buffer for computations
            num_cycles_to_show = 5  # Increase this to see more periods
            period = 1 / freq
            t_scale = (num_cycles_to_show * period) / 12
            scope.write(":TIM:SCAL {:.2E}".format(t_scale))

            # Give the scope ~500ms to stabilize the trigger and acquisition
            time.sleep(0.5)
            vpp1, vpp2, rel_phase = perform_measurement(scope, 2**6)

            # Write data to CSV
            f.write("{:.2f},{},{},{}\n".format(
                freq, vpp1.strip(), vpp2.strip(), rel_phase.strip()))
            
            # Flush to ensure data is written immediately
            f.flush()

def initialize_instruments(scope_num):
    rm = pyvisa.ResourceManager("@py")
    inst_list = rm.list_resources()
    fgen_id = inst_list[0]
    scope_id = f'TCPIP0::rigol{scope_num}.phas.ubc.ca::INSTR'
    scope = DS1202ZE(rm.open_resource(scope_id), attenuation = [1,1])
    fgen = HP33120A(rm.open_resource(fgen_id))
    return scope, fgen

def perform_measurement(scope, num_averages):
    """
    Measure parameters of the waveforms. Temporarily turns on averaging to reduce noise.

    num_averages must be an integer given by 2^n, where n is from 1 to 10.
    """

    scope.write(":ACQ:TYPE AVER")
    scope.write(f":ACQ:AVER {num_averages}")

    vpp1 = scope.query(":MEAS:ITEM? VPP,CHAN1")
    vpp2 = scope.query(":MEAS:ITEM? VPP,CHAN2")
    relative_phase = scope.query(":MEAS:ITEM? RPH")

    scope.write(":ACQ:TYPE NORM")

    return vpp1, vpp2, relative_phase

def perform_stat_measurement(scope, num_counts):
    """
    With the STAT measurement options you can try to also get standard deviations of 
    measured parameters (this only makes sense if averaging is turned off).

    Unfortunately, the manufacturer does not document how to calculate how many 
    counts per second are taken, and there seems to be no way to measure the number of counts.
    """
    # TODO method to estimate counts is incorrect

    waveform_length = float(scope.query(":TIM:SCAL?")) * 12
    delay_time = waveform_length * num_counts
    scope.write(":MEAS:STAT:DISP ON")
    scope.write(":MEAS:STAT:MODE DIFF")

    scope.write(":MEAS:STAT:ITEM VPP,CHAN1")
    scope.write(":MEAS:STAT:ITEM VPP,CHAN2")
    scope.write(":MEAS:STAT:ITEM RPH")

    scope.write(":MEAS:STAT:RES")
    time.sleep(delay_time)
    scope.write(":STOP")
    avg_vpp1 = float(scope.query(":MEAS:STAT:ITEM? AVER,VPP,CHAN1"))
    avg_vpp2 = float(scope.query(":MEAS:STAT:ITEM? AVER,VPP,CHAN2"))
    # TODO counts?
    scope.write(":RUN")
    return avg_vpp1, avg_vpp2

def autoscale(scope):
    """
    By default ":autoscale" displays both channels so that they are not overlapping.
    This function changes the vertical scale of both channels to maximize resolution.
    """

    scope.write(":RUN")

    # Enable averaging
    scope.write(":ACQ:TYPE AVER")
    scope.write(":ACQ:AVER 64")

    # Let autoscale choose an initial guess
    scope.write(":autoscale")

    # Trigger on channel 2 rising edge (the function generator input)
    scope.write(":TRIG:SWEEP NORM")
    scope.write(":TRIG:MODE EDGE")
    scope.write(":TRIG:EDG:SOUR CHAN2")
    scope.write(":TRIG:EDG:SLOP NEG")

    # Measure VPP of both channels
    vpp1 = float(scope.query(":MEAS:ITEM? VPP,CHAN1"))
    vpp2 = float(scope.query(":MEAS:ITEM? VPP,CHAN2"))

    # Set scaling to maximize resolution
    scope.write(":channel1:offset 0")
    scope.write(":channel2:offset 0")
    scope.write(":CHAN1:SCAL {:.1E}".format(vpp1/7))
    scope.write(":CHAN2:SCAL {:.1E}".format(vpp2/7))

    # Disable averaging
    scope.write(":ACQ:TYPE NORM")


if __name__ == "__main__":
    main()
