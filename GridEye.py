from serial import Serial
import struct
import numpy
import matplotlib.pyplot as plt
import numpy as np
from time import time, sleep

interp_methods = [None, 'none', 'nearest', 'bilinear', 'bicubic', 'spline16','spline36', 'hanning', 'hamming', 'hermite',
                  'kaiser', 'quadric', 'catrom', 'gaussian', 'bessel', 'mitchell', 'sinc', 'lanczos']

VERBOSE=True

class GridEyeMapper(object):
    """
    Things to consider:
    1. sending a '~' to shit stream off, only turn it on when we want to read.
    2. with a more interesting event loop that takes more time, be careful not to let serial buffer fill up or overflow.
    3. if it does overflow, expect to need to syncStream before you get good data again.
    """

    PacketWidth =  134  # bytes,  used for syncStream
    
    def __init__(self, display=True, interp='hamming'):
        port = Serial(port='/dev/ttyUSB0',baudrate=115200)
        #Initialize the device with '*'
        port.write('*')
        self.port=port
        self._start=time()
        self.numPackets=0
        self.display=display
        self.interp=interp
        
    def  run(self):
        if self.display:
            plt.ion() # allow plt.show() not to hang
            data,temp = self.read_packet()
            self.start_map(data)
        while 1:
            data,temp=self.read_packet()
            if self.display:
                self.update_map(data)
            else:
                print data
            if VERBOSE:
                delta= time()-self._start
                print 'T=',temp[0]
                print '#%s'%self.numPackets, '%f packets/sec'%(self.numPackets/delta)

    def start_map(self, data):
        self.imobj = plt.imshow(data, interpolation=self.interp)
        plt.show()
        
    def update_map(self, data):
        self.imobj.set_data(data)
        plt.draw()
    
    def _syncStream(self):
        port=self.port
        n=0
        while port.read(1) is not '*':
            n=n+1
            if n > self.PacketWidth:
                raise ValueError('Sync failed')
            continue
        ret=port.read(2) 
        if ret!='**': # last two bytes of sync pulse
            raise ValueError('Sync failed')
        
        self.chk = 0 # not computed on '***'

    def read_packet(self):
        # sync stream
        self._syncStream()
        
        port=self.port

        # Thermistor
        data=port.read(2)
        temp = struct.unpack('h',str(data))
        self.chk = self.chk + sum(map(ord,data))

        # array data
        data = port.read(128)
        self.chk=self.chk + sum(map(ord,data))

        # checksum
        chksum = ord( port.read(1) )
        self.chk = self.chk % 256
        
        if self.chk != chksum:
            print 'chksumT = %d, checksumR = %d'%(chksum, self.chk)
            data = struct.unpack('h'*64,str(data))
            data = numpy.fliplr(numpy.reshape(data,(8,8)))
            print data
            # could just go back to syncStream and try again later, and return no data
            raise ValueError('Bad checksum')
        
        data = struct.unpack('h'*64,str(data))
        data = numpy.fliplr(numpy.reshape(data,(8,8)))
        
        self.numPackets = self.numPackets+1

        return data, temp
    

if __name__ == '__main__':
    theMap = GridEyeMapper()
    theMap.run()
