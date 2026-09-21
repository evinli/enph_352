#!/usr/bin/env python

import os
import subprocess
import json
import time
import click
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
PINroomvalve = 19
PINvacuumvalve = 26
PINvacuumpower = 16
GPIO.setup(PINvacuumvalve, GPIO.OUT)
GPIO.setup(PINroomvalve, GPIO.OUT)
GPIO.setup(PINvacuumpower, GPIO.OUT)

@click.command()
@click.option('--pump', type=click.BOOL, help='switch pump, do this only at the beginning and end of experiment')
@click.option('--vacuumvalve', type=click.FLOAT, help='pull vacuum from chamber for some seconds')
@click.option('--roomvalve', type=click.FLOAT, help='admit room air to chamber for some seconds')
@click.option('--status', is_flag=True, help='get status reports on all output settings')
def switch(pump, vacuumvalve, roomvalve, status):
    """Use to open the two control valves for a fixed period of time. You may
    close the valve prematurely by interrupting the program using Ctrl-C.
    You can enquire about pump and valve status with option --status. Refrain
    from starting and stopping the pump. Start at the beginning and shutoff
    at the end of our experiment. Valid boolean for off=0 and on=1"""

    if pump is not None:
        if pump:
            click.echo('switching pump on')
            # Turn on Power.  Harmless if it is already on.
            GPIO.output(PINvacuumpower, GPIO.HIGH)
        else:
            click.echo('switching pump off')
            # Turn on Power.  Harmless if it is already on.
            GPIO.output(PINvacuumpower, GPIO.LOW)
    if vacuumvalve is not None:
        click.echo("Opening Vac Valve, pump is sucking on chamber (provided it's on)...")
        GPIO.output(PINvacuumvalve, GPIO.HIGH)
        try:
            vacuumvalve = min(vacuumvalve, 600)
            click.echo('waiting {0} seconds'.format(vacuumvalve))
            time.sleep(vacuumvalve)
        except KeyboardInterrupt:
            print('Keyboard Interrupt Detected')
        GPIO.output(PINvacuumvalve, GPIO.LOW)
        click.echo('Closing Vac Valve, chamber isolated from vacuum pump')
    if roomvalve is not None:
        click.echo('Opening Room Valve, air is coming into chamber ...')
        GPIO.output(PINroomvalve, GPIO.HIGH)
        try:
            roomvalve = min(roomvalve, 600)
            click.echo('waiting {0} seconds'.format(roomvalve))
            time.sleep(roomvalve)        
        except KeyboardInterrupt:
            print('Keyboard Interrupt Detected')
        click.echo('Closing Vac Valve, chamber isolated from room air')
        GPIO.output(PINroomvalve, GPIO.LOW)
    if status:
        if GPIO.input(PINvacuumvalve):
            click.echo('Vac Valve OPEN, pump is sucking on chamber')
        else:
            click.echo('Vac Valve CLOSED, pump is isolated from chamber')
        if GPIO.input(PINroomvalve):
            click.echo('Room Valve OPEN, room air is slowly leaking into chamber')
        else:
            click.echo('Room Valve CLOSED, chamber is isolated from room air')
        # enquire about the status of the smartswitch (which controls the pump)
        #returned_output = subprocess.check_output(['curl','http://smartplug1/cm?cmnd=Status'], 
                                                  #stderr=subprocess.PIPE,
                                                  #shell=False)
        # decode the JSON string returned by the curl enquiry to the smartswitch
        #power = json.loads(returned_output)['Status']['Power']
        #if power:
        #    click.echo('Pump is ON')
        #else:
            #click.echo('Pump is OFF')
        #TODO: return something here?



if __name__ == '__main__':
    switch()
