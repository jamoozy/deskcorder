import pygtk
pygtk.require('2.0')
import gtk
import gtk.glade
import gobject
import cairo

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

    self.connect("configure-event", self.gtk_configure)
    self.connect("expose-event", self.gtk_expose)
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

  def gtk_configure(self, widget, event):
    self.size = self.window.get_size()
    self.raster = self.window.cairo_create().get_target().create_similar(cairo.CONTENT_COLOR, self.size[0], self.size[1])
    self.raster_cr = cairo.Context(self.raster)
    self.raster_cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
    self.raster_cr.rectangle(0.0, 0.0, self.size[0], self.size[1])
    self.raster_cr.fill()
    for stroke in self.trace.last():
      self.draw(stroke.color, stroke[0].p, stroke[0].pos)
      if len(stroke) > 1:
        self.draw(stroke.color, stroke[1].p,
          stroke[0].pos, stroke[1].pos)
      for i in xrange(len(stroke)-2):
        self.draw(stroke.color, stroke[i+2].p,
          stroke[i].pos, stroke[i+1].pos, stroke[i+2].pos)
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

class GUI:
  def __init__(self, gladefile):
    # Set up most of the window (from glade file).
    self.glade_tree = gtk.glade.XML(gladefile)
    self.root = self.glade_tree.get_widget("mainwindow")
    self.root.connect("destroy", lambda x: sys.exit(0))

    # Add the canvas, too.
    self.canvas = Canvas()
    self.canvas.show()
    self.glade_tree.get_widget("vbox1").add(self.canvas)
    self.glade_tree.get_widget("clear").connect("clicked",
        lambda x: self.canvas.clear())

    self.last_fname = None

    # playback
    self.record_button = self.glade_tree.get_widget("record")
    self.play_button = self.glade_tree.get_widget("play")
    self.pause_button = self.glade_tree.get_widget("pause")
    self.stop_button = self.glade_tree.get_widget("stop")
    self.progress_bar = self.glade_tree.get_widget("progress-bar")
    self.pback_await = self.glade_tree.get_widget("playback/await")

#    self.play_button.connect("toggled", self.update_pbar)
    self.pbar_timer_id = None

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

    self.root.connect("delete-event", lambda x,y: gtk.main_quit())

    self.glade_tree.get_widget("edit/add").connect("activate",
        lambda x: self.canvas.clear())
    self.glade_tree.get_widget("add").connect("clicked",
        lambda x: self.canvas.clear())
    self.glade_tree.get_widget("file/open").connect("activate",
        lambda x: self.open())
    self.glade_tree.get_widget("open").connect("clicked",
        lambda x: self.open())
    self.glade_tree.get_widget("file/save").connect("activate",
        lambda x: self.save())
    self.glade_tree.get_widget("save").connect("clicked",
        lambda x: self.save())
    self.glade_tree.get_widget("file/save-as").connect("activate",
        lambda x: self.save_as())
    self.glade_tree.get_widget("file/quit").connect("activate", self.quit)
    self.glade_tree.get_widget("quit").connect("clicked", self.quit)

    self.save_fun = None
    self.open_fun = None

    self.canvas.set_extension_events(gtk.gdk.EXTENSION_EVENTS_ALL)

  def pbar_should_update(self):
    return self.pbar_timer_id is not None

  def update_pbar(self, w):
    if w.get_active():
      if self.pbar_timer_id is None:
        self.pbar_timer_id = gobject.timeout_add(1000, self.pbar_queue_redraw)
        print 'setting pbar_timer_id = %d' % self.pbar_timer_id
    else:
      if self.pbar_timer_id is not None:
        gobject.timeout_remove(self.pbar_timer_id)
        self.pbar_timer_id = None
        print 'stopped pbar_timer_id'

  def pbar_queue_redraw(self):
    if self.pbar_timer_id is not None:
      print 'queue'
      self.progress_bar.send_expose()
      return True
    return False

  def quit(self, event):
    if not self.canvas.dirty or self.dirty_ok():
      gtk.main_quit()


  # -------- Load/Save dialogues.

  def open(self):
    if self.canvas.dirty and not self.dirty_ok(): return
    fcd = gtk.FileChooserDialog('Choose a file to save', None,
        gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
          gtk.STOCK_OPEN, gtk.RESPONSE_ACCEPT))
    fcd.set_do_overwrite_confirmation(True)
    fcd.set_current_folder('saves')
    if fcd.run() == gtk.RESPONSE_ACCEPT:
      self.last_fname = fcd.get_filename()
      self.open_fun(fcd.get_filename())
    fcd.destroy()

  def save(self):
    if self.last_fname:
      self.save_fun(self.last_fname)
    else:
      self.save_as()

  def save_as(self):
    fcd = gtk.FileChooserDialog('Choose a file to save', None,
        gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
          gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
    fcd.set_do_overwrite_confirmation(True)
    fcd.set_current_folder('saves')
    fcd.set_current_name('save.dcb')
    if fcd.run() == gtk.RESPONSE_ACCEPT:
      self.last_fname = fcd.get_filename()
      self.save_fun(fcd.get_filename())
    fcd.destroy()

  def dirty_ok(self):
    '''Checks if it's okay that the canvas has unsaved changes on it.'''
    d = gtk.MessageDialog(None, 0, gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO,
        "You have unsaved changes.  Are you sure you want to continue?")
    ok = (d.run() == gtk.RESPONSE_YES)
    d.destroy()
    return ok


  # -------- Callbacks ---------------------

  def connect_new(self, fun):
    self.glade_tree.get_widget("file/new").connect("activate", lambda x: fun())
    self.glade_tree.get_widget("new").connect("clicked", lambda x: fun())

  def connect_record(self, fun):
    self.record_button.connect("toggled", lambda w: fun(w.get_active()))

  def connect_play(self, fun):
    self.play_button.connect("toggled", lambda w: fun(w.get_active()))

  def connect_pause(self, fun):
    self.pause_button.connect("toggled", lambda w: fun(w.get_active()))

  def connect_stop(self, fun):
    self.stop_button.connect("clicked", lambda w: fun())

  def connect_save(self, fun):
    self.save_fun = fun

  def connect_open(self, fun):
    self.open_fun = fun

  def connect_progress_fmt(self, fun):
    self.progress_bar.connect("format-value", lambda s,v: fun(v))


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

