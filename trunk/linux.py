# for the GUI
import pygtk
pygtk.require('2.0')
import gtk
import gobject
import cairo

# for audio
import alsaaudio

# for both
import time
import math
import sys

import deskcorder as dc

class Canvas(gtk.DrawingArea):
  def __init__(self):
    gtk.DrawingArea.__init__(self)

    self.radius = 3.0
    self.drawing = False
    self.size = None
    self.raster = None
    self.raster_cr = None
    self.color = (0.0, 0.0, 0.0)
    self.ttpt = -1

    # Keeps track of whether the state of the canvas is reflected in a file
    # somewhere or not.  If not, this is dirty.
    self.dirty = False

    # This won't accept mouse events when frozen.  Useful for when the
    # Deskcorder is playing back the contents of the Canvas and the
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
    self.trace = dc.Trace(time.time())

    # Not nearly as complex as trace.
    #
    # This is a list of points.  Each point is a tuple of time, (x,y) position
    # tuple, and (w,h) window size tuple.
    self.positions = []

    self.set_events(gtk.gdk.POINTER_MOTION_MASK  | gtk.gdk.BUTTON_MOTION_MASK | gtk.gdk.BUTTON1_MOTION_MASK | gtk.gdk.BUTTON2_MOTION_MASK | gtk.gdk.BUTTON3_MOTION_MASK | gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK)

    self.connect("configure-event", lambda w, e: self.draw_all())
    self.connect("expose-event", lambda w, e: self.gtk_expose())
    self.connect("motion-notify-event", self.gtk_motion)
    self.connect("button-press-event", self.gtk_button_press)
    self.connect("button-release-event", self.gtk_button_release)

    self.set_size_request(800,600)

  def get_time_of_first_event(self):
    self.trace.get_time_of_first_event()

  def freeze(self):
    self.frozen = True

  def unfreeze(self):
    self.frozen = False

  def draw_last_slide(self):
    for stroke in self.trace.last():
      self.draw(stroke.color, stroke[0].p, stroke[0].pos)
      if len(stroke) > 1:
        self.draw(stroke.color, stroke[1].p, stroke[0].pos, stroke[1].pos)
      for i in xrange(len(stroke)-2):
        self.draw(stroke.color, stroke[i+2].p,
          stroke[i].pos, stroke[i+1].pos, stroke[i+2].pos)

  def draw_to_ttpt(self):
    stroke = None
    for i in xrange(len(self.trace)):
      if self.trace[i].t < self.ttpt and self.ttpt < self.trace[i+1]:
        stroke = self.trace[i]
        break

    for stroke in self.trace[i]:
      if len(stroke) > 1:
        if stroke[1].t < self.ttpt:
          self.draw(stroke.color, stroke[0].p, stroke[0].pos, stroke[1].pos)
        for i in xrange(len(stroke)-2):
          if stroke[i].t < self.ttpt:
            self.draw(stroke.color, stroke[i].p, stroke[i].pos, stroke[i+1].pos, stroke[i+2].pos)
          else:
            return

  def draw_all(self):
    self.size = self.window.get_size()
    self.raster = self.window.cairo_create().get_target().create_similar(cairo.CONTENT_COLOR, self.size[0], self.size[1])
    self.raster_cr = cairo.Context(self.raster)
    self.raster_cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
    self.raster_cr.rectangle(0.0, 0.0, self.size[0], self.size[1])
    self.raster_cr.fill()
    if self.ttpt >= 0:
      self.draw_to_ttpt()
    else:
      self.draw_last_slide()
    self.refresh()

  def get_pressure_or_default(self, device, default = None):
    trace = device.get_state(self.window)
    p = device.get_axis(trace[0], gtk.gdk.AXIS_PRESSURE)
    return default if default is not None and p is None else p

  def gtk_button_press(self, widget, event):
    if not self.frozen:
      self.dirty = True
      self.drawing = True
      self.trace.last().append(self.color)

  def gtk_motion(self, widget, event):
    if not self.frozen:
      pos = event.get_coords()
      pos = (pos[0] / float(self.size[0]), pos[1] / float(self.size[1]))
      if self.drawing:
        self.dirty = True
        p = self.get_pressure_or_default(event.device, .5)
        r = (p * 2 + 0.2) * self.radius / math.sqrt(self.size[0]**2 + self.size[1]**2)
        if len(self.trace.last().last()) > 1:
          self.draw(self.color, r, self.trace[-1][-1][-2].pos, self.trace[-1][-1][-1].pos, pos)
        elif len(self.trace.last().last()) > 0:
          self.draw(self.color, r, self.trace[-1][-1][-1].pos, pos)
        else:
          self.draw(self.color, r, pos)
        self.trace.last().last().append(pos, time.time(), r)
      else:
        self.trace.add_move(pos, time.time())

  def gtk_button_release(self, widget, event):
    if not self.frozen:
      self.dirty = True
      self.drawing = False
      self.olderPos = None
      self.oldPos = None
      self.oldRad = None

  def gtk_expose(self):
    cr = self.window.cairo_create()
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

  def refresh(self):
    reg = gtk.gdk.Region()
    reg.union_with_rect((0, 0, self.size[0], self.size[1]))
    self.window.invalidate_region(reg, False)

  def reset(self):
    self.clear()
    self.trace = dc.Trace(time.time())
    self.positions = []
    self.dirty = False
    self.frozen = False

  def redraw(self):
    self.clear()
    self.draw_all()

  def draw(self, color, r, pos1, pos2=None, pos3=None):
    self.raster_cr.set_source_rgba(color[0], color[1], color[2], 1.0)
    reg = gtk.gdk.Region()
    r = r * math.sqrt(self.size[0]**2 + self.size[1]**2)
    pos1 = (pos1[0] * self.size[0], pos1[1] * self.size[1])
    if pos2 is not None:
      pos2 = (pos2[0] * self.size[0], pos2[1] * self.size[1])
    if pos3 is not None:
      pos3 = (pos3[0] * self.size[0], pos3[1] * self.size[1])
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

class ExportDialog(gtk.Dialog):
  def __init__(self):
    gtk.Dialog.__init__(self)

  def run(self):
    return 0

class GUI:
  def __init__(self):
    # Set up most of the window (from XML file).
    if True:
      self.builder = gtk.Builder()
      self.builder.add_from_file('layout.gtk')
      self.get_fun = self.builder.get_object
    else:
      self.glade_tree = gtk.glade.XML('layout.glade')
      self.get_fun = self.glade_tree.get_widget

    self.root = self.get_fun("root")
    self.root.connect("destroy", lambda x: sys.exit(0))

    # Add the canvas, too.
    self.canvas = Canvas()
    self.canvas.show()
    self.get_fun("vbox1").add(self.canvas)
    self.get_fun("clear").connect("clicked",
        lambda x: self.canvas.clear())

    self.last_fname = None

    # playback
    self.record_button = self.get_fun("record")
    self.play_button = self.get_fun("play")
    self.pause_button = self.get_fun("pause")
    self.stop_button = self.get_fun("stop")
    self.progress_bar = self.get_fun("progress-bar")
    self.pback_await = self.get_fun("playback/await")

    # import/export
    self.get_fun('file/exp-png').connect("activate",
        lambda x: self.exp_png())
    self.get_fun('file/exp-pdf').connect("activate",
        lambda x: self.exp_pdf())

    # pen widths
    self.get_fun("thin").connect("toggled",
        lambda x: x.get_active() and self.canvas.setRadius(1.5))
    self.get_fun("medium").connect("toggled",
        lambda x: x.get_active() and self.canvas.setRadius(3.0))
    self.get_fun("thick").connect("toggled",
        lambda x: x.get_active() and self.canvas.setRadius(6.0))

    # colors
    self.get_fun("black").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(0.0, 0.0, 0.0))
    self.get_fun("blue").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(0.0, 0.0, 1.0))
    self.get_fun("red").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(1.0, 0.0, 0.0))
    self.get_fun("green").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(0.0, 1.0, 0.0))
    self.get_fun("gray").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(0.5, 0.5, 0.5))
    self.get_fun("cyan").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(0.0, 1.0, 1.0))
    self.get_fun("lime").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(0.3, 1.0, 0.5))
    self.get_fun("magenta").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(1.0, 0.0, 1.0))
    self.get_fun("orange").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(1.0, 0.5, 0.0))
    self.get_fun("yellow").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(1.0, 1.0, 0.0))
    self.get_fun("white").connect("toggled",
        lambda x: x.get_active() and self.canvas.setColor(1.0, 1.0, 1.0))

    self.root.connect("delete-event", lambda x,y: gtk.main_quit())

    self.get_fun("edit/add").connect("activate",
        lambda x: self.canvas.clear())
    self.get_fun("add").connect("clicked",
        lambda x: self.canvas.clear())
    self.get_fun("file/open").connect("activate",
        lambda x: self.open())
    self.get_fun("open").connect("clicked",
        lambda x: self.open())
    self.get_fun("file/save").connect("activate",
        lambda x: self.save())
    self.get_fun("save").connect("clicked",
        lambda x: self.save())
    self.get_fun("file/save-as").connect("activate",
        lambda x: self.save_as())
    self.get_fun("file/quit").connect("activate", self.quit)
    self.get_fun("quit").connect("clicked", self.quit)

    self.save_fun = None
    self.open_fun = None
    self.exp_pdf_fun = None
    self.exp_png_fun = None
    self.imp_pdf_fun = None

    self.canvas.set_extension_events(gtk.gdk.EXTENSION_EVENTS_ALL)

  def quit(self, event):
    if not self.canvas.dirty or self.dirty_quit_ok():
      gtk.main_quit()

  def set_fname(self, fname):
    if fname.rindex('/') >= 0:
      self.last_fname = fname[fname.rindex('/')+1:]
    else:
      self.last_fname = fname


  # -------- Import/Export dialogues.
  
  def exp_png(self):
    if self.exp_png_fun is None:
      self.int_err('Export to PNG functionality disabled.')
      return

    fcd = gtk.FileChooserDialog('Choose a file to epxort to', None,
        gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
          gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
    fcd.set_do_overwrite_confirmation(True)
    fcd.set_current_folder('saves')
    if self.last_fname is not None:
      fcd.set_current_name(self.last_fname[:-4] + '.png')
    else:
      fcd.set_current_name('save.png')
    self.add_filters(fcd)
    if fcd.run() == gtk.RESPONSE_ACCEPT:
      self.exp_png_fun(fcd.get_filename(), (800,600), None)
      fcd.destroy()
      return True
    fcd.destroy()
    return False

  def exp_pdf(self):
    if self.exp_pdf_fun is None:
      self.int_err('Export to PDF functionality disabled.')
      return

    fcd = gtk.FileChooserDialog('Choose a file to epxort to', None,
        gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
          gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
    fcd.set_do_overwrite_confirmation(True)
    fcd.set_current_folder('saves')
    if self.last_fname is not None:
      fcd.set_current_name(self.last_fname[:-4] + '.pdf')
    else:
      fcd.set_current_name('save.pdf')
    self.add_filters(fcd)
    if fcd.run() == gtk.RESPONSE_ACCEPT:
      self.exp_pdf_fun(fcd.get_filename(), (800,600), None)
      fcd.destroy()
      return True
    fcd.destroy()
    return False

  def imp_pdf(self):
    if self.exp_pdf_fun is None:
      self.int_err('Import from PDF functionality disabled.')
      return


  # -------- Load/Save dialogues.

  def open(self):
    if self.open_fun is None:
      self.int_err("Open functionality disabled.")
      return

    if self.canvas.dirty and not self.dirty_open_ok(): return
    fcd = gtk.FileChooserDialog('Choose a file to save', None,
        gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
          gtk.STOCK_OPEN, gtk.RESPONSE_ACCEPT))
    fcd.set_do_overwrite_confirmation(True)
    fcd.set_current_folder('saves')
    self.add_filters(fcd)
    if fcd.run() == gtk.RESPONSE_ACCEPT:
      self.last_fname = fcd.get_filename()
      self.open_fun(fcd.get_filename())
    fcd.destroy()

  def save(self):
    if self.save_fun is None:
      self.int_err("Save functionality disabled.")
      return

    if self.last_fname:
      self.save_fun(self.last_fname)
      return True
    else:
      return self.save_as()

  def save_as(self):
    if self.open_fun is None:
      self.int_err("Save-as functionality disabled.")
      return

    fcd = gtk.FileChooserDialog('Choose a file to save', None,
        gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
          gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
    fcd.set_do_overwrite_confirmation(True)
    fcd.set_current_folder('saves')
    fcd.set_current_name('save.dcb')
    self.add_filters(fcd)
    if fcd.run() == gtk.RESPONSE_ACCEPT:
      self.last_fname = fcd.get_filename()
      self.save_fun(fcd.get_filename())
      fcd.destroy()
      return True
    fcd.destroy()
    return False


  # ---------- Dialogs ------------------------------

  @staticmethod
  def add_filters(fcd):
    filters = [("DC binary", "*.dcb"),
               ("DC XML", "*.dcx"),
               ("DC text", "*.dct"),
               ("All DC Files", "*.dc[bxt]"),
               ('PDF files', '*.pdf'),
               ('PNG files', '*.png'),
               ("All files", "*.*")]
    for t in filters:
      f = gtk.FileFilter()
      f.set_name(t[0])
      f.add_pattern(t[1])
      fcd.add_filter(f)

  def dirty_quit_ok(self):
    return self.dirty_ok("Quit", 'quitting')

  def dirty_open_ok(self):
    return self.dirty_ok("Open", "opening another file")

  def dirty_new_ok(self):
    return self.dirty_ok("Continue", 'starting a new page')

  def dirty_ok(self, but, verb):
    '''Checks if it's okay that the canvas has unsaved changes on it.'''
    d = gtk.MessageDialog(None, 0, gtk.MESSAGE_WARNING, gtk.BUTTONS_NONE,
        'You have unsaved changes!  Would you like to save before %s?' % verb)
    d.add_buttons("Save", 0, "Cancel", 1, '%s without saving' % but, 2)
    d.set_default_response(1)
    rtn = d.run()
    d.destroy()
    if rtn == 0:
      if not self.save():
        return self.dirty_ok(but, verb)
      else:
        return True
    elif rtn == 1:
      return False
    elif rtn == 2:
      return True
    else:
      print 'Unknown button: %d' % rtn
      return False

  def int_err(self, msg):
    '''Internal error notification dialog box.'''
    d = gtk.MessageDialog(None, 0, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, 'Internal Error!  ' + msg)
    d.run()
    d.destroy()


  # -------- Callbacks ---------------------

  def connect_new(self, fun):
    self.get_fun("file/new").connect("activate", lambda x: fun())
    self.get_fun("new").connect("clicked", lambda x: fun())

  def connect_record(self, fun):
    self.record_button.connect("toggled", lambda w: fun(w.get_active()))
    self.get_fun("playback/record").connect("activate", lambda w:
        fun(self.record_button.get_active()))

  def connect_play(self, fun):
    self.play_button.connect("toggled", lambda w: fun(w.get_active()))
    self.get_fun("playback/play").connect("activate", lambda w:
        fun(self.play_button.get_active()))

  def connect_pause(self, fun):
    self.pause_button.connect("toggled", lambda w: fun(w.get_active()))
    self.get_fun("playback/pause").connect("activate", lambda w:
        fun(self.pause_button.get_active()))

  def connect_stop(self, fun):
    self.stop_button.connect("clicked", lambda w: fun())
    self.get_fun("playback/stop").connect("activate", lambda w: fun())

  def connect_exp_png(self, fun):
    self.exp_png_fun = fun

  def connect_exp_pdf(self, fun):
    self.exp_pdf_fun = fun

  def connect_save(self, fun):
    self.save_fun = fun

  def connect_open(self, fun):
    self.open_fun = fun

  def connect_progress_fmt(self, fun):
    self.progress_bar.connect("format-value", lambda s,v: fun(v))

  def connect_progress_moved(self, fun):
    self.progress_bar.connect("change-value", lambda w, t, v: fun(max(min(v, 1.), .0)))


  # ---- buttons -------------------------

  def record_pressed(self, state = None):
    if state is None:
      return self.record_button.get_active()
    else:
      self.record_button.set_active(state)

  def play_pressed(self, state = None):
    if state is None:
      return self.play_button.get_active()
    else:
      self.play_button.set_active(state)

  def pause_pressed(self, state = None):
    if state is None:
      return self.pause_button.get_active()
    else:
      self.pause_button.set_active(state)

  def audio_wait_pressed(self, state = None):
    if state is None:
      return self.pback_await.get_active()
    else:
      self.pback_await.set_active(state)

  def progress_slider_value(self, val = None):
    if val is None:
      print 'returning value'
      return self.progress_bar.get_value()
    else:
      self.progress_bar.set_value(val)
      self.progress_bar.queue_draw()

  def timeout_add(self, delay, fun):
    gobject.timeout_add(delay, fun)


  # ---- Up and down ---------------------

  def init(self):
    self.root.show()

  def run(self):
    gtk.main()

  def deinit(self):
    self.root.hide()
    self.root.destroy()



class InvalidOperationError(RuntimeError):
  def __init__(self, msg):
    RuntimeError.__init__(self, msg)

class Audio:
  def __init__(self):
    self.data = []  # K.I.S.S.  Data stored as a string.
    # next version: store an array of strings.  Do smart things to determine
    # when no one is talking.

    self.startTime = time.time()

    self.play_start = None
    self.recording = False
    self.paused = False

    self.rate = 44100
    self.channels = 1
    self.period_size = 1024
    self.format = alsaaudio.PCM_FORMAT_S16_LE
    self.bytes_per_second = self.rate * 2

    # Once it's init'd, it will start to collect data, so don't init it until
    # it's time to record.
    self.inp = None

    self.out = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK,alsaaudio.PCM_NONBLOCK)
    self.out.setchannels(self.channels)
    self.out.setrate(self.rate)
    self.out.setperiodsize(self.period_size)
    self.out.setformat(self.format)

  def make_data(self):
    data = []
    for d in self.data:
      data.append([d[0], ''])
      for p in d[1]:
        data[-1][1] += p
    return data

  def load_data(self, data):
    self.data = []
    for d in data:
      self.data.append([d[0], []])
      i1 = 0
      i2 = self.period_size
      while i1 < len(d[1]):
        self.data[-1][1].append(d[1][i1:i2])
        i1 = i2
        i2 += self.period_size

  def print_info(self):
    print 'Card name: %s' % a.inp.cardname()
    print ' PCM mode: %d' % a.inp.pcmmode()
    print ' PCM type: %d' % a.inp.pcmtype()

  def reset(self):
    self.data = []
    self.play_start = None
    self.recording = False
    self.paused = False

  def is_recording(self):
    return self.inp is not None

  def set_progress(self, t):
    if self.is_playing():
      self.stop()

    self.play_init()
    if len(self.data) <= 0:
      return

    self.pause()

    # "fake play" until we're at an appropriate time.
    while self.get_current_audio_start_time() + self.get_s_played() < t:
      self.per_iter += 1
      if self.per_iter >= len(self.data[self.data_iter][1]):
        self.per_iter = 0
        self.data_iter += 1
        if self.data_iter >= len(self.data):
          self.stop()
          return

  def record(self, t = None):
    '''Start recording.  This will not block.  It init's the recording process.
    This Audio will continue recording until stop() gets called.'''
    if self.is_playing():
      raise InvalidOperationError('Already playing.')

    if t is None: t = time.time()
    self.inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE,alsaaudio.PCM_NONBLOCK)
    self.inp.setchannels(self.channels)
    self.inp.setrate(self.rate)
    self.inp.setperiodsize(self.period_size)
    self.inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    self.data.append([t, []])
    self.recording = True
    gobject.timeout_add(100, self.record_tick)

  def record_tick(self):
    while self.recording:
      l,data = self.inp.read()
      # Drops 0-length data and data recorded while this is paused.
      if l > 0:
        if not self.paused:
          self.data[-1][1].append(data)
      else:
        return True
    else:
      return False

  def compress_data(self):
    '''Turns all list-type data into str-type.'''
    for i in xrange(len(self.data)):
      if type(self.data[i][1]) == list:
        for j in xrange(len(self.data[i][1]) - 1):
          k = j + 1
          while len(self.data[i][1][j]) < self.period_size:
            sz = self.period_size - len(self.data[i][1][j])
            self.data[i][1][j] += self.data[i][1][k][:sz]

  def play(self):
    if len(self.data) == 0 or len(self.data[0][1]) == 0:
      return
    self.play_init()
    gobject.timeout_add(100, self.play_tick)

  def play_init(self):
    self.compress_data()
    self.play_start = time.time()
    self.data_iter = 0
    self.per_iter = 0

  def play_tick(self, ttpt = None):
    '''ttpt == "time to play to" so that things will only play when they
    should.'''
    if self.is_playing():
      if self.paused: return True
      # This has the effect of a do-while loop that loops until no more data
      # can be written to the speakers.
      while ttpt is None or ttpt >= self.data[self.data_iter][0]:
        data = self.data[self.data_iter][1][self.per_iter]
        if self.out.write(data) != 0:
          self.per_iter += 1
          if self.per_iter >= len(self.data[self.data_iter][1]):
            self.per_iter = 0
            self.data_iter += 1
            if self.data_iter >= len(self.data):
              self.stop()
              return False
        else:
          return self.is_playing()
      return self.is_playing()
    else:
      return False

  def is_playing(self):
    return self.play_start is not None

  def get_s_played(self):
    '''Computes and returns number of seconds played in this recording.'''
    if self.is_playing() and len(self.data) > 0 and self.per_iter != 0:
      return self.period_size * self.per_iter / float(self.bytes_per_second)
    else:
      return -1

  def get_time_of_first_event(self):
    return self.data[0][0] if len(self.data) > 0 else -1

  def get_time_of_last_event(self):
    return (self.data[-1][0] + (self.period_size * len(self.data[-1][1]) / float(self.bytes_per_second))) if len(self.data) else 0

  def get_current_audio_start_time(self):
    try:
      return self.data[self.data_iter][0]
    except IndexError:
      return -1

  def pause(self):
    self.paused = True

  def unpause(self):
    self.paused = False

  def stop(self):
    self.paused = False
    self.recording = False
    self.play_start = None
    if self.inp is not None:
      self.inp.close()
      self.inp = None
