from struct import unpack
from numpy import fliplr, reshape, zeros
import matplotlib.pyplot as plt
from time import time, sleep
from serial import Serial

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

    def startData(self):
        #Initialize the device with '*'
        self.port.flushInput()
        self.port.write('*')
        
    def stopData(self):
        self.port.write('~')
        self.port.flushInput()

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

            ret=self._run(data)
            if not ret:
                print data
                
    def _run(self, data):
        return False
    
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
    DisplayM = {None: False, True: 'start_map', 'all': 'start_map_all'}

    def __init__(self, display='all', interp='hamming', *args, **kwD):
        super(GridEyeMapper, self).__init__(args, kwD)
        if display:
            self.display = getattr(self, self.DisplayM[display])
        else:
            self.display=display
        self.interp=interp
        if 0: # was to prestart the display so we dont fall behind the data stream, doesnt work yet
            data=zeros((8,8), dtype='uint16')
            self.display(data)
        
    def _run(self, data):
        ret=False
        if self.display:
            self.display(data)
            ret=True
        return ret
        
    def start_map(self, data):
        plt.ion() # allow plt.show() not to hang
        self.imobj = plt.imshow(data, interpolation=self.interp)
        plt.show()
        # switch to update
        self.display=self.update_map
        
    def update_map(self, data):
        self.imobj.set_data(data)
        plt.draw()

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
        # switch to update
        self.display=self.update_map_all

    def update_map_all(self, data):
        for im in self.imL:
            im.set_data(data)
        plt.draw()
    

if __name__ == '__main__':
    if 1:
        theMap = GridEyeMapper()
    else:
        theMap=DKSB1015A()
        
    theMap.run()
