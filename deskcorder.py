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
import recorder
try:
  import alsa
  audio = True
except ImportError:
  audio = False

#class Trace:
#  def __init__(self, times, slides):
#    if type(times)  != list: raise 'times not list'
#    if type(slides) != list: raise 'slides not list'
#    if len(times) != len(slides):
#      raise 'Different amount of slides and times'
#
#    self.data = [None] * len(times) * 2
#    for i in range(len(times)):
#      self.data.append(times[i])
#      self.data.append(slides[i])
#
#  def get_clear_time(self, i):
#    return self.data[i*2]
#
#  def __len__(self):
#    return len(self.data) / 2
#
#  def get_slide(self, i):
#    return self.data[i*2+1]
#
#  def append(self, data):
#    return self.data.append(data)
#
#  def slides(self):
#    slides = []
#    for s in self.data:
#      if type(s) == list:
#        slides.append(s)
#    return slides
#
#  def clear_times(self):
#    times = []
#    for s in self.data:
#      if type(s) != list:
#        times.append(s)
#    return times

#class State:
#  class Iter:
#    def __init__(self, i = 0, j = 0, k = 0):
#      self.i = i
#      self.j = j
#      self.k = k
#
#  def __init__(self, data = []):
#    '''Initialize a blank state object.  If you have internal data (formerly
#    known as a "trace"), then you can just pass that here.'''
#    if type(data) != list:
#      raise :e 
#    self.data = data
#
#  def __getitem__(self, it = Iter()):
#    pass
#
#  def __delitem


class GtkCanvas(gtk.DrawingArea):
  def __init__(self):
    gtk.DrawingArea.__init__(self)

    self.radius = 3.0
    self.drawing = False
    self.size = None
    self.raster = None
    self.raster_cr = None
    self.color = (0.0, 0.0, 0.0)

    # Keeps track of whether the state of the canvas is reflected in a file
    # somewhere or not.  If not, this is dirty.
    self.dirty = False

    # This won't accept mouse events when frozen.  Useful for when the
    # Deskcorder is playing back the contents of the GtkCanvas and the
    # Audio.
    self.frozen = False

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

    # Not nearly as complex as trace.
    #
    # This is a list of points.  Each point is a tuple of time, (x,y) position
    # tuple, and (w,h) window size tuple.
    self.positions = []

    self.set_events(gtk.gdk.POINTER_MOTION_MASK  | gtk.gdk.BUTTON_MOTION_MASK | gtk.gdk.BUTTON1_MOTION_MASK | gtk.gdk.BUTTON2_MOTION_MASK | gtk.gdk.BUTTON3_MOTION_MASK | gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK)

    self.connect("configure-event", self.gtk_configure)
    self.connect("expose-event", self.gtk_expose)
    self.connect("motion-notify-event", self.gtk_motion)
    self.connect("button-press-event", self.gtk_button_press)
    self.connect("button-release-event", self.gtk_button_release)
    self.set_size_request(800,600)

  def get_time_of_first_event(self):
    for e in trace[1:]:
      if type(e) == list:
        if len(e) > 0:
          for stroke in e:
            if len(stroke) > 0:
              return stroke[0][0]
      else:
        return e
    return -1

  def freeze(self):
    self.frozen = True

  def unfreeze(self):
    self.frozen = False

  def gtk_configure(self, widget, event):
    self.size = self.window.get_size()
    self.raster = self.window.cairo_create().get_target().create_similar(cairo.CONTENT_COLOR, self.size[0], self.size[1])
    self.raster_cr = cairo.Context(self.raster)
    self.raster_cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
    self.raster_cr.rectangle(0.0, 0.0, self.size[0], self.size[1])
    self.raster_cr.fill()
    for curve in self.trace[-1]:
      self.draw(curve[0][3], curve[0][2],
          ((curve[0][1][0]*self.size[0])/curve[0][4][0],
           (curve[0][1][1]*self.size[1])/curve[0][4][1]))
      if len(curve) > 1:
        self.draw(curve[1][3], curve[1][2],
          ((curve[0][1][0]*self.size[0])/curve[1][4][0],
           (curve[0][1][1]*self.size[1])/curve[1][4][1]),
          ((curve[1][1][0]*self.size[0])/curve[1][4][0],
           (curve[1][1][1]*self.size[1])/curve[1][4][1])
        )
      for i in xrange(len(curve)-2):
        self.draw(curve[i+2][3], curve[i+2][2],
          ((curve[i  ][1][0]*self.size[0])/curve[i+2][4][0],
           (curve[i  ][1][1]*self.size[1])/curve[i+2][4][1]),
          ((curve[i+1][1][0]*self.size[0])/curve[i+2][4][0],
           (curve[i+1][1][1]*self.size[1])/curve[i+2][4][1]),
          ((curve[i+2][1][0]*self.size[0])/curve[i+2][4][0],
           (curve[i+2][1][1]*self.size[1])/curve[i+2][4][1])
        )
    self.refresh()

  def get_pressure(self, device):
    trace = device.get_state(self.window)
    return device.get_axis(trace[0], gtk.gdk.AXIS_PRESSURE)

  def gtk_motion(self, widget, event):
    if not self.frozen:
      pos = event.get_coords()
      if self.drawing:
        self.dirty = True
        p = self.get_pressure(event.device)
        if p is None:
          p = 1.0
        r = (p * 2 + 0.2)*self.radius
        if len(self.trace[-1][-1]) > 1:
          self.draw(self.color, r, self.trace[-1][-1][-2][1], self.trace[-1][-1][-1][1], pos)
        elif len(self.trace[-1][-1]) > 0:
          self.draw(self.color, r, self.trace[-1][-1][-1][1], pos)
        else:
          self.draw(self.color, r, pos)
        self.trace[-1][-1].append((time.time(), pos, r, self.color, self.size))
      else:
        self.positions.append((time.time(), pos, self.size))

  def gtk_button_press(self, widget, event):
    if not self.frozen:
      self.dirty = True
      self.drawing = True
      self.trace[-1].append([])

  def gtk_button_release(self, widget, event):
    if not self.frozen:
      self.dirty = True
      self.drawing = False
      self.olderPos = None
      self.oldPos = None
      self.oldRad = None

  def gtk_expose(self, widget, event):
    cr = widget.window.cairo_create()
    cr.set_source_surface(self.raster, 0.0, 0.0)
    cr.paint()
    cr.set_line_width(2)
    cr.set_source_rgba(0.0, 0.0, 0.0, 0.25)
    cr.rectangle(0.0, 0.0, self.size[0], self.size[1])
    cr.stroke()

  def setRadius(self, rad):
    self.radius = rad

  def setColor(self, r, g, b):
    self.color = (r,g,b)

  def clear(self):
    self.size = self.window.get_size()
    self.raster_cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
    self.raster_cr.rectangle(0.0, 0.0, self.size[0], self.size[1])
    self.raster_cr.fill()
    self.refresh()
    if not self.frozen:
      self.trace.append(time.time())
      self.trace.append([])

  def refresh(self):
    reg = gtk.gdk.Region()
    reg.union_with_rect((0, 0, self.size[0], self.size[1]))
    self.window.invalidate_region(reg, False)

  def reset(self):
    self.clear()
    self.trace = [time.time(), []]
    self.positions = []
    self.dirty = False
    self.frozen = False

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

class Deskcorder:
  def __init__(self, gladefile, audioenabled=True):
    # Playback variables.
    self.play_time = None
    self.play_timer_id = None
    self.break_times = []
    self.last_pause = None

    # Set up most of the window (from glade file).
    self.glade_tree = gtk.glade.XML(gladefile)
    self.root = self.glade_tree.get_widget("mainwindow")

    # Add the canvas, too.
    self.canvas = GtkCanvas()
    self.canvas.show()
    self.glade_tree.get_widget("vbox1").add(self.canvas)

    self.glade_tree.get_widget("clear").connect("clicked",
        lambda x: self.canvas.clear())

    # playback
    self.record_button = self.glade_tree.get_widget("record")
    self.play_button = self.glade_tree.get_widget("play")
    self.pause_button = self.glade_tree.get_widget("pause")
    self.stop_button = self.glade_tree.get_widget("stop")
    self.play_button.connect("toggled", lambda x: self.play(time.time()))
    self.pause_button.connect("toggled", lambda x: self.pause(time.time()))
    self.stop_button.connect("clicked", lambda x: self.stop())

    # Set up audio (or not).
    self.audioenabled = audioenabled
    if audioenabled:
      self.audio = alsa.Audio()
      self.record_button.connect("toggled", lambda x: self.record())
    else:
      print "Audio disabled."

    # pen widths
    self.glade_tree.get_widget("thin").connect("toggled",
        lambda x: x.get_active() and self.canvas.setRadius(1.5))
    self.glade_tree.get_widget("medium").connect("toggled",
        lambda x: x.get_active() and self.canvas.setRadius(3.0))
    self.glade_tree.get_widget("thick").connect("toggled",
        lambda x: x.get_active() and self.canvas.setRadius(6.0))

    # colors
    self.glade_tree.get_widget("black").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(0.0, 0.0, 0.0))
    self.glade_tree.get_widget("blue").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(0.0, 0.0, 1.0))
    self.glade_tree.get_widget("red").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(1.0, 0.0, 0.0))
    self.glade_tree.get_widget("green").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(0.0, 1.0, 0.0))
    self.glade_tree.get_widget("gray").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(0.5, 0.5, 0.5))
    self.glade_tree.get_widget("cyan").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(0.0, 1.0, 1.0))
    self.glade_tree.get_widget("lime").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(0.3, 1.0, 0.5))
    self.glade_tree.get_widget("magenta").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(1.0, 0.0, 1.0))
    self.glade_tree.get_widget("orange").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(1.0, 0.5, 0.0))
    self.glade_tree.get_widget("yellow").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(1.0, 1.0, 0.0))
    self.glade_tree.get_widget("white").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(1.0, 1.0, 1.0))

    # other soup
    self.root.connect("delete-event", lambda x,y: sys.exit(0))

    self.glade_tree.get_widget("file/new").connect("activate",
        lambda x: self.reset())
    self.glade_tree.get_widget("edit/add").connect("activate",
        lambda x: self.canvas.clear())
    self.glade_tree.get_widget("file/open").connect("activate",
        lambda x: self.open())
    self.glade_tree.get_widget("file/save").connect("activate",
        lambda x: self.save())
    self.glade_tree.get_widget("file/save-as").connect("activate",
        lambda x: self.save())


    self.glade_tree.get_widget("new").connect("clicked",
        lambda x: self.reset())
    self.glade_tree.get_widget("add").connect("clicked",
        lambda x: self.canvas.clear())
    self.glade_tree.get_widget("open").connect("clicked",
        lambda x: self.open())
    self.glade_tree.get_widget("file/quit").connect("activate",
        lambda x: sys.exit(0))
    self.glade_tree.get_widget("quit").connect("clicked",
        lambda x: sys.exit(0))
    self.glade_tree.get_widget("save").connect("clicked",
        lambda x: self.save())

    self.canvas.set_extension_events(gtk.gdk.EXTENSION_EVENTS_ALL)

  def run(self, fname = None):
    '''Runs the program.'''
    self.root.show()
    try:
      if fname != None:
        if fname.endswith(".dcb"):
          self.load_dcb(fname)
        elif fname.endswith(".dcx"):
          self.load_dcx(fname)
        else:
          self.load_dct(fname)
    except IOError as e:
      print 'Error: %s"' % e.message

    try:
      gtk.main()
    except KeyboardInterrupt:
      pass
    self.root.hide()

  def reset(self):
    '''Clears the state of the canvas and audio, as if the system had just
    started.'''
    if not self.canvas.dirty or self.dirty_ok():
      self.canvas.reset()
      self.audio.reset()

  def is_recording(self):
    return self.record_button.get_active()

  def record(self):
    '''Starts the mic recording.'''
    if self.is_recording():
      try:
        self.audio.record()
      except recorder.InvalidOperationError:
        self.record_button.set_active(False)
    else:
      self.audio.stop()

  def is_playing(self):
    '''Determines if this is playing or not.'''
    return self.play_time is not None

  def play(self, t):
    '''Start/stop playing what's in this file.'''
    if not self.play_button.get_active():
      self.stop()
      return

    if self.is_recording():
      self.stop()
      self.play_button.set_active(True)

    if self.is_playing():
      if self.is_paused():
        self.pause(t)
      return

    self.canvas.freeze()
    if self.audioenabled:
      self.audio.play_init()
    self.play_time = t
    self.slide_i = 0
    self.curve_i = 0
    self.point_i = 0
    self.play_timer_id = gobject.timeout_add(100, self.play_tick)

  def play_tick(self):
    '''Do one 'tick' in the process of playing back what's stored in this
    program.'''
    if not self.is_playing(): return False
    if self.is_paused(): return True

    # dt is the difference between when the trace was recorded and when the
    # play button was hit.
    dt = self.play_time - self.canvas.trace[0]
    for pause in self.break_times:
      dt += pause[1] - pause[0]

    now = time.time()

    if self.audioenabled and self.audio.is_playing():
      a_start = self.audio.get_current_audio_start_time()
      a_time = self.audio.get_s_played()
      if a_start >= 0:
        self.audio.play_tick(now - dt)
        if a_time >= 0:
          dt = a_start + dt + a_time - now + dt

    # I'm simulating a do-while loop here.  This one is basically:
    #  1. While we still have stuff to iterate over, iterate.
    #  2. While the thing our iterator is pointing at is still old enough to
    #     draw, draw it.
    #  3. When we can't draw any more because the point our iterator is
    #     pointed at is too old, return True (run the function again later).
    #  4. When out iterator goes past the end of the trace object, return
    #     false (stop calling this function).
    while True:
      slide = self.canvas.trace[self.slide_i]
      if type(slide) == float:
        if slide + dt <= now:
          self.canvas.clear()
        else:
          return True
      elif type(slide) == list:
        if len(slide) > 0:
          curve = slide[self.curve_i]
          if len(curve) > 0:
            point = curve[self.point_i]
            radius = point[2]
            color = point[3]
            if point[0] + dt <= now:
              if self.point_i > 1:
                self.canvas.draw(color, radius, curve[self.point_i-2][1], curve[self.point_i-1][1], curve[self.point_i][1])
              elif self.point_i > 0:
                self.canvas.draw(color, radius, curve[self.point_i-1][1], curve[self.point_i][1])
              else:
                self.canvas.draw(color, radius, curve[self.point_i][1])
            else:
              return True
      else:
        print 'Warning, unknown type: %s' % type(slide)

      if not self.play_iters_inc():
        if not self.audioenabled or self.audio.get_current_audio_start_time() < 0:
          self.stop()
          return False
        return True


  def play_iters_inc(self):
    '''Increments all the iterators that have to do with the playing
    process.'''
    if len(self.canvas.trace) > 0:
      if type(self.canvas.trace[self.slide_i]) == list and len(self.canvas.trace[self.slide_i]) > 0:
        self.point_i += 1
        if self.point_i < len(self.canvas.trace[self.slide_i][self.curve_i]):
          return True
        self.point_i = 0

        self.curve_i += 1
        if self.curve_i < len(self.canvas.trace[self.slide_i]):
          return True
        self.curve_i = 0

      self.slide_i += 1
      if self.slide_i < len(self.canvas.trace):
        return True

    self.slide_i = 0
    self.curve_i = 0
    self.point_i = 0
    return False

  def pause(self, t):
    '''Pauses playback and audio recording.'''
    if self.is_playing():
      if self.last_pause == None:
        self.last_pause = t
        self.pause_button.set_active(True)
        if self.audioenabled:
          self.audio.pause()
      else:
        self.break_times.append((self.last_pause, t))
        self.last_pause = None
        self.pause_button.set_active(False)
        if self.audioenabled:
          self.audio.unpause()
    else:
      self.pause_button.set_active(False)


  def is_paused(self):
    return self.last_pause is not None

  def done(self):
    '''The drawing portion is done playing back.  Wait for the speech portion
    to finish also.'''
    if self.audioenabled:
      gobject.timeout_add(100, self.check_done)
    else:
      self.stop()

  def check_done(self):
    if not self.audio.is_playing():
      self.stop()
      return False
    return True

  def stop(self):
    if self.audioenabled:
      self.audio.stop()
      self.audio.compress_data()
    if self.is_paused():
      self.pause(time.time())
    self.record_button.set_active(False)
    self.play_button.set_active(False)
    self.canvas.unfreeze()
    self.play_time = None
    self.play_timer_id = None
    self.last_pause = None
    self.break_times = []
    self.audio.stop()



  ############################################################################
  # ------------------------------ File I/O -------------------------------- #
  ############################################################################

  def save(self, fname = 'save.dcb', graphical = True):
    if graphical:
      if self.is_recording(): self.record()
      fcd = gtk.FileChooserDialog('Choose a file to save', None,
          gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
      fcd.set_do_overwrite_confirmation(True)
      fcd.set_current_folder('saves')
      fcd.set_current_name(fname)

    if not graphical or fcd.run() == gtk.RESPONSE_ACCEPT:
      if graphical:
        fname = fcd.get_filename()

      if fname.lower().endswith(".dcx"):
        self.save_dcx(fname)
      elif fname.lower().endswith(".dct"):
        self.save_dct(fname)
      else:
        self.save_dcb(fname)
      self.canvas.dirty = False

    if graphical:
      fcd.destroy()

  def get_audio_data(self):
    '''Convenience function that returns the audio data or [] if audio is
    disabled.'''
    return self.audio.data if self.audioenabled else []

  def save_dcx(self, fname = "strokes.dcx"):
    recorder.save_dcx(fname, self.canvas.trace, self.canvas.positions, self.get_audio_data())

  def save_dct(self, fname = "strokes.dct"):
    recorder.save_dct(fname, self.canvas.trace)

  def save_dcb(self, fname = "strokes.dcb"):
    recorder.save_dcb(fname, self.canvas.trace, self.canvas.positions, self.get_audio_data())

  def errorMessageDialog(self, msg):
    d = gtk.MessageDialog(None, 0, gtk.MESSAGE_WARNING, gtk.BUTTONS_OK, msg)
    d.run()
    d.destroy()

  def open(self, fname = 'save.dcb', graphical = True):
    if graphical:
      if self.canvas.dirty and not self.dirty_ok(): return
      if fname == None: fname = 'save.dcx'
      fcd = gtk.FileChooserDialog('Choose a file to save', None,
          gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_OPEN, gtk.RESPONSE_ACCEPT))
      fcd.set_do_overwrite_confirmation(True)
      fcd.set_current_folder('saves')
      fcd.set_current_name(fname)

    if not graphical or fcd.run() == gtk.RESPONSE_ACCEPT:
      if graphical:
        fname = fcd.get_filename()

      if fname.lower().endswith('.dcx'):
        self.load_dcx(fname)
      elif fname.lower().endswith('.dct'):
        self.load_dct(fname)
      else:
        self.load_dcb(fname)
      self.canvas.dirty = False

    if graphical:
      fcd.destroy()

  def load_dcb(self, fname = 'save.dcb'):
    self.canvas.trace, self.canvas.positions, self.audio.data = \
        recorder.load_dcb(fname, self.canvas.size)

  def load_dcx(self, fname = 'save.dcx'):
    self.canvas.trace, self.canvas.positions, self.audio.data = \
        recorder.load_dcx(fname, self.canvas.size)

  def load_dct(self, fname = 'save.dcx'):
    self.canvas.trace, self.canvas.positions, self.audio.data = \
        recorder.load_dct(fname, self.canvas.size)

  def dirty_ok(self):
    '''Checks if it's okay that the canvas has unsaved changes on it.'''
    d = gtk.MessageDialog(None, 0, gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO,
        "You have unsaved changes.  Are you sure you want to continue?")
    ok = (d.run() == gtk.RESPONSE_YES)
    d.destroy()
    return ok



##############################################################################
# -------------------------- Testing/Running ------------------------------- #
##############################################################################

if __name__ == '__main__':
  fname = None
  if len(sys.argv) > 1:
    if sys.argv[1] == '-h' or sys.argv[1] == '--help':
      print 'Usage %s [-A|--no-audio]'
    elif sys.argv[1] == '-A' or sys.argv[1] == '--no-audio':
      audio = False
    elif sys.argv[1].startswith('--open='):
      fname = sys.argv[1][7:]
    else:
      print 'Unrecognized command: "%s"' % sys.argv[1]
  d = Deskcorder("layout.glade", audio)
  d.run(fname)
