from struct import unpack
import signal 
from numpy import fliplr, reshape, zeros, ones, random, amax, amin, argmax, where, average
from numpy.linalg import norm
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


motion detection schemes:
1. http://www-staff.it.uts.edu.au/~massimo/BackgroundSubtractionReview-Piccardi.pdf

"""

interp_methods = [None, 'none', 'nearest', 'bilinear', 'bicubic', 'spline16','spline36', 'hanning', 'hamming', 'hermite',
                  'kaiser', 'quadric', 'catrom', 'gaussian', 'bessel', 'mitchell', 'sinc', 'lanczos']

VERBOSE=True

class DeviceError(Exception):
    pass
class SyncError(DeviceError):
    pass
class ChecksumError(DeviceError):
    pass

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

    def average_data(self, data):
        if self.samples==0:
            self.adata = data
        else:
            self.adata = self.adata+data
            
        self.samples=self.samples+1
        
        if self.samples == self.numAvg:
            if self.numAvg>1: self.adata = self.adata/self.numAvg
            self.samples=0
            return True
        else:
            return False

    def motion_detect(self, show=False):
        # simple derivative in 8x8 space
        if self.olddata is None:
            self.olddata=self.adata
            return
        # compute distance 
        diff = self.adata - self.olddata
        if VERBOSE:
            print self.olddata
            print self.adata
            print diff
        # compute Froebenius norm
        dp = norm(diff, 'fro')
        # depends strongly on averaging. for low sample count, need higher #, > 2
        if dp> 20. and self.occupancy: self.motion=True
        if dp<13.: self.motion=False
        if VERBOSE or show: print 'motion = %5.3f'%dp
        self.olddata=self.adata

    def motion_detect_current_frame(self, show=False):
        # simple derivative in 8x8 space
        # compute distance 
        diff = self.current_frame-self.adata
        if VERBOSE:
            print self.current_frame
            print self.adata
            print diff
        # compute Froebenius norm
        dp = norm(diff, 'fro')
        # depends strongly on averaging. for low sample count, need higher #, > 2
        if dp> 25. and self.occupancy: self.motion=True
        if dp<20.: self.motion=False
        if VERBOSE or show: print 'motion = %5.3f'%dp

    def occupancy_detect_single_pixel(self, show=False):
        # single pixel max detect; could use Froebenius norm here too
        dmin = amin(self.adata)
        dmax = amax(self.adata)
        rat = float(dmax)/dmin
        loc = where(self.adata==dmax)
        loc=(loc[0][0], loc[1][0])
        if VERBOSE or show: print 'min = ',dmin, ' max = ', dmax, 'ratio = %4.3f'%rat, 'max x,y = ', loc
        # hysteresis:
        if rat > 1.4: self.occupancy=True
        if rat< 1.25: self.occupancy=False
    
    def occupancy_detect_froebenius_norm(self, show=False):
        # needs background subtraction
        occ=norm(self.adata - average(self.adata), 'fro')
        if show: print 'occ = ', occ
        if occ > 30.: self.occupancy=True
        if occ < 25.: self.occupancy=False

    def step(self):
        # warning: if this function is not called frequently enough,
        # the serial buffer will fill up and you will not have current
        # readings.
        try: # shaves some microseconds off the event loop
            data,temp=self.read_packet()
        except DeviceError, e:
            print e
            # just try again next step
            return

        if VERBOSE:
            delta= time()-self._startT
            print 'T=',temp[0]
            print '#%s'%self.numPackets, '%6.3f packets/sec'%(self.numPackets/delta)

        self.current_frame=self.array_from_data(data)
        ret = self.average_data(self.current_frame)
        if ret:
            if 0:
                self.occupancy_detect_single_pixel(self.show)
            else:
                self.occupancy_detect_froebenius_norm(self.show)
            if 1:
                self.motion_detect(self.show)
            else:
                self.motion_detect_current_frame(self.show)

            self._run(self.adata)

        if self.numPackets in self.triggerL:
            self._triggerCB()
    
    # set a trigger for a one off action based on packet #
    def  run(self, numAvg=1, triggerL=(0,), show=False, doLoop=True):
        if numAvg<1: numAvg=1
        self.numAvg = numAvg
        self.triggerL=triggerL
        self.show=show
        self.samples=0
        self.numPackets=0
        self.occupancy=False
        self.motion=False
        self.adata = None
        self.olddata=None
        # maybe delay this until plot window is up, otherwise introduce slight delay in plot
        self.startData() 
        self._startT=time()
        # thread this???? 
        while doLoop:
            self.step()

    def prep(self, *args, **kwD):
        kwD['doLoop']=False
        self._run(args, kwD)
            
    def _run(self, data): # override as needed
        print data

    def _triggerCB(self): # override as needed
        pass
    
    def _syncStream(self):
        _read=self.port.read
        n=0
        while _read(1) is not '*':
            n=n+1
            if n > self.PacketWidth:
                raise SyncError("Sync failed: did not find '*' in PacketWidth bytes")
            continue
        ret=_read(2)
        if ret!='**': # last two bytes of sync pulse
            raise SyncError("Sync failed: last two bytes not '**'")

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
            raise ChecksumError('Bad checksum')
        
        self.numPackets = self.numPackets+1

        return data, temp

    def quit(self):
        print 'Cleaning up ...'
        self.stopData()
    
#def _handle(signum, frame):
#    DKSB1015A.quit(theMap)
#signal.signal(signal.SIGINT, _handle)

class GridEyeMapper(DKSB1015A):
    DisplayM = { True: 'start_map', 'all': 'start_map_all'}

    def __init__(self, display=True, interp='none', *args, **kwD):
        super(GridEyeMapper, self).__init__(args, kwD)
        self.display = getattr(self, self.DisplayM[display])
        self.interp=interp
        data=random.randint(60, 100, (8,8)) # be careful this doesnt skew scale factor
        self.display(data)  # brings the display up before we start grabbing data, so we dont get behind on the serial buffer
            
    def _run(self, data):
        self.display(data)

    def _triggerCB(self):
        self.save()
        
    def start_map(self, data):
        plt.ion() # allow plt.show() not to hang
        self.imobj = plt.imshow(data, interpolation=self.interp)
        plt.title('Occupied = ??  / Motion = ??')
        plt.show()
        # switch to update
        self.display=self.update_map
        
    def update_map(self, data):
        self.imobj.set_data(data)
        plt.title('Occupied = %s    /    Motion = %s'%(self.occupancy, self.motion) )
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
            
    def save(self):
        TimeStamp =   datetime.datetime.now().isoformat().replace(':', '-').split('.')[0]    
        fn = 'Pics/grideye-%s.png'%TimeStamp
        print 'Saving to %s (numPackets = %d)'%(fn, self.numPackets)
        plt.savefig(fn)
    

if __name__ == '__main__':
    import datetime
    if 1:
        theMap = GridEyeMapper()
    else:
        theMap=DKSB1015A()
        
    theMap.run(numAvg=10, triggerL=(0,), show=True)
