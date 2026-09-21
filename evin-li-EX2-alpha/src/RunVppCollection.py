#!/usr/bin/env python3
import pyvisa as visa
import os
import time
import argparse
import pigpio
import sys
import RPi.GPIO as GPIO
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT)) # Add PROJECT_ROOT to PATH

GATE1_PIN = 5

class RigolScope:
    """Wraps PyVISA calls for the Rigol DS Series Oscilloscope."""
    def __init__(self, resource_manager):
        self.rm = resource_manager
        self.instr = self._find_and_open()
        
    def _find_and_open(self):
        resources = self.rm.list_resources()
        address = next((addr for addr in resources if "DS" in addr), None)
        if not address:
            raise ConnectionError("Could not find Rigol Scope (DS) on USB.")
        
        print(f"Connecting to Scope: {address}")
        scope = self.rm.open_resource(address, timeout=2000, chunk_size=1024000)
        return scope

    def configure(self, trigger_ch="CHAN1", read_ch="CHAN1", level=4.0):
        self.instr.write(":RUN")
        self.instr.write(f":TRIG:EDG:SOUR {trigger_ch}")
        self.instr.write(f"TRIG:EDG:LEV {level}")
        self.instr.write(f":MEAS:SOUR {read_ch}")
        self.instr.write(":CHAN1:SCAL 2.0")
        self.instr.write(":ACQ:MDEP 6000")
        time.sleep(0.1)

    def get_vpp(self):
        try:
            val = float(self.instr.query(":MEAS:VPP?").strip())
            return val if val < 1e30 else 0.0  # Handle invalid/clipped data
        except Exception as e:
            print(f"VPP Read Error: {e}")
            return None

    def close(self):
        self.instr.close()

class TriggerCounter:
    """Wraps pigpio logic for pulse counting."""
    def __init__(self):
        self.pi = pigpio.pi()
        self.ticks = 0

    def _callback(self, gpio, level, tick):
        if level == 1:
            self.ticks += 1

    def measure_rate(self, duration_sec):
        print(f"Measuring trigger counts for {duration_sec}s...")
        self.ticks = 0
        cb = self.pi.callback(GATE1_PIN, pigpio.RISING_EDGE, self._callback)
        time.sleep(duration_sec)
        cb.cancel()
        
        rate_per_min = (self.ticks / duration_sec) * 60
        return self.ticks, rate_per_min

    def stop(self):
        self.pi.stop()

def main():
    parser = argparse.ArgumentParser(description="Particle Vpp Histogram Collection")
    parser.add_argument("--samples", type=int, default=1000, help="Number of VPP samples to take")
    parser.add_argument("--name", type=str, help="Name of experiment")
    args = parser.parse_args()

    # Generate ISO filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    output_file_name = Path(PROJECT_ROOT) / 'data/{}_{}.csv'.format(timestamp, args.name)
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file_name), exist_ok=True)

    rm = visa.ResourceManager()
    try:
        scope = RigolScope(rm)
        scope.configure()
        
        print(f"Starting collection: {args.samples} VPP readings")
        with open(output_file_name, 'w') as f:
            f.write("Peak-to-Peak Voltage (Vpp)\n")
            for i in range(args.samples):
                vpp = scope.get_vpp()
                if vpp is not None:
                    f.write(f"{vpp:.4f}\n")
                
                if (i + 1) % 10 == 0:
                    print(f"Progress: {i+1}/{args.samples} traces collected")
                time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nSession interrupted by user.")
    except Exception as e:
        print(f"\nHardware Error: {e}")
        # Cleanup
        if 'scope' in locals(): scope.close()
        rm.close()
        print(f"File saved to: {output_file_name}")

if __name__ == "__main__":
    main()