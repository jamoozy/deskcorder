#!/usr/bin/python

import pygtk
pygtk.require('2.0')
import gtk
import gtk.glade
import gobject
import cairo
import math
import sys
import time
import thread
import os
import signal
try:
  import audiosavior
  audio = True
except ImportError:
  audio = False

class DrawingTestWidget(gtk.DrawingArea):
  def __init__(self):
    gtk.DrawingArea.__init__(self)

    self.device = 0
    self.radius = 3.0
    self.drawing = False
    self.window_size = None
    self.raster = None
    self.raster_cr = None
    self.color = (0., 0., 0.)

    # Playback variables.
    self.play_time = None
    self.play_timer_id = None
    self.break_times = []
    self.last_pause = None

    # Keeps track of whether the state of the canvas is reflected in a file
    # somewhere or not.  If not, this is dirty.
    self.dirty = False

    # This is a very loaded list of lists.  At the topmost level, this is a
    # list of floats and lists.  It should start with a float and end in a
    # list.  The floats are "clear times" (including the starting and ending
    # times) and the lists represent slides between the clears.
    #
    # Each slide is a list of "curves" (more commonly known as "strokes").
    #
    # Each curve is a list of points.
    #
    # Each point is a tuple containing a time stamp, (x,y) position tuple,
    # radius, (r,g,b) color tuple, and (w,h) window size tuple.
    self.trace = [time.time(), []]

    # Also somewhat complex, but not nearly as much as with state.
    #
    # This is a list of points.  Each point is a tuple of time, (x,y) position
    # tuple, and (w,h) window size tuple.
    self.position = []

    self.set_events(gtk.gdk.POINTER_MOTION_MASK  | gtk.gdk.BUTTON_MOTION_MASK | gtk.gdk.BUTTON1_MOTION_MASK | gtk.gdk.BUTTON2_MOTION_MASK | gtk.gdk.BUTTON3_MOTION_MASK | gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK)

    self.connect("configure-event", self.ConfigureEvent)
    self.connect("expose-event", self.ExposeEvent)
    self.connect("motion-notify-event", self.MotionEvent)
    self.connect("button-press-event", self.ButtonPress)
    self.connect("button-release-event", self.ButtonRelease)
    self.set_size_request(800,600)

  def ConfigureEvent(self, widget, event):
    self.window_size = self.window.get_size()
    self.raster = self.window.cairo_create().get_target().create_similar(cairo.CONTENT_COLOR, self.window_size[0], self.window_size[1])
    self.raster_cr = cairo.Context(self.raster)
    self.raster_cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
    self.raster_cr.rectangle(0.0, 0.0, self.window_size[0], self.window_size[1])
    self.raster_cr.fill()
    for curve in self.trace[-1]:
      self.draw(curve[0][3], curve[0][2],
          ((curve[0][1][0]*self.window_size[0])/curve[0][4][0],
           (curve[0][1][1]*self.window_size[1])/curve[0][4][1]))
      if len(curve) > 1:
        self.draw(curve[1][3], curve[1][2],
          ((curve[0][1][0]*self.window_size[0])/curve[1][4][0],
           (curve[0][1][1]*self.window_size[1])/curve[1][4][1]),
          ((curve[1][1][0]*self.window_size[0])/curve[1][4][0],
           (curve[1][1][1]*self.window_size[1])/curve[1][4][1])
        )
      for i in xrange(len(curve)-2):
        self.draw(curve[i+2][3], curve[i+2][2],
          ((curve[i  ][1][0]*self.window_size[0])/curve[i+2][4][0],
           (curve[i  ][1][1]*self.window_size[1])/curve[i+2][4][1]),
          ((curve[i+1][1][0]*self.window_size[0])/curve[i+2][4][0],
           (curve[i+1][1][1]*self.window_size[1])/curve[i+2][4][1]),
          ((curve[i+2][1][0]*self.window_size[0])/curve[i+2][4][0],
           (curve[i+2][1][1]*self.window_size[1])/curve[i+2][4][1])
        )
    self.refresh()

  def playing(self):
    return self.play_time != None

  def play(self, t):
    print "Playing"
    self.play_time = t
    self.play_timer_id = gobject.timeout_add(100, self.play_tick)

  def play_tick(self):
    if not self.playing(): return False

    # dt is the difference between when the trace was recorded and when the
    # play button was hit.
    dt = self.play_time - self.trace[0]

    now = time.time()

    # TODO&FIXME---Efficiency.
    # Super-inefficient implementation: iterate through EVERYTHING and redraw
    # it ALL EVERY TIME.  Ideally, there should be some object-level iteratore
    # that are used instead.

    # e is a timestamp or a slide (list of curves)
    for e in self.trace:
      if type(e) == float:
        if e + dt <= now:
          self.clear()
        else:
          return True
      elif type(e) == list:
        for curve in e:
          for i in range(len(curve)):
            if curve[i][0] + dt > now: return True
            if i > 1:
              self.draw(curve[i][3], curve[i][2], curve[i-2][1], curve[i-1][1], curve[i][1])
            elif i > 0:
              self.draw(curve[i][3], curve[i][2], curve[i-1][1], curve[i][1])
            else:
              self.draw(curve[i][3], curve[i][2], curve[i][1])
      else:
        raise 'Mal-formatted trace.'

    self.stop()
    return False

  def pause(self, t):
    if self.last_pause == None:
      print "Pausing"
      self.last_pause == t
    else:
      print "Unpausing"
      self.break_times.append((self.last_pause, t))
      self.last_pause = None

  def stop(self):
    print 'Stopping'
    self.play_time = None
    self.play_timer_id = None
    self.last_pause = None
    self.break_times = []

  def GetPressure(self):
    dev = gtk.gdk.devices_list()[self.device]
    trace = dev.get_state(self.window)
    return dev.get_axis(trace[0], gtk.gdk.AXIS_PRESSURE)

  def MotionEvent(self, widget, event):
    if not self.playing():
      pos = event.get_coords()
      if self.drawing:
        self.dirty = True
        p = self.GetPressure()
        if p == None:
          p = 1.0
        r = (p * 2 + 0.2)*self.radius
        if len(self.trace[-1][-1]) > 1:
          self.draw(self.color, r, self.trace[-1][-1][-2][1], self.trace[-1][-1][-1][1], pos)
        elif len(self.trace[-1][-1]) > 0:
          self.draw(self.color, r, self.trace[-1][-1][-1][1], pos)
        else:
          self.draw(self.color, r, pos)
        self.trace[-1][-1].append((time.time(), pos, r, self.color, self.window_size))
      else:
        self.position.append((time.time(), pos, self.window_size))

  def ButtonPress(self, widget, event):
    if not self.playing():
      self.dirty = True
      self.drawing = True
      self.trace[-1].append([])

  def ButtonRelease(self, widget, event):
    if not self.playing():
      self.dirty = True
      self.drawing = False
      self.olderPos = None
      self.oldPos = None
      self.oldRad = None

  def ExposeEvent(self, widget, event):
    cr = widget.window.cairo_create()
    cr.set_source_surface(self.raster, 0.0, 0.0)
    cr.paint()
    cr.set_line_width(2)
    cr.set_source_rgba(0.0, 0.0, 0.0, 0.25)
    cr.rectangle(0.0, 0.0, self.window_size[0], self.window_size[1])
    cr.stroke()

  def setRadius(self, rad):
    self.radius = rad

  def setColor(self, r, g, b):
    self.color = (r,g,b)

  def clear(self):
    self.window_size = self.window.get_size()
    self.raster_cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
    self.raster_cr.rectangle(0.0, 0.0, self.window_size[0], self.window_size[1])
    self.raster_cr.fill()
    self.refresh()
    if not self.playing():
      self.trace.append(time.time())
      self.trace.append([])

  def refresh(self):
    reg = gtk.gdk.Region()
    reg.union_with_rect((0, 0, self.window_size[0], self.window_size[1]))
    self.window.invalidate_region(reg, False)

  def reset(self):
    self.clear()
    self.trace = [time.time(), []]
    self.position = []

  def draw(self, color, r, pos1, pos2=None, pos3=None):
    self.raster_cr.set_source_rgba(color[0], color[1], color[2], 1.0)
    reg = gtk.gdk.Region()
    if pos2 is None:
      self.raster_cr.set_line_width(0)
      self.raster_cr.arc(pos1[0], pos1[1], 0.5*r, 0.0, 2 * math.pi)
      self.raster_cr.fill_preserve()
      reg.union_with_rect((int(pos1[0] - 0.5*r), int(pos1[1] - 0.5*r), int(r), int(r)))
    elif pos3 is None:
      self.raster_cr.set_line_width(r)
      self.raster_cr.set_line_join(cairo.LINE_JOIN_MITER)
      self.raster_cr.set_line_cap(cairo.LINE_CAP_ROUND)
      self.raster_cr.move_to(pos1[0], pos1[1])
      self.raster_cr.line_to(pos2[0], pos2[1])
      self.raster_cr.stroke()
      reg.union_with_rect((
            min(int(pos1[0] - 0.5*r), int(pos2[0] - 0.5*r)),
            min(int(pos1[1] - 0.5*r), int(pos2[1] - 0.5*r)),
            int(abs(pos1[0] - pos2[0]) + r),
            int(abs(pos1[1] - pos2[1]) + r)))
    else:
      self.raster_cr.set_line_width(r)
      self.raster_cr.set_line_join(cairo.LINE_JOIN_MITER)
      self.raster_cr.set_line_cap(cairo.LINE_CAP_ROUND)
      self.raster_cr.move_to(pos1[0], pos1[1])
      self.raster_cr.line_to(pos2[0], pos2[1])
      self.raster_cr.line_to(pos3[0], pos3[1])
      self.raster_cr.stroke()
      reg.union_with_rect((
            min(int(pos1[0] - 0.5*r), int(pos2[0] - 0.5*r)),
            min(int(pos1[1] - 0.5*r), int(pos2[1] - 0.5*r)),
            int(abs(pos1[0] - pos2[0]) + r),
            int(abs(pos1[1] - pos2[1]) + r)))
      reg.union_with_rect((
            min(int(pos2[0] - 0.5*r), int(pos3[0] - 0.5*r)),
            min(int(pos2[1] - 0.5*r), int(pos3[1] - 0.5*r)),
            int(abs(pos2[0] - pos3[0]) + r),
            int(abs(pos2[1] - pos3[1]) + r)))
    self.window.invalidate_region(reg, False)

  def save(self, fname = None, format = "xml"):
    if fname == None: fname = 'strokes.xml'
    chooser = gtk.FileChooserDialog('Choose a file to save', None,
        gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
          gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
    chooser.set_do_overwrite_confirmation(True)
    chooser.set_current_folder('data')
    chooser.set_current_name(fname)
    if chooser.run() == gtk.RESPONSE_ACCEPT:
      self.saveXML(chooser.get_filename())
    chooser.destroy()

#    if format == "xml":
#      if fname is None:
#        self.saveXML()
#      else:
#        self.saveXML(fname)
#    else:
#      if fname is None:
#        self.saveRAW()
#      else:
#        self.saveRAW(fname)

  def saveXML(self, fname = "strokes.wbx"):
    output = open(fname, 'w')
    output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    clears = []
    for clear in self.trace:
      if type(clear) == float:
        clears.append(clear)
    output.write('<document>\n')
    output.write('  <clears type="array">\n')
    for t in clears:
      output.write("    <clear type=\"float\">%lf</clear>\n" % (1000*t))
    output.write('  </clears>\n')
    output.write('  <slides type="array">\n')
    for slide in self.trace:
      if type(slide) == list:
        output.write('    <slide>\n')
        output.write('      <curves type="array">\n')
        for curve in slide:
          if len(curve) == 0:
            continue
          output.write('        <curve>\n')
          output.write('          <points type="array">\n')
          for pt in curve:
            output.write('            <point>\n')
            output.write("              <posx type=\"float\">%lf</posx>\n" % (pt[1][0]*640/pt[4][0]))
            output.write("              <posy type=\"float\">%lf</posy>\n" % (pt[1][1]*480/pt[4][1]))
            output.write("              <time type=\"float\">%lf</time>\n" % (1000*pt[0]))
            output.write("              <colorr type=\"integer\">%d</colorr>\n" % int(255*pt[3][0]))
            output.write("              <colorg type=\"integer\">%d</colorg>\n" % int(255*pt[3][1]))
            output.write("              <colorb type=\"integer\">%d</colorb>\n" % int(255*pt[3][2]))
            output.write("              <thickness type=\"float\">%lf</thickness>\n" % (pt[2]*(math.sqrt(640*640+480*480))/(math.sqrt(pt[4][0]*pt[4][0]+pt[4][1]*pt[4][1]))))
            output.write('            </point>\n')
          output.write('          </points>\n')
          output.write('        </curve>\n')
        output.write('      </curves>\n')
        output.write('    </slide>\n')
    output.write('  </slides>\n')
    output.write('  <positions type="array">\n')
    for pt in self.position:
      output.write('    <position>\n')
      output.write("      <posx type=\"float\">%lf</posx>\n" % (pt[1][0]*640/pt[2][0]))
      output.write("      <posy type=\"float\">%lf</posy>\n" % (pt[1][1]*480/pt[2][1]))
      output.write("      <time type=\"float\">%lf</time>\n" % (1000*pt[0]))
      output.write('    </position>\n')
    output.write('  </positions>\n')
    output.write('</document>\n')
    output.flush() ; output.close()

  def saveTXT(self, fname = "strokes.wbt"):
    output = open(fname, 'w')
    clears = []
    for clear in self.trace:
      if type(clear) == float:
        clears.append(clear)
    for t in clears:
      output.write("%lf " % (1000*t))
    output.write("\n")
    for slide in self.trace:
      if type(slide) == list:
        for curve in slide:
          for pt in curve:
            output.write("%d %d %lf %d %d %d %lf\n" % (pt[1][0]*640/pt[4][0], pt[1][1]*480/pt[4][1], 1000*pt[0], int(255*pt[3][0]), int(255*pt[3][1]), int(255*pt[3][2]), pt[2]))
          output.write("\n")
        output.write("\n")
    output.flush()
    output.close()

  def saveRAW(self, fname = "strokes.wbr"):
    print "I don't know how to save raw files yet ..."

  def open(self, fname = None, format = 'xml'):
    if self.dirty and not self.dirtyOK(): return
    if fname == None: fname = 'strokes.xml'
    chooser = gtk.FileChooserDialog('Choose a file to save', None,
        gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
          gtk.STOCK_OPEN, gtk.RESPONSE_ACCEPT))
    chooser.set_do_overwrite_confirmation(True)
    chooser.set_current_folder('data')
    chooser.set_current_name(fname)
    if chooser.run() == gtk.RESPONSE_ACCEPT:
      self.openXML(chooser.get_filename())
      self.dirty = False
    chooser.destroy()

  def openXML(self, fname = 'strokes.wbx'):
    def get_xml_type(line, tag, typ):
      stag = '<%s type="%s">' % (tag, typ)
      etag = '</%s>' % tag
      if not line.startswith(stag): raise 'Bad wbx: expected %s' % stag
      substr = line[len(stag):line.find(etag)]
      num = float(substr) if typ == 'float' else int(substr)
      return num

    ifile = open(fname, 'r')
    state = 'start'
    self.trace = []
    self.position = []
    clears = []
    try:
      while True:
        line = ifile.next().strip()
        if state == 'start':
          if line != '<?xml version="1.0" encoding="UTF-8"?>': raise 'Bad wbx: expected <?xml version="1.0" encoding="UTF-8"?>'
          state = 'document'
        elif state == 'document':
          if line != '<document>': raise "Bad wbx: expected <document>"
          state = 'clears'
        elif state == 'clears':
          if line != '<clears type="array">': raise 'Bad wbx: expected <clears type="array">'
          state = 'clear'
        elif state == 'clear':
          if line.startswith('<clear type="float">'):
            endpos = line.find('<', 20)
            try:
              clears.append(float(line[20:endpos]) / 1000.0)
            except ValueError:
              print 'Warning wbx has non-float clear: "%s"' % line[20:endpos]
          elif line == "</clears>":
            state = 'slides'
          else:
            raise 'Bad wbx: expected <clear type="float"> or </clears>'
        elif state == 'slides':
          if line != '<slides type="array">': raise 'Bad wbx: expected <slides type="array">'
          state = 'slide'
        elif state == 'slide':
          if line != '<slide>': raise 'Bad wbx: expected <slide>'
          self.trace.append(clears.pop(0))
          self.trace.append([])
          state = 'curves'
        elif state == 'curves':
          if line != '<curves type="array">': raise 'Bad wbx: expected <curves type="array">'
          state = 'curve'
        elif state == 'curve':
          if line != '<curve>': raise 'Bad wbx: <curve>'
          self.trace[-1].append([])
          state = 'points'
        elif state == 'points':
          if line != '<points type="array">': raise 'Bad wbx: expected <points type="array">'
          state = 'point'
        elif state == 'point':
          if line == '<point>':
            try:
              posx = get_xml_type(ifile.next().strip(), 'posx', 'float') * self.window_size[0]/640
              posy = get_xml_type(ifile.next().strip(), 'posy', 'float') * self.window_size[1]/480
              time = get_xml_type(ifile.next().strip(), 'time', 'float') / 1000.0
              colorr = get_xml_type(ifile.next().strip(), 'colorr', 'integer') / 255.0
              colorg = get_xml_type(ifile.next().strip(), 'colorg', 'integer') / 255.0
              colorb = get_xml_type(ifile.next().strip(), 'colorb', 'integer') / 255.0
              thickness = get_xml_type(ifile.next().strip(), 'thickness', 'float') * (math.sqrt(self.window_size[0]*self.window_size[0]+self.window_size[1]*self.window_size[1]))/(math.sqrt(640*640+480*480))
              self.trace[-1][-1].append((time, (posx, posy), thickness, (colorr, colorg, colorb), self.window_size))
              if ifile.next().strip() != '</point>': raise 'Bad wbx: expected </point>'
            except (StopIteration, ValueError):
              raise 'Bad wbx: expected posx, posy, time, colorr, colorg, colorb, thickness, and </point>'
          elif line == '</points>':
            state = '/curve'
          else:
            raise 'Bad wbx: expected <point>...</point>'
        elif state == '/curve':
          if line != '</curve>': raise 'Bad wbx: expected </curve>'
          state = '/curves'
        elif state == '/curves':
          if line == '</curves>':
            state = '/slide'
          elif line == '<curve>':
            self.trace[-1].append([])
            state = 'points'
          else:
            raise 'Bad wbx: expected </curves> or <curve>'
        elif state == '/slide':
          if line != '</slide>': raise 'Bad wbx: expected </slide>'
          state = '/slides'
        elif state == '/slides':
          if line == '<slide>':
            self.trace.append(clears.pop(0))
            self.trace.append([])
            state = 'curves'
          elif line == '</slides>':
            state = 'positions'
          else:
            raise 'Bad wbx: expected </slides> or <slide>'
        elif state == 'positions':
          if line != '<positions type="array">': raise 'Bad wbx: expected <positions type="array">'
          state = 'position'
        elif state == 'position':
          if line == '<position>':
            try:
              posx = get_xml_type(ifile.next().strip(), 'posx', 'float') * self.window_size[0] / 640.0
              posy = get_xml_type(ifile.next().strip(), 'posy', 'float') * self.window_size[1] / 480.0
              time = get_xml_type(ifile.next().strip(), 'time', 'float') * self.window_size[1] / 1000.0
              self.position.append((time, (posx,posy), self.window_size))
              if ifile.next().strip() != '</position>': raise 'Bad wbx: expected </position>'
            except (ValueError, StopIteration):
              raise 'Bad wbx: expected posx, posy, time'
          elif line == '</positions>':
            state = '/document'
          else:
            raise 'Bad wbx: expected <position>...</position> or </positions>'
        elif state == '/document':
          if line != '</document>': raise 'Bad wbx: expected </document>'
          state = 'done'
        elif state == 'done':
          if len(line) > 0:
            print "Warning, extra at end of file: %s" % line
    except StopIteration:
      pass
    ifile.close()

# Each point is a tuple containing:
#     a time stamp, (x,y) position tuple, radius, color, and (w,h) window size tuple.

  def openRAW(self, fname = 'strokes.wbr'):
    print "I don't know how to open raw files yet ..."

  def openTXT(self, fname = 'strokes.wbt'):
    print "I don't know how to open text files yet ..."

  def dirtyOK(self):
    d = gtk.MessageDialog(None, 0, gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO,
        "You have unsaved changes.  Are you sure you want to continue?")
    ok = d.run() == gtk.RESPONSE_YES
    d.destroy()
    return ok

class Whiteboard:
  def __init__(self, gladefile, audioenabled=True):
    if not audioenabled: print "Audio not supported."

    self.WidgetTree = gtk.glade.XML(gladefile)
    self.MainWindow = self.WidgetTree.get_widget("mainwindow")
    self.DrawingFrame = self.WidgetTree.get_widget("vbox1")

    self.DrawingArea = DrawingTestWidget()
    self.DrawingArea.show()
    self.DrawingFrame.add(self.DrawingArea)

    self.WidgetTree.get_widget("clear").connect("clicked",
        lambda x: self.DrawingArea.clear())

    # playback
    self.WidgetTree.get_widget("record").connect("clicked",
        lambda x: x.record())
    self.WidgetTree.get_widget("play").connect("clicked",
        lambda x: self.DrawingArea.play(time.time()))
    self.WidgetTree.get_widget("pause").connect("clicked",
        lambda x: self.DrawingArea.pause(time.time()))
    self.WidgetTree.get_widget("stop").connect("clicked",
        lambda x: self.DrawingArea.stop())

    # pen widths
    self.WidgetTree.get_widget("thin").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setRadius(1.5))
    self.WidgetTree.get_widget("medium").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setRadius(3.0))
    self.WidgetTree.get_widget("thick").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setRadius(6.0))

    # colors
    self.WidgetTree.get_widget("black").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setColor(0.0, 0.0, 0.0))
    self.WidgetTree.get_widget("blue").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setColor(0.0, 0.0, 1.0))
    self.WidgetTree.get_widget("red").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setColor(1.0, 0.0, 0.0))
    self.WidgetTree.get_widget("green").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setColor(0.0, 1.0, 0.0))
    self.WidgetTree.get_widget("gray").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setColor(0.5, 0.5, 0.5))
    self.WidgetTree.get_widget("cyan").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setColor(0.0, 1.0, 1.0))
    self.WidgetTree.get_widget("lime").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setColor(0.3, 1.0, 0.5))
    self.WidgetTree.get_widget("magenta").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setColor(1.0, 0.0, 1.0))
    self.WidgetTree.get_widget("orange").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setColor(1.0, 0.5, 0.0))
    self.WidgetTree.get_widget("yellow").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setColor(1.0, 1.0, 0.0))
    self.WidgetTree.get_widget("white").connect("toggled",
        lambda x: x.get_active() and self.DrawingArea.setColor(1.0, 1.0, 1.0))

    # other soup
    self.MainWindow.connect("delete-event", lambda x,y: sys.exit(0))

    self.WidgetTree.get_widget("file/new").connect("activate",
        lambda x: self.DrawingArea.reset())
    self.WidgetTree.get_widget("file/open").connect("activate",
        lambda x: self.DrawingArea.open())
    self.WidgetTree.get_widget("file/save").connect("activate",
        lambda x: self.DrawingArea.save())
    self.WidgetTree.get_widget("file/save-as").connect("activate",
        lambda x: self.DrawingArea.save())

    self.WidgetTree.get_widget("open").connect("clicked",
        lambda x: self.DrawingArea.open())
    if audioenabled:
      self.WidgetTree.get_widget("file/quit").connect("activate",
          lambda x: (os.kill(self.AudioSaviorPID, signal.SIGTERM), sys.exit(0)))
      self.WidgetTree.get_widget("quit").connect("clicked",
          lambda x: (os.kill(self.AudioSaviorPID, signal.SIGTERM), sys.exit(0)))
      self.WidgetTree.get_widget("save").connect("clicked",
          lambda x: (self.DrawingArea.save(), os.kill(self.AudioSaviorPID, signal.SIGUSR1)))
    else:
      self.WidgetTree.get_widget("file/quit").connect("activate",
          lambda x: sys.exit(0))
      self.WidgetTree.get_widget("new").connect("clicked",
          lambda x: self.DrawingArea.reset())
      self.WidgetTree.get_widget("save").connect("clicked",
          lambda x: self.DrawingArea.save())
    self.WidgetTree.get_widget("quit").connect("clicked",
        lambda x: sys.exit(0))

    self.DrawingArea.set_extension_events(gtk.gdk.EXTENSION_EVENTS_ALL)

    if audioenabled:
      self.AudioSaviorPID = os.fork()
      if self.AudioSaviorPID == 0:
        a = audiosavior.AudioSavior()
        signal.signal(signal.SIGUSR1, lambda signum, frame: a.save())
        a.record()

  def Run(self):
    self.MainWindow.show()
    try:
      gtk.main()
    except KeyboardInterrupt:
#      os.kill(self.AudioSaviorPID, signal.SIGTERM)
      pass
    self.MainWindow.hide()

if __name__ == '__main__':
  wb = Whiteboard("layout.glade", audio)
  wb.Run()
