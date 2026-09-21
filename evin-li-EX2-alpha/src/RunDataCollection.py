#!/usr/bin/env python3
import pyvisa as visa
import time
import argparse
import RPi.GPIO as GPIO
import pigpio
import numpy as np
import sys
import os
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT)) # Add PROJECT_ROOT to PATH

PIN_ROOM_VALVE = 19
PIN_VACUUM_VALVE = 26
PIN_VACUUM_POWER = 16
GATE1_PIN = 5

class ExperimentController:
    def __init__(self):
        self.pi = pigpio.pi()
        self.ticks = 0
        self._setup_gpio()

    def _setup_gpio(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for pin in [PIN_ROOM_VALVE, PIN_VACUUM_VALVE, PIN_VACUUM_POWER]:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

    def set_vacuum_power(self, state: bool):
        level = GPIO.HIGH if state else GPIO.LOW
        print(f"Vacuum Power: {'ON' if state else 'OFF'}")
        GPIO.output(PIN_VACUUM_POWER, level)

    def set_room_valve(self, state: bool):
        GPIO.output(PIN_ROOM_VALVE, GPIO.HIGH if state else GPIO.LOW)

    def set_vacuum_valve(self, state: bool):
        GPIO.output(PIN_VACUUM_VALVE, GPIO.HIGH if state else GPIO.LOW)

    def pulse_room_vent(self, duration: float):
        """Wraps the system call for venting the room valve."""
        print(f"Opening room valve for {duration}s")
        self.set_room_valve(True)
        time.sleep(duration)
        self.set_room_valve(False)
        print("Closing Room Valve")

    def _cb_trig(self, gpio, level, tick):
        if level == 1:
            self.ticks += 1

    def count_triggers(self, duration: float):
        """Wraps pigpio callback logic to count pulses over a duration."""
        self.ticks = 0
        cb = self.pi.callback(GATE1_PIN, pigpio.RISING_EDGE, self._cb_trig)
        time.sleep(duration)
        cb.cancel()
        return self.ticks

    def cleanup(self):
        self.set_vacuum_power(False)
        self.set_room_valve(False)
        self.set_vacuum_valve(False)
        GPIO.cleanup()
        self.pi.stop()

def instrument_setup(trigger_ch, read_ch, level):
    rm = visa.ResourceManager()
    resources = rm.list_resources()
    
    scope_addr = next((addr for addr in resources if "DS" in addr), None)
    if not scope_addr:
        print("Error: Scope not found.")
        exit(1)

    print(f"Connecting to: {scope_addr}")
    scope = rm.open_resource(scope_addr, timeout=2000, chunk_size=1024000)

    # Aggregate all scope commands into a list - was getting out of hand previously
    cmds = [
        f":TRIG:EDG:SOUR {trigger_ch}",
        f"TRIG:EDG:LEV {level}",
        f":MEAS:SOUR {read_ch}",
        ":CHAN1:SCAL 2.0",
        ":CHAN2:SCAL 2.0",
        ":RUN",
        ":WAV:SOUR CHAN1",
        ":ACQ:MDEP 6000"
    ]
    for cmd in cmds:
        scope.write(cmd)
        time.sleep(0.05)
    
    return scope, rm

def take_meas(scope, n_p2p_reads):
    # Get avg voltage from channel 2 - which reads pressure
    scope.write(":MEAS:SOUR CHAN2")
    avg_v = float(scope.query(":MEAS:ITEM? VAVG").split(',')[-1].strip())
    
    # Get peak-to-peak from channel 1 - which reads alpha particle signal
    scope.write(":MEAS:SOUR CHAN1")
    p2ps = []
    for _ in range(n_p2p_reads):
        try:
            val = float(scope.query(":MEAS:VPP?").strip())
            if val < 1e37: # Scope often returns 9.9e37 if measurement is invalid
                p2ps.append(val)
            time.sleep(0.05)
        except Exception:
            break
            
    avg_p2p = np.mean(p2ps) if p2ps else 0.0
    return avg_p2p, avg_v

def main():
    parser = argparse.ArgumentParser(description="Bragg's Curve Measurement Automation")
    parser.add_argument("--reads", type=int, default=500, help="Number of measurement cycles")
    parser.add_argument("--p2p", type=int, default=20, help="P2P readings per cycle")
    parser.add_argument("--vent", type=float, default=0.03, help="Room valve open duration (s)")
    parser.add_argument("--name", type=str, help="Name of experiment")

    args = parser.parse_args()

    # Generate ISO filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    output_file_name = Path(PROJECT_ROOT) / 'data/{}_{}.csv'.format(timestamp, args.name)
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file_name), exist_ok=True)
    
    ctrl = ExperimentController()
    scope, rm = instrument_setup("CHAN1", "CHAN1", 4.0)

    try:
        ctrl.set_vacuum_power(True)
        
        with open(output_file_name, 'w') as f:
            f.write("Pressure DMM (V_avg),Particle Peak-to-Peak (Vpp),Trigger Count\n")
            for i in range(args.reads):
                ctrl.pulse_room_vent(args.vent)
                
                print(f"[{i+1}/{args.reads}] Counting triggers...")
                trig_count = ctrl.count_triggers(2.0)
                
                print("Taking voltage readings...")
                avgp2p, avgv = take_meas(scope, args.p2p)
                
                f.write(f"{avgv:.4f}, {avgp2p:.4f}, {trig_count}\n")
                f.flush()
                time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nUser aborted. Cleaning up...")
    finally:
        scope.close()
        rm.close()
        ctrl.cleanup()
        print(f"Data saved to {output_file_name}")

if __name__ == "__main__":
    main()