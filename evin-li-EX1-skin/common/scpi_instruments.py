import pyvisa
import numpy as np

class SCPIInstrument():
    def __init__(self, instrument : pyvisa.resources.MessageBasedResource, timeout, dsrdtr = False):

        self.inst = instrument
        self.inst.timeout = timeout

        if dsrdtr:
            self.inst.set_visa_attribute(pyvisa.constants.VI_ATTR_ASRL_FLOW_CNTRL, 
                                         pyvisa.constants.VI_ASRL_FLOW_DTR_DSR)

    def query(self, command : str) -> str:
        # Send a command and return the response
        # Note that malformed commands can cause timeouts
        return self.inst.query(command)

    def write(self, command : str):
        # Send a command that doesn't require a response

        # Some commands can take some time to execute. If a query is sent
        # while a command is still being executed, it can cause timeout errors.
        # To avoid this, we wait for a response from the *OPC? (operation complete) query.
        self.query(command + "; *OPC?")


class HP33120A(SCPIInstrument):
    def __init__(self, instrument : pyvisa.resources.USBInstrument, timeout=200000):
        # TODO set output impedance (OUTP:LOAD), maybe *RST everything for reproducibility?
        # TODO noise lab also uses HP33120A, make compatible with Prologix

        # This device doesn't seem to like chaining the standard three-letter commands
        # e.g. *IDN?; *IDN? will give an error and only return one

        super().__init__(instrument, timeout, dsrdtr=True)
        
        self.write("SYSTEM:REMOTE")
        self.write("*CLS")  # Clear errors

        print("Finding IDN...")
        print(self.query("*IDN?"))

        print("Testing")
        print(self.query("*TST?"))

    def arbitrary_wave(self, wave_array):
        """
        Output an arbitrary wave shape.

        :param wave_array: numpy array of values between -1 and 1, with length 
        between 8 and 16,000.
        """

        wave_string = np.array2string(wave_array, 
                                      formatter={'float_kind':'{0:.3f}'.format}, 
                                      separator=",")[1:-1]
        self.write(f"DATA VOLATILE, {wave_string}")
        self.write("FUNCtion:USER VOLATILE")
        self.write("FUNCtion:SHAPe USER") 


class DS1202ZE(SCPIInstrument):
 
    def __init__(self, instrument : pyvisa.resources.MessageBasedResource, 
                 attenuation = [1,1], timeout=20000, chunk_size=1024000):
        """
        Class for control of DS1202Z-E Oscilloscopes.

        :param attentuation: List of [channel1, channel2] probe attentuations. 

        TODO BW limit helps lower probe noise, add it.
        """
        super().__init__(instrument, timeout)
        self.inst.chunk_size = chunk_size
        #self.write("*rst") #TODO determine if this resets LAN settings (if it does, can queue commmands with ; )
        self.write(f":CHAN1:PROB {attenuation[0]}")
        self.write(f":CHAN2:PROB {attenuation[1]}")
        self.write(":WAV:FORM BYTE")
        # With MODE RAW, waveform data (i.e. :WAV: commands, not :MEAS) must be collected after :STOP
        self.write(":WAV:MODE RAW")
        self.write(":ACQ:MDEP 6000")

        self.write(":ACQ:TYPE NORM")