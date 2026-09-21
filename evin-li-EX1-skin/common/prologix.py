"""
Simplified GPIB Serial Control via Prologix GPIB-USB Controller.
By Ryan Wicks, modified by Josh Kraan.
Based on work by Matthew Hasselfield, 2009-09-04.
"""

import serial

# TODO look into timeouts, *OPC?

class Prologix:

    def __init__(self, device_file='/dev/ttyUSB0'):
        self.ser = serial.Serial(device_file, timeout = 3)
        self._flush_io()
        self.ser.write("++mode 1\r".encode())
        self.ser.write("++auto 0\r".encode())
        self.ser.write("++eoi 1\r".encode())
        # The Prologix device can only send to / read from one GPIB channel at a time
        # self.channel records the current channel
        self.channel = -1

    def _flush_io(self):
        self.ser.flushOutput()
        self.ser.flushInput()     

    def _change_channel(self, channel : int):
        if (channel != self.channel):
            self.channel=channel
            self.ser.write(f"++addr {self.channel}\r".encode())
            self._flush_io()

    def send_command(self, command : str, channel : int):
        self._change_channel(channel)
        self.ser.write(f"{command}\r".encode())

    def read_line(self, channel : int):
        self._change_channel(channel)
        self.ser.write("++read eoi\r".encode())
        line = self.ser.readline()
        self._flush_io()
        return line.strip().decode('ascii')
    
    def new_instrument(self, channel : int):
        return Instrument(self, channel)


class Instrument():

    def __init__(self, prologix : Prologix, channel=21):
        self.prologix = prologix
        self.channel = channel

    def query(self, command : str):
        self.prologix.send_command(command, self.channel)
        return self.prologix.read_line(self.channel)

    def write(self, command : str):
        self.prologix.send_command(command, self.channel)
