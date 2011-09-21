#!/usr/bin/python

import math, struct, zlib

############################################################################
# HELPER FUNCTIONS

# convert a string of "0"s and "1"s into binary data (padded with 0s on the right)
def binToBytes(binString):
  return "".join([chr(sum([(ord(j)-ord('0'))*(1<<(7-jidx)) for jidx,j in zip(range(len(binString[i:i+8])), binString[i:i+8]) ])) for i in xrange(0, len(binString), 8)])

# convert a number into a string of "0"s and "1"s with nbits bits
# (2s complement)
def binary(num, nbits):
  return "".join([str((num >> i) % 2) for i in xrange(nbits-1,-1,-1)])

# a fixed point number -- in SWF the fixed point is always 16
def FB(num, nbits, mbits = 16):
  return binary(int(num), nbits) + binary(int((num - int(num)) * 2**mbits), mbits)

# convert a single boolean to a single bit
def boolToBit(cond):
  return "1" if cond else "0"

############################################################################
# Data types

class INTTYPE(object):
  def __init__(self, value):
    self.value = value
  def __str__(self): # little endian
    return struct.pack(self.fmt, self.value)

class UI8(INTTYPE):
  fmt = "<B"

class UI16(INTTYPE):
  fmt = "<H"

class UI32(INTTYPE):
  fmt = "<I"

class UI64(INTTYPE):
  fmt = "<Q"

class SI8(INTTYPE):
  fmt = "<b"

class SI16(INTTYPE):
  fmt = "<h"

class SI32(INTTYPE):
  fmt = "<i"

class SI64(INTTYPE):
  fmt = "<q"

class UI8n(object):
  def __init__(self, valarray):
    self.valarray = valarray
  def __str__(self):
    return struct.pack(*(("<"+"B"*len(self.valarray),) + tuple(self.valarray)))

class UI16n(object):
  def __init__(self, valarray):
    self.valarray = valarray
  def __str__(self):
    return struct.pack(*(("<"+"H"*len(self.valarray),) + tuple(self.valarray)))

# TODO this is untested
class UI24n(object):
  def __init__(self, valarray):
    self.valarray = valarray
  def __str__(self):
    return binToBytes("".join([binary(x, 24) for x in self.valarray])
        + ("0000" if len(self.valarray) % 2 == 1 else ""))

class UI32n(object):
  def __init__(self, valarray):
    self.valarray = valarray
  def __str__(self):
    return struct.pack(*(("<"+"I"*len(self.valarray),) + tuple(self.valarray)))

class UI64n(object):
  def __init__(self, valarray):
    self.valarray = valarray
  def __str__(self):
    return struct.pack(*(("<"+"Q"*len(self.valarray),) + tuple(self.valarray)))

class SI8n(object):
  def __init__(self, valarray):
    self.valarray = valarray
  def __str__(self):
    return struct.pack(*(("<"+"b"*len(self.valarray),) + tuple(self.valarray)))

class SI16n(object):
  def __init__(self, valarray):
    self.valarray = valarray
  def __str__(self):
    return struct.pack(*(("<"+"h"*len(self.valarray),) + tuple(self.valarray)))

# TODO are fixed point numbers signed or unsigned??? assuming unsigned.
class FIXED8(object):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return struct.pack("<BB", int(256*(self.value-int(self.value))), int(self.value))

class FIXED(object):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return struct.pack("<hH", int(self.value), \
        + int(256*256*(self.value - int(self.value))))

# TODO this is untested!
class FLOAT16(object):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    # self.value = (-1)**s * (1.c) * 2**q
    s = self.value >= 0                          #  1 bit
    q = int(math.log(abs(self.value), 2)) + 16   #  5 bits
    c = int(abs(self.value) * 2**(26-q) - 2**10) # 10 bits
    return binToBytes((  \
        boolToBit(s) +   \
        binary(q, 5) +   \
        binary(c, 10))[-1:-17:-1]) # reversed-- little-endian

class FLOAT(object):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return struct.pack("<f", self.value)

class DOUBLE(object):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return struct.pack("<d", self.value)

class Rectangle(object):
  def __init__(self, xmin, ymin, xmax, ymax):
    self.xmin = xmin
    self.ymin = ymin
    self.xmax = xmax
    self.ymax = ymax
  def __str__(self):
    nbits = int(math.log(max([abs(xc) for xc in [self.xmin, self.xmax, self.ymin, self.ymax, 1]]), 2)) + 2
    return binToBytes(binary(nbits, 5)           \
                    + binary(self.xmin, nbits)   \
                    + binary(self.xmax, nbits)   \
                    + binary(self.ymin, nbits)   \
                    + binary(self.ymax, nbits))

class Matrix(object):
  def __init__(self, scaleX = 1, scaleY = 1, rotateSkew0 = 0, rotateSkew1 = 0, translateX = 0, translateY = 0):
    self.scaleX      = scaleX
    self.scaleY      = scaleY
    self.rotateSkew0 = rotateSkew0
    self.rotateSkew1 = rotateSkew1
    self.translateX  = translateX
    self.translateY  = translateY
  def __str__(self):
    rvalue = []
    if self.scaleX != 1 or self.scaleY != 1:
      nbits = int(math.log(max([abs(xc) for xc in [self.scaleX, self.scaleY, 1]]), 2)) + 2
      mbits = 16
      rvalue.append("1")
      rvalue.append(binary(nbits + mbits, 5))
      rvalue.append(FB(self.scaleX, nbits, mbits))
      rvalue.append(FB(self.scaleY, nbits, mbits))
    else:
      rvalue.append("0")
    if self.rotateSkew0 != 0 or self.rotateSkew1 != 0:
      nbits = int(math.log(max([abs(xc) for xc in [self.rotateSkew0, self.rotateSkew1, 1]]), 2)) + 2
      mbits = 16
      rvalue.append("1")
      rvalue.append(binary(nbits + mbits, 5))
      rvalue.append(FB(self.rotateSkew0, nbits, mbits))
      rvalue.append(FB(self.rotateSkew1, nbits, mbits))
    else:
      rvalue.append("0")
    nbits = int(math.log(max([abs(xc) for xc in [self.translateX, self.translateY, 1]]), 2)) + 2
    rvalue.append(binary(nbits, 5))
    rvalue.append(binary(self.translateX, nbits))
    rvalue.append(binary(self.translateY, nbits))
    return binToBytes("".join(rvalue))

############################################################################
# Tags

class Tag(object):
  def __init__(self, data=""):
		self.data = data
  def __str__(self):
		data = str(self.data)
		if len(data) <= 62:
			# short tag
			return str(UI16((self.tagType << 6) + len(data))) + data
		else:
			# long tag
			return str(UI16((self.tagType << 6) + 0x3F)) + str(UI32(len(data))) + data

class EndTag(Tag):
	tagType = 0

class ShowFrame(Tag):
	tagType = 1

class DefineShape(Tag):
  tagType = 2
  def __init__(self, shapeID, bounds, shapestyle):
    self.data = str(UI16(shapeID)) + str(bounds) + str(shapestyle)

class PlaceObject(Tag):
  tagType = 4
  def __init__(self, objectID, depth, matrix, cxform = ""):
    self.data = str(UI16(objectID)) + str(UI16(depth)) + str(matrix) + str(cxform)

class RemoveObject(Tag):
  tagType = 5
  def __init__(self, characterID, depth):
    self.data = str(UI16(characterID)) + str(UI16(depth))

class SoundStreamHead(Tag):
  tagType = 18
  def __init__(self, psrate=3, pssize=1, pstype=0, ssformat=3, ssrate=3, sssize=1, sstype=0, sscount=1470, latency = ""):
    self.data = binToBytes(   \
        binary(0, 4)          \
        + binary(psrate, 2)   \
        + binary(pssize, 1)   \
        + binary(pstype, 1)   \
        + binary(ssformat, 4) \
        + binary(ssrate, 2)   \
        + binary(sssize, 1)   \
        + binary(sstype, 1)   \
    ) + str(UI16(sscount)) + str(latency)

class SoundStreamBlock(Tag):
  tagType = 19

class DefineShape2(Tag):
  tagType = 22
  def __init__(self, shapeID, bounds, shapestyle):
    self.data = str(UI16(shapeID)) + str(bounds) + str(shapestyle)

class PlaceObject2(Tag):
  tagType = 26
  def __init__(self,                        \
               depth,                       \
               objectID=None,               \
               placeFlagHasCharacter=False, \
               placeFlagMove=False):
    rvalue = []
    rvalue.append("0") # PlaceFlagHasClipActions    = False (always)
    rvalue.append("0") # PlaceFlagHasClipDepth      = False
    rvalue.append("0") # PlaceFlagHasName           = False
    rvalue.append("0") # PlaceFlagHasRatio          = False
    rvalue.append("0") # PlaceFlagHasColorTransform = False
    rvalue.append("0") # PlaceFlagHasMatrix         = False
    rvalue.append(boolToBit(placeFlagHasCharacter))
    rvalue.append(boolToBit(placeFlagMove))
    self.data = binToBytes(rvalue) + str(UI16(depth))
    if placeFlagHasCharacter:
      self.data += str(UI16(objectID))

class RemoveObject2(Tag):
  tagType = 28
  def __init__(self, depth):
    self.data = str(UI16(depth))

class SoundStreamHead2(SoundStreamHead):
  tagType = 45

############################################################################
# Shape Records

class RGB(object):
  def __init__(self, red, green, blue):
    self.red    = int(red)
    self.green  = int(green)
    self.blue   = int(blue)
  def __str__(self):
    return str(UI8(self.red)) + str(UI8(self.green)) + str(UI8(self.blue))

class LineStyle(object):
  def __init__(self, width, color):
    self.width = width
    self.color = color
  def __str__(self):
    return str(UI16(self.width)) + str(self.color)

class EndShapeRecord(object):
  def __str__(self):
    return "000000"

class StraightEdgeRecord(object):
  def __init__(self, dx = 0, dy = 0):
    self.dx = dx
    self.dy = dy
  def __str__(self):
    nbits = int(math.log(max([abs(self.dx), abs(self.dy), 1]), 2)) + 2
    rvalue = ["11"]
    rvalue.append(binary(nbits - 2, 4))
    if self.dx != 0 and self.dy != 0:
      rvalue.append("1")
      rvalue.append(binary(self.dx, nbits))
      rvalue.append(binary(self.dy, nbits))
    elif self.dy != 0:
      rvalue.append("01")
      rvalue.append(binary(self.dy, nbits))
    else:
      rvalue.append("00")
      rvalue.append(binary(self.dx, nbits))
    return "".join(rvalue)

class StyleChangeRecord(object):
  def __init__(self, lineStyle=None, fillStyle0=None, fillStyle1=None, x=None, y=None):
    self.lineStyle  = lineStyle
    self.fillStyle0 = fillStyle0
    self.fillStyle1 = fillStyle1
    self.x = x
    self.y = y
  def __str__(self):
    rvalue = []
    rvalue.append("0") # non-edge record flag -- always 0
    rvalue.append("0") # new styles flag
    if self.lineStyle is not None:
      rvalue.append("1")
    else:
      rvalue.append("0")
    if self.fillStyle0 is not None:
      rvalue.append("1")
    else:
      rvalue.append("0")
    if self.fillStyle1 is not None:
      rvalue.append("1")
    else:
      rvalue.append("0")
    if self.x is not None and self.y is not None:
      rvalue.append("1")
      nbits = int(math.log(max([abs(xc) for xc in [self.x, self.y, 1]]), 2)) + 2
      rvalue.append(binary(nbits, 5))
      rvalue.append(binary(self.x, nbits))
      rvalue.append(binary(self.y, nbits))
    else:
      rvalue.append("0")
    if self.fillStyle0 is not None:
      rvalue.append(self.fillStyle0)
    if self.fillStyle1 is not None:
      rvalue.append(self.fillStyle1)
    if self.lineStyle is not None:
      rvalue.append(self.lineStyle)
    return "".join(rvalue)

class ShapeWithStyle(object):
  def __init__(self, fillstyles, linestyles, numfillbits, numlinebits, shapes):
    self.fillstyles = fillstyles
    self.linestyles = linestyles
    self.numfillbits = numfillbits
    self.numlinebits = numlinebits
    self.shapes = shapes
  def __str__(self):
    return str(UI8(len(self.fillstyles)))                                      \
        + "".join(map(str, self.fillstyles))                                   \
        + str(UI8(len(self.linestyles)))                                       \
        + "".join(map(str, self.linestyles))                                   \
        + binToBytes(binary(self.numfillbits, 4) + binary(self.numlinebits, 4))\
        + binToBytes("".join(map(str, self.shapes)))

############################################################################
# SWF Wrapper

class SWF(object):
  def __init__(self, fps=30, size=(10000,10000), fname=None, nframes=0, compression=None):
    self.version = 6
    self.frameSize = Rectangle(0, 0, size[0], size[1])
    self.fps = fps
    self.nframes = nframes
    self.compression = None
    if compression:
      self.compression = zlib.compressobj(compression)
    self.totalLength = 0
    self._out = open(fname, "w")
    # 4 bytes
    if self.compression:
      self.append("CWS%c" % chr(self.version), compress=False)
    else:
      self.append("FWS%c" % chr(self.version))
    # 4 bytes -- we'll come back and fill this in
    self._length_offset = self.tell()
    self.append("####", compress=False)
    # len(str(self.frameSize)) bytes
    self.append(self.frameSize)
    # 2 bytes
    self.append(FIXED8(self.fps))
    # 2 bytes -- we'll come back and fill this in
    if self.compression is None:
      self._frames_offset = self.tell()
    else:
      self._frames_offset = None
    self.append(UI16(self.nframes))
  def tell(self):
    return self._out.tell()
  def flush(self):
    if self.compression:
      self._out.write(self.compression.flush(zlib.Z_FULL_FLUSH))
    self._out.flush()
  def append(self, data, compress=True):
    ndata = str(data)
    self.totalLength += len(ndata)
    if self.compression and compress:
      self._out.write(self.compression.compress(ndata))
    else:
      self._out.write(ndata)
  def newFrame(self):
    self.append(ShowFrame())
    self.nframes += 1
  def close(self):
    self.append(EndTag())
    if self.compression:
      self._out.write(self.compression.flush())
      self.compression = None
    self.flush()
    self._out.seek(self._length_offset)
    self._out.write(str(UI32(self.totalLength)))
    if self._frames_offset:
      self._out.seek(self._frames_offset)
      self._out.write(str(UI16(self.nframes)))
    self._out.flush()
    self._out.close()

class Sinus(SoundStreamBlock):
  def __init__(self, freq, phase, samples = 1470):
    self.data = ""
    from math import sin, exp
    for i in xrange(samples):
      self.data += str(UI16(int(15000 + 15000*sin(freq * (i + phase)))))

if __name__ == "__main__":
  x = SWF(fname="test1.swf", nframes=120, compression=9)
#  x.append(SoundStreamHead(3, 1, 0, 3, 3, 1, 0, 1470))
  # I promised 1470 16-bit samples per frame
  for i in xrange(120):
#    x.append(Sinus(0.02, 1470*i, 1470))
    x.append(DefineShape2(i+1, Rectangle(900, 900, 9100, 9100),                \
                  ShapeWithStyle(                                              \
                    [],                                                        \
                    [LineStyle(100, RGB(0, 0, 0))],                            \
                    0,                                                         \
                    1,                                                         \
                    [StyleChangeRecord(lineStyle="1", x=1000, y=1000),         \
                     StraightEdgeRecord(8000*abs(i-60)/60, 8000*abs(i-60)/60), \
                     EndShapeRecord()]                                         \
                  )))
    x.append(PlaceObject2(1, objectID=i+1, placeFlagHasCharacter=True, placeFlagMove=(i!=0)))
    x.newFrame()
  x.close()
