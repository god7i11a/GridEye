from struct import unpack
from numpy import fliplr, reshape, zeros, ones, random
from matplotlib import rc, use
use('TkAgg')
import matplotlib.pyplot as plt
from time import time, sleep
from serial import Serial

"""
Basic code to grab data from a Panasonic GridEye 8x8 IR pixel device via DigiKey's DKSB1015A evaluation board.

Using Matplotlib to visualize the data.

More in-line comments to follow.

Les Schaffer
VP
Designspring Inc.
Westport CT

http://www.designspring.com 


"""

interp_methods = [None, 'none', 'nearest', 'bilinear', 'bicubic', 'spline16','spline36', 'hanning', 'hamming', 'hermite',
                  'kaiser', 'quadric', 'catrom', 'gaussian', 'bessel', 'mitchell', 'sinc', 'lanczos']

VERBOSE=True

class DKSB1015A(object):
    """
    DigiKey Evaluation board for Panasonic's GridEye sensor.
    
    Things to consider:
    1. sending a '~' to shut stream off, only turn it on when we want to read.
    2. with a more interesting event loop that takes more time, be careful not to let serial buffer fill up or overflow.
    3. if it does overflow, expect to need to syncStream before you get good data again.
    """

    PacketWidth =  134  # bytes,  used for syncStream

    def __init__(self, *args, **kwD):
        port = Serial(port='/dev/ttyUSB0',baudrate=115200)
        self.port=port
        self.stopData()

    def startData(self):
        #Initialize the device with '*'
        self.port.flushInput()
        self.port.write('*')
        self.port.flushOutput()
        
    def stopData(self):
        self.port.write('~')
        self.port.flushInput()
        self.port.flushOutput()
        
    def array_from_data(self, data):
        data = unpack('h'*64,str(data))
        return  fliplr(reshape(data,(8,8)))
        
    def  run(self):
        # maybe delay this until plot window is up, otherwise introduce slight delay in plot
        self.startData() 
        self.numPackets=0
        self._startT=time()
        # thread this???? 
        while 1:
            data,temp=self.read_packet()
            data=self.array_from_data(data)
            if VERBOSE:
                delta= time()-self._startT
                print 'T=',temp[0]
                print '#%s'%self.numPackets, '%f packets/sec'%(self.numPackets/delta)

            self._run(data)
                
    def _run(self, data):
        print data
    
    def _syncStream(self):
        _read=self.port.read
        n=0
        while _read(1) is not '*':
            n=n+1
            if n > self.PacketWidth:
                raise ValueError('Sync failed')
            continue
        ret=_read(2) 
        if ret!='**': # last two bytes of sync pulse
            raise ValueError('Sync failed')

    def read_packet(self):
        # sync stream
        self._syncStream()
        chk=0
        
        _read=self.port.read

        # Thermistor
        data=_read(2)
        temp = unpack('h',str(data))
        chk = chk + sum(map(ord,data))

        # array data
        data = _read(128)
        chk=chk + sum(map(ord,data))

        # checksum
        chksum = ord( _read(1) )
        chk = chk % 256
        
        if chk != chksum:
            print 'chksumT = %d, checksumR = %d'%(chksum, chk)
            print self.array_from_data(data)
            # could just go back to syncStream and try again later, and return no data
            raise ValueError('Bad checksum')
        
        self.numPackets = self.numPackets+1

        return data, temp
    

class GridEyeMapper(DKSB1015A):
    DisplayM = { True: 'start_map', 'all': 'start_map_all'}

    def __init__(self, display=True, interp='spline36', trigger=0, *args, **kwD):
        super(GridEyeMapper, self).__init__(args, kwD)
        self.display = getattr(self, self.DisplayM[display])
        self.interp=interp
        self.triggerNum=trigger # set a trigger for a one off action based on packet #
        data=random.randint(60, 100, (8,8)) # be careful this doesnt skew scale factor
        self.display(data)  # brings the display up before we start grabbing data, so we dont get behind on the serial buffer
            
    def _run(self, data):
        self.display(data)
        if self.numPackets == self.triggerNum:
            self.save()
        
    def start_map(self, data):
        plt.ion() # allow plt.show() not to hang
        self.imobj = plt.imshow(data, interpolation=self.interp)
        plt.show()
        # switch to update
        self.display=self.update_map
        
    def update_map(self, data):
        self.imobj.set_data(data)
        plt.draw()
        if self.numPackets==100: self.save()

    def start_map_all(self, data):
        plt.ion() # allow plt.show() not to hang        
        fig, axes = plt.subplots(3, 6, figsize=(12, 6), subplot_kw={'xticks': [], 'yticks': []})
        fig.subplots_adjust(hspace=0.3, wspace=0.05)
        self.imL=[]
        for ax, interp_method in zip(axes.flat, interp_methods):
            imgObj=ax.imshow(data, interpolation=interp_method)
            ax.set_title(interp_method)
            self.imL.append(imgObj)
        plt.show()
        #sleep(1)
        # switch to update
        self.display=self.update_map_all

    def update_map_all(self, data):
        for im in self.imL:
            im.set_data(data)
        plt.draw()
            
    def save(self):
        plt.savefig('grideye1.png')
    

if __name__ == '__main__':
    if 1:
        theMap = GridEyeMapper(trigger=100)
    else:
        theMap=DKSB1015A()
        
    theMap.run()
