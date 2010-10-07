#!/usr/bin/python

import math
import sys
import time
import thread
import os
import signal
from datatypes import *

import fileio
import exporter



############################################################################
# ---------------------------- Main Object ------------------------------- #
############################################################################

class Main:
  def __init__(self, gui_enabled=True, audio_enabled=True):
    # Playback variables.
    self.play_time = None
    self.break_times = []
    self.last_pause = None

    self.lec = Lecture()

    self.audio = Audio(self)
    self.gui = GUI(self)

    self.gui.connect_new(self.reset)
    self.gui.connect_play(self.play)
    self.gui.connect_pause(self.pause)
    self.gui.connect_stop(self.stop)
    self.gui.connect_save(self.save)
    self.gui.connect_open(self.load)
    self.gui.connect_record(self.record)
    self.gui.connect_progress_fmt(self.fmt_progress)
    self.gui.connect_progress_moved(self.move_progress)
    self.gui.connect_exp_png(self.exp_png)
    self.gui.connect_exp_pdf(self.exp_pdf)
    self.gui.connect_exp_swf(self.exp_swf)

    if not audio_enabled: print 'Audio disabled'
    if not gui_enabled: print 'GUI disabled'

    self.progress = -1

  def set_color(self, r, g, b):
    self.lec.append(Color(time.time(), (r,g,b)))

  def set_thickness(self, th):
    self.lec.append(Thickness(time.time(), th))

  def is_empty(self):
    return self.lec.is_empty() and self.audio.is_empty()

  def all_buttons_off(self):
    self.gui.record_pressed(False)
    self.gui.play_pressed(False)
    self.gui.pause_pressed(False)

  def set_progress(self, val):
    self.progress = val
    self.audio.set_progress(val + self.lec.first().utime())
    self.gui.canvas.ttpt = val + self.lec.first().utime()
    self.it.seek(self.progress)

  def reset(self):
    '''Clears the state of the canvas and audio, as if the system had just
    started.'''
    if not self.gui.canvas.dirty or self.gui.dirty_new_ok():
      self.all_buttons_off()
      self.gui.progress_slider_value(.0)
      self.gui.canvas.reset()
      self.audio.reset()
      self.stop()

  def load_config(self, config):
    self.config = config
    if config is None: return

    print 'Loading configuration from "%s"' % config.config_dir

    if os.path.isdir(config.lecture_dir):
      self.gui.ask_recover()

    if config.file_to_load is not None and config.file_to_load is not False:
      print 'Loading', config.file_to_load
      try:
        self.load(config.file_to_load)
      except IOError as e:
        print 'Could not load file, %s: %s"' % (fname, str(e))
    else:
      print 'config.file_to_load:', config.file_to_load

  def run(self, config = None):
    '''Runs the program.'''
    self.gui.init()
    self.load_config(config)
    try:
      self.lec.append(Start(time.time(), self.gui.get_size()))
      self.gui.run()
    except KeyboardInterrupt:
      pass
    self.gui.deinit()

  def is_recording(self):
    return self.audio.is_recording()

  def record(self, rec):
    '''Starts the mic recording.'''
    if rec:
      self.gui.disable_progress_bar()
      try:
        self.audio.record()
      except fileio.InvalidOperationError:
        self.gui.record_pressed(False)
    else:
      self.gui.enable_progress_bar()
      self.audio.stop()

  def is_playing(self):
    '''Determines if this is playing or not.'''
    # FIXME Adding one at the end is the same hack as below (in play_tick()).
    return self.progress >= 0 and self.progress <= self.lec.duration() + 1

  def play(self, active):
    '''Start/stop playing what's in this file.'''
    if self.is_empty():
      self.all_buttons_off()
      return

    if not active:
      if self.is_paused():
        self.gui.play_pressed(True)
        self.gui.pause_pressed(False)
      else:
        self.stop()
      return
    elif self.is_playing():
      return

    if self.is_recording():
      self.stop()
      self.gui.play_pressed(True)

    self.audio.play_init()

    now = time.time()

    self.gui.canvas.freeze()

    # Playback iterators.
    self.it = iter(self.lec)

    # prev & curr time play_tick() was called and progress in seconds.
    self.play_time = now
    self.prev_now = now
    self.curr_now = self.prev_now
    self.progress = 0

    self.gui.canvas.clear()  # FIXME hack because I don't get the first slide
                             #       from the Lecture.Iterator object.
    self.gui.timeout_add(50, self.play_tick)

  def play_tick(self):
    '''Do one "tick" in the process of playing back what's stored in this
    program.'''

    if not self.is_playing():
      return False
    if self.is_paused():
      return True
    if self.lec.duration() <= 0:
      return False

    # "normal" update
    self.prev_now = self.curr_now
    self.curr_now = time.time()
    self.progress += self.curr_now - self.prev_now

    # adjustment for audio lag
    if self.audio.is_playing():
      a_start = self.audio.get_current_audio_start_time()
      a_time = self.audio.get_s_played()
      if a_start > 0:
        self.audio.play_tick(self.progress + self.lec.first().utime())
        if a_time <= 0 and not self.gui.audio_wait_pressed():
          a_time = .01
        if a_time > 0:
          self.progress = a_start + a_time - self.lec.first().utime()
    else:
      a_time = -1

    # updating GUI slider bar
    self.gui.progress_slider_value(self.progress / self.lec.duration())
    self.gui.canvas.ttpt = self.progress + self.lec.first().utime()

    # FIXME hack: I'm fixing the symptom, not the cause, here ...
    self.progress += 1

    # I'm simulating a do-while loop here.  This one is basically:
    #  1. Get all the objects up to self.progress.
    #     a. for each slide, clear the screen,
    #     b. for each stroke, start drawing a new stroke
    #     c. for each point, draw the point.
    #  2. When out iterator goes past the end of the lec object and we're
    #     out of audio, return false (stop calling this function).
    for e in self.it.next(self.progress):
      if isinstance(e, ScreenEvent):
        self.gui.canvas.clear()
      elif isinstance(e, Click):
        self.last_point = e
      elif isinstance(e, Point):
        self.gui.canvas.draw(self.it.state.color,
            self.it.state.thickness * e.p, self.last_point.pos, e.pos)
        self.last_point = e

    if not self.it.has_next() and a_time < 0:
      self.stop()
      return False
    return self.check_done()

  def pause(self, checked):
    '''Pauses playback and audio recording.'''
    if self.is_empty():
      self.all_buttons_off()
      return

    now = time.time()
    if self.is_playing():
      if self.last_pause == None:
        self.last_pause = now
        self.gui.pause_pressed(True)
        self.audio.pause()
      else:
        self.break_times.append((self.last_pause, now))
        self.last_pause = None
        self.gui.pause_pressed(False)
        self.audio.unpause()
    else:
      self.gui.pause_pressed(False)

  def is_paused(self):
    '''Determines if playback is paused.'''
    return self.last_pause is not None

  def done(self):
    '''The drawing portion is done playing back.  Wait for the speech portion
    to finish also.'''
    self.gui.timeout_add(100, self.check_done)

  def check_done(self):
    '''Returns True if this should keep playing, False otherwise.'''
    if not self.is_playing():
      self.stop()
      return False
    return True

  def stop(self):
    '''Stops playback and recording.'''
    if self.is_paused():
      self.pause(time.time())
    self.audio.stop()
    self.gui.record_pressed(False)
    self.gui.play_pressed(False)
    self.gui.canvas.unfreeze()
    self.last_pause = None
    self.break_times = []
    self.play_time = None
    self.progress = -1

  def fmt_progress(self, val):
    '''Called by the GUI upon a request to redraw the progress label.'''
    dur = self.lec.duration()
    total = '%d:%02d' % (dur / 60, math.ceil(dur % 60))
    if self.is_empty():
      if self.gui.progress_slider_value() != 0:
        self.gui.progress_slider_value(.0)
      return '0:00 / 0:00'
    elif self.is_playing():
      return '%d:%02d / %s' % (round(self.progress / 60), self.progress % 60, total)
    else:
      return '0:00 / %s' % total

  def move_progress(self, val):
    '''Called by the GUI when the progress bar has been moved (usually by a
    mouse drag).'''
    if self.is_empty():
      self.all_buttons_off()
      # Can't set progress here, because may be in reaction to a mouse click,
      # in which case an update will get immediately overwritten by the
      # mouse-up event, or whatever is responsible for it.
      return
    elif self.is_recording():
      pass # do nothing?
    else:
      self.gui.play_pressed(True)
      self.gui.pause_pressed(True)
      self.set_progress(val * self.lec.duration())
      self.gui.redraw()



  ############################################################################
  # ------------------------------ File I/O -------------------------------- #
  ############################################################################

  def exp_png(self, fname, size, times):
    if fname.lower().endswith('.png'):
      exporter.to_png(self.lec, fname[:-4], size, times)
    else:
      exporter.to_png(self.lec, fname, size, times)

  def exp_pdf(self, fname, size, times):
    if fname.lower().endswith('.pdf'):
      exporter.to_pdf(self.lec, fname[:-4], size, times)
    else:
      exporter.to_pdf(self.lec, fname, size, times)

  def exp_swf(self, fname):
    exporter.to_swf(self.lec, self.audio.make_data(), fname)

  def save(self, fname = 'save.dcb'):
    if self.is_recording():
      self.record(False)
    fileio.save(fname, self.lec)
    self.gui.canvas.dirty = False

  def load(self, fname = 'save.dcb'):
    try:
      self.lec = fileio.load(fname)
      return True
    except fileio.FormatError:
      return False



##############################################################################
# -------------------------- Testing/Running ------------------------------- #
##############################################################################

class Configuration:
  '''Represents a configuration of Deskcorder.  This takes all things into
  account, including the configuration files, the OS, and command-line
  parameters.'''

  # valid video modules in preferred order
  VALID_AV_MODULES = ['linux', 'mac', 'qt', 'dummy']

  def __init__(self, config_dir = None):
    # platform-agnostic options
    self.help_req = False
    self.export_fmt = None
    self.file_to_load = False
    self._load_defaults(config_dir)
    self._load_config(self.config_file)

  def _load_defaults(self, config_dir):
    '''Loads the platform-dependent default configuration.'''
    # platform-dependent options
    if os.name == 'posix':
      self.gui_module = 'linux'
      self.audio_module = 'linux'
      self.config_dir = os.path.expanduser('~/.deskcorder' if config_dir is None else config_dir)
      self.config_file = self.config_dir + '/config'
      self.lecture_dir = self.config_dir + '/session'
    elif os.name == 'nt':
      print 'Warning: NT varieties of Windows not yet supported.'
    elif os.name == 'os2':
      print 'Warning: Mac OS not yet supported.'
    elif os.name == 'ce':
      print 'Warning: CE varieties of Windows not yet supported.'
    elif os.name == 'riscos':
      print 'Warning: I have no idea what RiscOS is ...'
    else:
      print 'Warning: unhandled OS type:', os.name
      self.gui_module = None
      self.audio_module = None
      self.config_dir = None
      self.config_file = None
      self.lecture_dir = None

  def _load_config(self, cfile):
    '''Loads the configuration in 'cfile'.'''
    # If cfile DNE,
    if not os.path.exists(cfile):
      # If cdir exists
      if os.path.exists(os.path.dirname(cfile)):
        # If cdir is a directory
        if os.path.isdir(os.path.dirname(cfile)):
          # Create an empty cfile.
          open(cfile, 'w').close()
        # If cdir is is a file
        else:
          # Move it to a temp file
          tmp = tempfile.mktemp()
          os.rename(os.path.dirname(cfile), tmp)
          # Create the directory
          os.mkdir(os.path.dirname(cfile))
          # Move the temp file to cfile
          os.rename(tmp, cfile)
      else:
        os.mkdir(os.path.dirname(cfile))
        open(cfile, 'w').close()

    fp = file(cfile, 'r')
    try:
      while True:
        line = fp.next().strip()
        if line.startswith("#"): continue
        if line.startswith("default_format"):
          pass  # TODO write me
    except StopIteration:
      pass


  def load_file(self, fname = None):
    '''Register the file to load with the configuration.  Assume that if a
    file name has already been given, the new "file" is actually a bad
    command line argument.  If fname is None, assume that the caller wants
    to know what the file name is.'''
    if fname is None:
      return self.file_to_load
    elif self.file_to_load != False:
      print 'Warning: unrecognized command line argument:', fname
    else:
      self.file_to_load = fname

  def help(self):
    self.help_req = True

  def export(self, exp):
    self.export_fmt = exp

  def audio(self, module = None):
    if module is None:
      return self.audio_module
    else:
      self.audio_module = module

  def gui(self, module = None):
    if module is None:
      return self.gui_module
    else:
      self.gui_module = module

  @staticmethod
  def print_usage():
    print
    print 'Usage: ', sys.argv[0], '[file] [options]'
    print '  -h --help'
    print '      Print this usage and exit.'
    print '  -G --no-gui'
    print "      Don't use a GUI"
    print "  -A --no-audio"
    print "      Don't use audio"
    print "  --use-gui=[module]"
    print '      Use a specific GUI module.'
    print "  --use-audio=[module]"
    print '      Use a specific audio module.'
    print '  --exp-swf'
    print '      Export to a SWF file.  Implies "--no-gui"'
    print '      Assumes [file] was given.'
    print

def parse_args(args):
  config = Configuration()
  for arg in args:
    if arg == '-h' or arg == '--help':
      config.help()
    elif arg == '-G' or arg == '--no-gui':
      config.gui(False)
    elif arg == '-A' or arg == '--no-audio':
      config.audio(False)
    elif arg.startswith('--use-gui='):
      config.gui(arg[10:])
    elif arg.startswith('--use-audio='):
      config.audio(arg[12:])
    elif arg.startswith('--exp-'):
      config.export(arg[-3:])
    else:
      config.load_file(arg)
  return config

if __name__ == '__main__':

  config = parse_args(sys.argv[1:])

  if config.help_req:
    Configuration.print_usage()
    sys.exit(0)

  if config.export_fmt is not None:
    if config.export_fmt == 'swf':
      lec = fileio.load(config.file_to_load)
      exporter.to_swf(lec, a, config.file_to_load[:-4] + '.swf')
    elif config.export_fmt == 'pdf':
      lec = fileio.load(config.file_to_load)
      exporter.to_pdf(lec, config.file_to_load[:-4] + '.swf')
    elif config.export_fmt in ['dcd', 'dcb', 'dcx', 'dar', 'dct']:
      lec = fileio.load(config.file_to_load)
      fileio.save(config.file_to_load[:-3] + config.export_fmt, lec, a)
    else:
      print 'Unknown flag "--exp-%s"' % config.export_fmt
    sys.exit(0)

  # Something was passed, so use that to 
  if config.audio_module is not None:
    try:
      Audio = __import__(config.audio_module).Audio
    except AttributeError:
      config.audio_module = None
      print 'audio module "%s" not found' % config.audio_module

  if config.audio_module is None:
    for a in Configuration.VALID_AV_MODULES:
      try:
        Audio = __import__(a).Audio
        config.audio_module = a
        break
      except AttributeError:
        pass

  if config.gui_module is not None:
    try:
      Canvas = __import__(config.gui_module).Canvas
      GUI = __import__(config.gui_module).GUI
    except AttributeError:
      config.gui_module = None
      print 'video module "%s" not found' % config.gui_module

  if config.gui_module is None:
    for v in Configuration.VALID_AV_MODULES:
      try:
        GUI = __import__(v).GUI
        config.gui_module = v
        break
      except AttributeError:
        pass

  print 'using %s audio and %s gui' \
      % (config.audio_module, config.gui_module)
  Main().run(config)
