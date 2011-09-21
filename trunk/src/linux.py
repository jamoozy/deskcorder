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

# for debugging
import traceback

from datatypes import *

class Canvas(gtk.DrawingArea):
  def __init__(self, dc):
    gtk.DrawingArea.__init__(self)

    self.radius = 3.0
    self.drawing = False
    self.raster = None
    self.raster_cr = None
    self.ttpt = -1

    # Keeps track of whether the state of the canvas is reflected in a file
    # somewhere or not.  If not, this is dirty.
    self.dirty = False

    # This won't accept mouse events when frozen.  Useful for when the
    # Deskcorder is playing back the contents of the Canvas and the
    # Audio.
    self.frozen = False

    self.dc = dc

    self.set_events(gtk.gdk.POINTER_MOTION_MASK |
                    gtk.gdk.BUTTON_MOTION_MASK |
                    gtk.gdk.BUTTON1_MOTION_MASK |
                    gtk.gdk.BUTTON2_MOTION_MASK |
                    gtk.gdk.BUTTON3_MOTION_MASK |
                    gtk.gdk.BUTTON_PRESS_MASK |
                    gtk.gdk.BUTTON_RELEASE_MASK)

    self.connect("configure-event", lambda w, e: self._configure())
    self.connect("expose-event", lambda w, e: self._gtk_expose())
    self.connect("motion-notify-event", self.gtk_motion)
    self.connect("button-press-event", self.gtk_button_press)
    self.connect("button-release-event", self.gtk_button_release)

    self.set_size_request(800,600)

  def freeze(self):
    self.frozen = True

  def unfreeze(self):
    self.frozen = False

  def draw_last_slide(self):
    
    it = self.dc.lec.last_slide_iter()
    try:
      last_point = None
      while True:
        point = it.next()
        if isinstance(point, Point):
          if last_point is None:
            self.draw(it.state.color, it.state.thickness * point.p,
                point.pos)
          else:
            self.draw(it.state.color, it.state.thickness * last_point.p,
                last_point.pos, point.pos)
          last_point = point
    except StopIteration:
      pass

  def draw_to_ttpt(self):
    '''Draw all events leading up to the ttpt variable.'''
    it = self.dc.lec.events_to_time(self.ttpt)
    try:
      last_point = it.next()
      self.draw(it.state.color, it.state.thickness * last_point.p,
          last_point.pos)
      while True:
        point = it.next()
        self.draw(it.state.color, it.state.thickness * last_point.p,
            last_point.pos, point.pos)
        last_point = point
    except StopIteration:
      pass

  def _configure(self):
    
    self.dc.lec.resize(self.window.get_size())
    self.draw_all()

  def draw_all(self):
    self.raster = self.window.cairo_create().get_target().create_similar(
        cairo.CONTENT_COLOR, int(self.dc.lec.state.width()),
                             int(self.dc.lec.state.height()))
    self.raster_cr = cairo.Context(self.raster)
    self.raster_cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
    self.raster_cr.rectangle(0.0, 0.0, self.dc.lec.state.width(),
                                       self.dc.lec.state.height())
    self.raster_cr.fill()
    if self.ttpt >= 0:
      self.draw_to_ttpt()
    else:
      self.draw_last_slide()
    self.refresh()

  def get_pressure_or_default(self, device, default = None):
    pressures = [dev.get_axis(dev.get_state(self.window)[0],
      gtk.gdk.AXIS_PRESSURE) for dev in gtk.gdk.devices_list()]
    p = max([0.0] + [i for i in pressures if i is not None])
    if p < 1e-5: p = None
    return default if default is not None and p is None else p

  def _compute_normalized_pos(self, event):
    pos = event.get_coords()
    return (pos[0] / float(self.dc.lec.state.width()),
            pos[1] / float(self.dc.lec.state.height()))

  def gtk_button_press(self, widget, event):
    if not self.frozen:
      pos = self._compute_normalized_pos(event)
      self.dirty = True
      self.drawing = True
      ratio = self.dc.lec.state.aspect_ratio()
      self.dc.lec.append(Click(time.time(), pos))

  def gtk_motion(self, widget, event):
    if not self.frozen:
      pos = self._compute_normalized_pos(event)
      if self.drawing:
        self.dirty = True
        p = self.get_pressure_or_default(event.device, .5)
        r = p * self.dc.lec.state.thickness
        points = self.dc.lec.last_points(2)
        if len(points) > 1:
          self.draw(self.dc.lec.state.color, r,
              points[-2].pos, points[-1].pos, pos)
        elif len(points) > 0:
          self.draw(self.dc.lec.state.color, r,
              points[-1].pos, pos)
        else:
          self.draw(self.dc.lec.state.color, r, pos)
        self.dc.lec.append(Point(time.time(), pos, p))
      else:
        self.dc.lec.append(Move(time.time(), pos))

  def gtk_button_release(self, widget, event):
    if not self.frozen:
      pos = self._compute_normalized_pos(event)
      self.dirty = True
      self.drawing = False
      self.olderPos = None
      self.oldPos = None
      self.oldRad = None
      self.dc.lec.append(Release(time.time(), pos))

  def _gtk_expose(self):
    cr = self.window.cairo_create()
    cr.set_source_surface(self.raster, 0.0, 0.0)
    cr.paint()
    cr.set_line_width(2)
    cr.set_source_rgba(0.0, 0.0, 0.0, 0.25)
    cr.rectangle(0.0, 0.0, self.dc.lec.state.width(),
                           self.dc.lec.state.height())
    cr.stroke()

  def set_radius(self, rad):
    self.radius = rad

  def setColor(self, r, g = None, b = None):
    if isinstance(r, tuple) and len(r) == 3:
      self.color = r
    elif g is None or b is None:
      raise AttributeError("sign. is setColor((r,g,b)) or setColor(r,g,b)")
    else:
      self.color = (r,g,b)

  def clear(self):
    self.raster_cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
    self.raster_cr.rectangle(0.0, 0.0, self.dc.lec.state.width(),
                                       self.dc.lec.state.height())
    self.raster_cr.fill()
    self.refresh()
    if not self.frozen:
      self.dc.lec.append(time.time())

  def refresh(self):
    reg = gtk.gdk.Region()
    reg.union_with_rect((0, 0, int(self.dc.lec.state.width()),
                               int(self.dc.lec.state.height())))
    self.window.invalidate_region(reg, False)

  def reset(self):
    self.clear()
    self.dc.lec = Lecture()
    self.positions = []
    self.dirty = False
    self.frozen = False

  def redraw(self):
    self.clear()
    self.draw_all()

  def draw(self, color, r, pos1, pos2=None, pos3=None):
    self.raster_cr.set_source_rgba(color[0], color[1], color[2], 1.0)
    reg = gtk.gdk.Region()
    r = r * math.sqrt(self.dc.lec.state.width()**2 + self.dc.lec.state.height()**2)
    pos1 = (pos1[0] * self.dc.lec.state.width(), pos1[1] * self.dc.lec.state.height())
    if pos2 is not None:
      pos2 = (pos2[0] * self.dc.lec.state.width(),
              pos2[1] * self.dc.lec.state.height())
    if pos3 is not None:
      pos3 = (pos3[0] * self.dc.lec.state.width(),
              pos3[1] * self.dc.lec.state.height())
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
            min(int(pos1[0] - r), int(pos2[0] - r)),
            min(int(pos1[1] - r), int(pos2[1] - r)),
            int(abs(pos1[0] - pos2[0]) + 2*r),
            int(abs(pos1[1] - pos2[1]) + 2*r)))
    else:
      self.raster_cr.set_line_width(r)
      self.raster_cr.set_line_join(cairo.LINE_JOIN_MITER)
      self.raster_cr.set_line_cap(cairo.LINE_CAP_ROUND)
      self.raster_cr.move_to(pos1[0], pos1[1])
      self.raster_cr.line_to(pos2[0], pos2[1])
      self.raster_cr.line_to(pos3[0], pos3[1])
      self.raster_cr.stroke()
      reg.union_with_rect((
            min(int(pos1[0] - r), int(pos2[0] - r)),
            min(int(pos1[1] - r), int(pos2[1] - r)),
            int(abs(pos1[0] - pos2[0]) + 2*r),
            int(abs(pos1[1] - pos2[1]) + 2*r)))
      reg.union_with_rect((
            min(int(pos2[0] - r), int(pos3[0] - r)),
            min(int(pos2[1] - r), int(pos3[1] - r)),
            int(abs(pos2[0] - pos3[0]) + 2*r),
            int(abs(pos2[1] - pos3[1]) + 2*r)))
    self.window.invalidate_region(reg, False)

class ExportDialog(gtk.Dialog):
  def __init__(self):
    gtk.Dialog.__init__(self)

  def run(self):
    return 0

class GUI:
  def __init__(self, dc):
    self.dc = dc

    # Set up most of the window (from XML file).
    self.builder = gtk.Builder()
    self.builder.add_from_file('../config/layout.gtk')
    self['root'].connect("destroy", lambda x: sys.exit(0))

    # Add the canvas, too.
    self.canvas = Canvas(dc)
    self.canvas.show()
    self["vbox1"].add(self.canvas)
    self["clear"].connect("clicked", lambda x: self.canvas.clear())

    self.last_fname = None

    # import/export
    self['file/export/png'].connect("activate", lambda x: self.exp_png())
    self['file/export/pdf'].connect("activate", lambda x: self.exp_pdf())
    self['file/export/swf'].connect("activate", lambda x: self.exp_swf())

    # pen widths
    self["thin"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_thickness(.005))
    self["medium"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_thickness(.01))
    self["thick"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_thickness(.02))

    # colors
    self["black"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_color(0.0, 0.0, 0.0))
    self["blue"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_color(0.0, 0.0, 1.0))
    self["red"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_color(1.0, 0.0, 0.0))
    self["green"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_color(0.0, 1.0, 0.0))
    self["gray"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_color(0.5, 0.5, 0.5))
    self["cyan"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_color(0.0, 1.0, 1.0))
    self["lime"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_color(0.3, 1.0, 0.5))
    self["magenta"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_color(1.0, 0.0, 1.0))
    self["orange"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_color(1.0, 0.5, 0.0))
    self["yellow"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_color(1.0, 1.0, 0.0))
    self["white"].connect("toggled",
        lambda x: x.get_active() and self.dc.set_color(1.0, 1.0, 1.0))

    self['root'].connect("delete-event", lambda x,y: gtk.main_quit())

    self["edit/add"].connect("activate", lambda x: self.canvas.clear())
    self["add"].connect("clicked", lambda x: self.canvas.clear())
    self["file/open"].connect("activate", lambda x: self.open())
    self["open"].connect("clicked", lambda x: self.open())
    self["file/save"].connect("activate", lambda x: self.save())
    self["save"].connect("clicked", lambda x: self.save())
    self["file/save-as"].connect("activate", lambda x: self.save_as())
    self["file/quit"].connect("activate", self.quit)
    self["quit"].connect("clicked", self.quit)

    self["help/about"].connect("activate", lambda x: self.about_dialog())

    self.save_fun = None
    self.open_fun = None
    self.exp_pdf_fun = None
    self.exp_png_fun = None
    self.imp_swf_fun = None

    self.canvas.set_extension_events(gtk.gdk.EXTENSION_EVENTS_ALL)

  def __getitem__(self, key):
    return self.builder.get_object(key)

  def get_size(self):
    '''Returns a (width,height) tuple of the canvas size.'''
    print 'window size:', self.canvas.window.get_size()
    print '       size:', self['root'].get_size()
    return self.canvas.window.get_size()

  def about_dialog(self):
    '''Shows the about dialog.'''
    d = gtk.AboutDialog()
    d.set_name('Deskcorder')
    d.set_version('0.1')
    d.set_copyright('GPL v.3')
    d.set_comments('''Deskcorder is a recorder for what happens at your desk!

Draw and record yourself, then play it back for your friends!  What a party trick!  Be the life of the party!''')
    d.set_license('GPL v.3')
    d.set_website('http://deskcorder.googlecode.com')
    d.set_authors(('Andrew Correa (jamoozy@csail.mit.edu)',
                   'Ali Mohammad (alawi@csail.mit.edu)'))
    d.run()
    d.destroy()

  def quit(self, event):
    if not self.canvas.dirty or self.dirty_quit_ok():
      gtk.main_quit()

  def set_fname(self, fname):
    try:
      self.last_fname = fname[fname.rindex('/')+1:]
    except ValueError:
      self.last_fname = fname


  # -------- Import/Export dialogs.

#  def frame_selector(self):
#    b = gtk.Builder()
#    b.load_from_file('exp-dialog.gtk')
#    model = b.builder.get_object('treeview').get_model()
#
#    tstamps = map(lambda x: x.t - .1, self.canvas.dc.lec.slides[1:]) + [self.canvas.dc.lec.last().last().last().t + .1]
#    for ts in tstamps:
#      it = b.builder.get_object('list').append((gobject.TYPE_UINT64, gobject.TYPE_STRING))
#      b.builder.get_object('list').append(it, 0, ts, 
#
#    b.builder.get_object('root').show()
#    b.builder.get_object('root').destroy()
#
#    for b
#    return tstamps

  def exp_png(self):
    if self.exp_png_fun is None:
      self.int_err('Export to PNG functionality disabled.')
      return
    #frames = self.frame_selector()
    frames = []

    fcd = gtk.FileChooserDialog('Choose a PNG file to export to', None,
        gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
          gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
    fcd.set_do_overwrite_confirmation(True)
    fcd.set_current_folder('saves')
    if self.last_fname is not None:
      fcd.set_current_name(self.last_fname[:-4] + '.png')
    else:
      fcd.set_current_name('save.png')
    self.add_png_filters(fcd)
    if fcd.run() == gtk.RESPONSE_ACCEPT:
      self.exp_png_fun(fcd.get_filename(), (800,600), None) # FIXME (800,600)?
      fcd.destroy()
      return True
    fcd.destroy()
    return False

  def exp_pdf(self):
    if self.exp_pdf_fun is None:
      self.int_err('Export to PDF functionality disabled.')
      return

    fcd = gtk.FileChooserDialog('Choose a PDF file to export to', None,
        gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
          gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
    fcd.set_do_overwrite_confirmation(True)
    fcd.set_current_folder('saves')
    if self.last_fname is not None:
      fcd.set_current_name(self.last_fname[:-4] + '.pdf')
    else:
      fcd.set_current_name('save.pdf')
    self.add_pdf_filters(fcd)
    if fcd.run() == gtk.RESPONSE_ACCEPT:
      self.exp_pdf_fun(fcd.get_filename(), (800,600), None) # FIXME (800,600)?
      fcd.destroy()
      return True
    fcd.destroy()
    return False

  def exp_swf(self):
    if self.exp_swf_fun is None:
      self.int_err('Export to Flash functionality disabled.')
      return

    fcd = gtk.FileChooserDialog('Choose a .swf file to export to', None,
        gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
          gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
    fcd.set_do_overwrite_confirmation(True)
    fcd.set_current_folder('saves')
    if self.last_fname is not None:
      fcd.set_current_name(self.last_fname[:-4] + '.swf')
    else:
      fcd.set_current_name('save.swf')
    self.add_swf_filters(fcd)
    if fcd.run() == gtk.RESPONSE_ACCEPT:
      self.exp_swf_fun(fcd.get_filename())
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
    self.add_dc_filters(fcd)
    while fcd.run() == gtk.RESPONSE_ACCEPT:
      self.last_fname = fcd.get_filename()
      if self.open_fun(fcd.get_filename()):
        break
      else:
        self.ext_err("Invalid or corrupted file.")
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
    self.add_dc_filters(fcd)
    if fcd.run() == gtk.RESPONSE_ACCEPT:
      self.last_fname = fcd.get_filename()
      self.save_fun(fcd.get_filename())
      fcd.destroy()
      return True
    fcd.destroy()
    return False


  # ---------- Dialogs ------------------------------

  @staticmethod
  def add_filter(fcd, ft):
    '''Adds "filter tuple" ft to the fcd dialog.'''
    if not isinstance(ft, tuple):
      raise RuntimeError('not a tuple, as expected')
    f = gtk.FileFilter()
    f.set_name(ft[0])
    f.add_pattern(ft[1])
    fcd.add_filter(f)

  @staticmethod
  def add_dc_filters(fcd):
    GUI.add_filter(fcd, ("DC archive", "*.dar"))
    GUI.add_filter(fcd, ("DC binary (deprecated)", "*.dcb"))
    GUI.add_filter(fcd, ("DC XML", "*.dcx"))
    GUI.add_filter(fcd, ("DC text", "*.dct"))
    GUI.add_filter(fcd, ("All DC Files", "*.dc[bxt]"))
    GUI.add_filter(fcd, ("All files", "*.*"))

  @staticmethod
  def add_pdf_filters(fcd):
    GUI.add_filter(fcd, ('PDF files', '*.pdf'))
    GUI.add_dc_filters(fcd)

  @staticmethod
  def add_swf_filters(fcd):
    GUI.add_filter(fcd, ('SWF files', '*.swf'))
    GUI.add_dc_filters(fcd)

  @staticmethod
  def add_png_filters(fcd):
    GUI.add_filter(fcd, ('PNG files', '*.png'))
    GUI.add_dc_filters(fcd)

  @staticmethod
  def add_all_filters(fcd):
    GUI.add_filter(fcd, ('PDF files', '*.pdf'))
    GUI.add_filter(fcd, ('PNG files', '*.png'))
    GUI.add_dc_filters(fcd)

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

  def ext_err(self, msg):
    '''External error notification dialog box.'''
    d = gtk.MessageDialog(None, 0, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, msg)
    d.run()
    d.destroy()


  # -------- Callbacks ---------------------

  def connect_new(self, fun):
    self["file/new"].connect("activate", lambda x: fun())
    self["new"].connect("clicked", lambda x: fun())
    self.last_fname = None

  def connect_record(self, fun):
    self['record'].connect("toggled", lambda w: fun(w.get_active()))
    self["playback/record"].connect("activate", lambda w:
        fun(self['record'].get_active()))

  def connect_play(self, fun):
    self['play'].connect("toggled", lambda w: fun(w.get_active()))
    self["playback/play"].connect("activate", lambda w:
        fun(self['play'].get_active()))

  def connect_pause(self, fun):
    self['pause'].connect("toggled", lambda w: fun(w.get_active()))
    self["playback/pause"].connect("activate", lambda w:
        fun(self['pause'].get_active()))

  def connect_stop(self, fun):
    self['stop'].connect("clicked", lambda w: fun())
    self["playback/stop"].connect("activate", lambda w: fun())

  def connect_exp_swf(self, fun):
    self.exp_swf_fun = fun

  def connect_exp_png(self, fun):
    self.exp_png_fun = fun

  def connect_exp_pdf(self, fun):
    self.exp_pdf_fun = fun

  def connect_save(self, fun):
    self.save_fun = fun

  def connect_open(self, fun):
    self.open_fun = fun

  def connect_progress_fmt(self, fun):
    self['progress-bar'].connect("format-value", lambda s,v: fun(v))

  def connect_progress_moved(self, fun):
    self['progress-bar'].connect("change-value", lambda s,t,v: fun(max(min(v, 1.), .0)))


  # ---- buttons -------------------------

  def record_pressed(self, state = None):
    if state is None:
      return self['record'].get_active()
    else:
      self['record'].set_active(state)

  def play_pressed(self, state = None):
    if state is None:
      return self['play'].get_active()
    else:
      self['play'].set_active(state)

  def pause_pressed(self, state = None):
    if state is None:
      return self['pause'].get_active()
    else:
      self['pause'].set_active(state)

  def audio_wait_pressed(self, state = None):
    if state is None:
      return self['playback/await'].get_active()
    else:
      self['playback/await'].set_active(state)

  def progress_slider_value(self, val = None):
    if val is None:
      return self['pbar-align'].get_value()
    else:
      self['pbar-align'].set_value(min(max(0., val), 1.))
      self['progress-bar'].queue_draw()

  def disable_progress_bar(self):
    self['progress-bar'].set_sensitive(False)

  def enable_progress_bar(self):
    self['progress-bar'].set_sensitive(True)

  def timeout_add(self, delay, fun):
    gobject.timeout_add(delay, fun)


  # ---- Up and down ---------------------

  def init(self):
    self['root'].show()
    self.canvas._configure()  # Some arch's need this or nothing is shown.

  def run(self):
    gtk.main()

  def deinit(self):
    self['root'].hide()
    self['root'].destroy()



class InvalidOperationError(RuntimeError):
  '''Used when an invalid audio operation was made.'''
  pass

class Audio:
  def __init__(self, lec):
    self.data = []  # K.I.S.S.  Data stored as a string.
    # next version: store an array of strings.  Do smart things to determine
    # when no one is talking.

    self.lec = lec
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

  def print_info(self):
    if self.inp is None: return
    print 'Card name: %s' % self.inp.cardname()
    print ' PCM mode: %d' % self.inp.pcmmode()
    print ' PCM type: %d' % self.inp.pcmtype()

  def reset(self):
    self.play_start = None
    self.recording = False
    self.paused = False

  def is_recording(self):
    return self.inp is not None

  def set_progress(self, t):
    if self.is_playing():
      self.stop()

    self.play_init()
    if len(self.lec.adats[-1]) <= 0:
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
      if isinstance(self.data[i][1], list):
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
    '''Gets the time the first audio snippet began recording.'''
    return self.data[0][0] if len(self.data) > 0 else -1

  def get_time_of_last_event(self):
    '''Gets the time the last audio snippet finished.'''
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

  def is_empty(self):
    return len(self.data) <= 0 or len(self.data[-1][1]) <= 0
