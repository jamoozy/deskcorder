#!/usr/bin/python

import string
from ming import *

Ming_useSWFVersion(7)

fps  = 33.0
fpsi = 1000./fps #nominally, anyway

m = SWFMovie()
m.setDimension(640,520)
m.setBackground(0x00, 0x00, 0x00)
m.setRate(fps)

# chalkboard boundary

s = SWFShape()
s.setLine(1, 0xff, 0xff, 0xff)
s.movePenTo(0,481)
s.drawLine(640,0)
m.add(s)

s = SWFShape()
s.setLine(1, 0xff, 0xff, 0xff)
s.movePenTo(0,0)
s.drawLine(0,480)
m.add(s)

s = SWFShape()
s.setLine(1, 0xff, 0xff, 0xff)
s.movePenTo(0,0)
s.drawLine(640,0)
m.add(s)

s = SWFShape()
s.setLine(1, 0xff, 0xff, 0xff)
s.movePenTo(640,0)
s.drawLine(0,480)
m.add(s)


# pause/play button

s = SWFShape()
s.setRightFill(s.addFill(0,0,0))
s.movePenTo(-10,-10)
s.drawLine(20,0)
s.drawLine(0,20)
s.drawLine(-20,0)
s.drawLine(0,-20)
s.setRightFill(s.addFill(0xaa,0xaa,0xaa))
s.movePenTo(-10,-10)
s.drawLine(8,0)
s.drawLine(0,20)
s.drawLine(-8,0)
s.drawLine(0,-20)
s.movePenTo(2,-10)
s.drawLine(8,0)
s.drawLine(0,20)
s.drawLine(-8,0)
s.drawLine(0,-20)

b = SWFButton()
b.addShape(s, SWFBUTTON_HIT | SWFBUTTON_UP | SWFBUTTON_DOWN | SWFBUTTON_OVER)
b.addAction(SWFAction("setTarget('/chalk') ; stop(); setTarget('/ppbut'); gotoFrame(1);"), SWFBUTTON_MOUSEDOWN | SWFBUTTON_MOUSEUP);

p = SWFSprite()
a = p.add(b)
p.add(SWFAction("setTarget('/ppbut') ; stop();"))
p.nextFrame()

s = SWFShape()
s.setRightFill(s.addFill(0,0,0))
s.movePenTo(-10,-10)
s.drawLine(20,0)
s.drawLine(0,20)
s.drawLine(-20,0)
s.drawLine(0,-20)
s.setRightFill(s.addFill(0xaa,0xaa,0xaa))
s.movePenTo(-8,-12)
s.drawLine(18,12)
s.drawLine(-18,12)
s.drawLine(0,-24)

b = SWFButton()
b.addShape(s, SWFBUTTON_HIT | SWFBUTTON_UP | SWFBUTTON_DOWN | SWFBUTTON_OVER)
b.addAction(SWFAction("""
setTarget('/');
if(chalk._currentframe == chalk._totalframes) {
  chalk.gotoAndPlay(1);
} else {
  chalk.play();
}
setTarget('/ppbut'); gotoFrame(0);
"""), SWFBUTTON_MOUSEDOWN | SWFBUTTON_MOUSEUP);

p.remove(a)
p.add(b)
p.add(SWFAction("setTarget('/ppbut') ; stop();"))
p.nextFrame()

i = m.add(p)
i.setName('ppbut')
i.moveTo(50,500)

# stop button

s = SWFShape()
s.setRightFill(s.addFill(0xaa,0xaa,0xaa))
s.movePenTo(-10,-10)
s.drawLine(20,0)
s.drawLine(0,20)
s.drawLine(-20,0)
s.drawLine(0,-20)

b = SWFButton()
b.addShape(s, SWFBUTTON_HIT | SWFBUTTON_UP | SWFBUTTON_DOWN | SWFBUTTON_OVER)
b.addAction(SWFAction("setTarget('/chalk') ; gotoFrame(1); stop(); setTarget('/ppbut'); gotoFrame(1);"), SWFBUTTON_MOUSEDOWN);

p = SWFSprite()
p.add(b)
p.nextFrame()

i = m.add(p)
i.moveTo(80,500)

# FF button

s = SWFShape()
s.setRightFill(s.addFill(0,0,0))
s.movePenTo(-10,-10)
s.drawLine(20,0)
s.drawLine(0,20)
s.drawLine(-20,0)
s.drawLine(0,-20)
s.setRightFill(s.addFill(0xaa,0xaa,0xaa))
s.movePenTo(-10,-10)
s.drawLine(10,10)
s.drawLine(-10,10)
s.drawLine(0,-20)
s.movePenTo(0,-10)
s.drawLine(10,10)
s.drawLine(-10,10)
s.drawLine(0,-20)

b = SWFButton()
b.addShape(s, SWFBUTTON_HIT | SWFBUTTON_UP | SWFBUTTON_DOWN | SWFBUTTON_OVER)
b.addAction(SWFAction("setTarget('/'); FF = true;"),  SWFBUTTON_MOUSEDOWN);
b.addAction(SWFAction("setTarget('/'); FF = false;"), SWFBUTTON_MOUSEUP);

p = SWFSprite()
p.add(b)
p.nextFrame()

i = m.add(p)
i.moveTo(110,500)

# RR button

s = SWFShape()
s.setRightFill(s.addFill(0,0,0))
s.movePenTo(-10,-10)
s.drawLine(20,0)
s.drawLine(0,20)
s.drawLine(-20,0)
s.drawLine(0,-20)
s.setRightFill(s.addFill(0xaa,0xaa,0xaa))
s.movePenTo(10,-10)
s.drawLine(-10,10)
s.drawLine(10,10)
s.drawLine(0,-20)
s.movePenTo(0,-10)
s.drawLine(-10,10)
s.drawLine(10,10)
s.drawLine(0,-20)

b = SWFButton()
b.addShape(s, SWFBUTTON_HIT | SWFBUTTON_UP | SWFBUTTON_DOWN | SWFBUTTON_OVER)
b.addAction(SWFAction("setTarget('/'); RR = true;"),  SWFBUTTON_MOUSEDOWN);
b.addAction(SWFAction("setTarget('/'); RR = false;"), SWFBUTTON_MOUSEUP);

p = SWFSprite()
p.add(b)
p.nextFrame()

i = m.add(p)
i.moveTo(20,500)

# actually input and process the data file

a = open('strokes.out').readlines()
clears = map(float, string.split(a[0]))
slides = map(lambda x:                                               \
           map(lambda y:                                             \
             map(lambda z:                                           \
               (lambda zz:                                           \
                 tuple(map(int, zz[0:2])+[float(zz[2])]))            \
                 (string.split(z, ' ')),                             \
               string.split(y, '\n')),                               \
             string.split(x, '\n\n')),                               \
           string.split(string.strip(string.join(a[1:],'')),'\n\n\n'))

# arrange things so that you draw everything "on time"
# that is, everything gets drawn by the time it is
# timestamped to get drawn

lines = []

for slide in slides:
  slidelines = []
  for curve in slide:
    if len(curve) == 0:
      continue
    last = curve[0]
    for point in curve[1:]:
      slidelines.append((last,point))
      last = point
    if len(curve) == 1:
      slidelines.append((last,last))
  lines.append(slidelines)

frames = []
thisframe = []
time = clears[0]
clears = clears[1:]

while len(lines) > 0:
  while len(lines[0]) > 0:
    xi = lines[0][0][0][0]
    yi = lines[0][0][0][1]
    ti = lines[0][0][0][2]
    xf = lines[0][0][1][0]
    yf = lines[0][0][1][1]
    tf = lines[0][0][1][2]
    if ti > time:
      time += fpsi
      frames.append(thisframe) # replace with just doing the frame here?
      thisframe = []
    elif tf < time:
      thisframe.append(lines[0][0])
      lines[0] = lines[0][1:]
    else:
      xm = ((xf - xi) * (time - ti)) / (tf - ti) + xi
      ym = ((yf - yi) * (time - ti)) / (tf - ti) + yi
      thisframe.append(((xi,yi,ti),(xm,ym,time)))
      lines[0][0] = ((xm,ym,time),(xf,yf,tf))
      time += fpsi
      frames.append(thisframe) # replace with just doing the frame here?
      thisframe = []

  if len(clears) > 0:
    while clears[0] > time:
      time += fpsi
      frames.append(thisframe) # replace with just doing the frame here?
      thisframe = []

    thisframe.append('clear')
    clears = clears[1:]

  lines = lines[1:]

frames.append(thisframe) # replace with just doing the frame here?
thisframe = []

sofar = []

p = SWFSprite()

s = SWFShape()
s.setRightFill(s.addFill(0xaa,0xaa,0xaa))
s.movePenTo(200,490)
s.drawLine(440,0)
s.drawLine(0,20)
s.drawLine(-440,0)
s.drawLine(0,-20)
m.add(s)

s = SWFShape()
s.setRightFill(s.addFill(0x55,0x55,0x55))
s.movePenTo(200,497)
s.drawLine(440,0)
s.drawLine(0,6)
s.drawLine(-440,0)
s.drawLine(0,-6)
m.add(s)

s = SWFShape()
s.setRightFill(s.addFill(0xaa,0xaa,0xaa))
s.setLine(1,0x00,0x00,0x00)
s.movePenTo(-20,-10)
s.drawLine(40,0)
s.drawLine(0,20)
s.drawLine(-40,0)
s.drawLine(0,-20)
s.setRightFill(s.addFill(0x55,0x55,0x55))
s.setLine(1,0x55,0x55,0x55)
s.movePenTo(-10,-2)
s.drawLine(20,0)
s.drawLine(0,4)
s.drawLine(-20,0)
s.drawLine(0,-4)

b = SWFButton()
b.addShape(s, SWFBUTTON_HIT | SWFBUTTON_UP | SWFBUTTON_DOWN | SWFBUTTON_OVER)
b.addAction(SWFAction("startDrag('/slider',220,500,620,500); setTarget('/'); Playing = false;"), SWFBUTTON_MOUSEDOWN);
b.addAction(SWFAction("stopDrag(); setTarget('/'); ok = Math.ceil(((slider._x-220.)*chalk._totalframes)/400.); chalk.gotoAndPlay(ok); Playing = true; setTarget('/ppbut'); gotoFrame(0);"), SWFBUTTON_MOUSEUP | SWFBUTTON_MOUSEUPOUTSIDE);

ps = SWFSprite()
ps.add(b)
ps.nextFrame()

slider = m.add(ps)
slider.setName('slider')
slider.moveTo(220,500)

for frame in xrange(len(frames)):
  for stroke in frames[frame]:
    if stroke == 'clear':
      for i in sofar:
        p.remove(i)
      sofar = []
    else:
      s = SWFShape()
      s.setLine(1, 0xff, 0xff, 0xff)
      s.movePenTo(stroke[0][0],stroke[0][1])
      s.drawLineTo(stroke[1][0],stroke[1][1])
      sofar.append(p.add(s))
#  slider.moveTo(220 + (400*frame / len(frames)),500)
  p.nextFrame()

#p.add(SWFAction("stop(); gotoFrame(0); setTarget('/ppbut'); gotoFrame(1);"));
p.add(SWFAction("stop(); setTarget('/ppbut'); gotoFrame(1);"));

p.nextFrame()
i = m.add(p)
i.setName('chalk')

m.add(SWFAction(""" 

setTarget('/');
Playing = true;
FF = false;
RR = false;
move = function() {
  if(Playing) {
    slider._x = 220 + (chalk._currentframe * 400) / chalk._totalframes;
  }
  if(FF) { 
    chalk.gotoAndPlay(chalk._currentframe + 3);
  }
  if(RR) { 
    chalk.gotoAndPlay(chalk._currentframe - 5);
  }
};
chalk.onEnterFrame = move;
"""));

print "%d frames converted." % (len(frames))

m.save("ming-draw.swf")
