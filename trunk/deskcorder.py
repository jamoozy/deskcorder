#!/usr/bin/python

import math
import sys
import time
import thread
import os
import signal
from datatypes import *

import recorder
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

    self.lecture = Lecture(time.time())

    self.audio = Audio()
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

  def is_empty(self):
    return self.lecture.is_empty() and self.audio.is_empty()

  def all_buttons_off(self):
    self.gui.record_pressed(False)
    self.gui.play_pressed(False)
    self.gui.pause_pressed(False)

  def set_progress(self, val):
    self.progress = val
    self.audio.set_progress(val + self.earliest_event_time())
    self.gui.canvas.ttpt = val + self.earliest_event_time()
    self.it.seek(self.progress)

  def get_duration(self):
    start_t = self.earliest_event_time()
    end_t = self.latest_event_time()
    return (end_t - start_t) if start_t >= 0 and end_t >= 0 else .0

  def earliest_event_time(self):
    video_t = self.lecture.get_time_of_first_event()
    audio_t = self.audio.get_time_of_first_event()
    if audio_t >= 0 and video_t >= 0:
      return min(audio_t, video_t)
    elif video_t >= 0:
      return video_t
    else:
      return audio_t

  def latest_event_time(self):
    video_t = self.lecture.get_time_of_last_event()
    audio_t = self.audio.get_time_of_last_event()
    return max(audio_t, video_t) if video_t >= 0 else audio_t

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

    print 'Loading from "%s"' % config.config_dir

    if os.path.isdir(config.lecture_dir):
      self.gui.ask_recover()

    if config.file_to_load is not None and config.file_to_load is not False:
      try:
        self.load(config.file_to_load)
      except IOError as e:
        print 'Could not load file, %s: %s"' % (fname, str(e))


  def run(self, config = None):
    '''Runs the program.'''
    self.gui.init()
    self.load_config(config)
    try:
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
      except recorder.InvalidOperationError:
        self.gui.record_pressed(False)
    else:
      self.gui.enable_progress_bar()
      self.audio.stop()

  def is_playing(self):
    '''Determines if this is playing or not.'''
    # FIXME Adding one at the end is the same hack as below (in play_tick()).
    return self.progress >= 0 and self.progress <= self.get_duration() + 1

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
    self.it = iter(self.lecture)

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
    if self.get_duration() <= 0:
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
        self.audio.play_tick(self.progress + self.earliest_event_time())
        if a_time <= 0 and not self.gui.audio_wait_pressed():
          a_time = .01
        if a_time > 0:
          self.progress = a_start + a_time - self.earliest_event_time()
    else:
      a_time = -1

    # updating GUI slider bar
    self.gui.progress_slider_value(self.progress / self.get_duration())
    self.gui.canvas.ttpt = self.progress + self.earliest_event_time()

    # FIXME hack: I'm fixing the symptom, not the cause, here ...
    self.progress += 1

    # I'm simulating a do-while loop here.  This one is basically:
    #  1. Get all the objects up to self.progress.
    #     a. for each slide, clear the screen,
    #     b. for each stroke, start drawing a new stroke
    #     c. for each point, draw the point.
    #  2. When out iterator goes past the end of the lecture object and we're
    #     out of audio, return false (stop calling this function).
    for e in self.it.next(self.progress):
      if type(e) == Slide:
        self.gui.canvas.clear()
      elif type(e) == Stroke:
        self.last_point = None
        self.stroke = e
      elif type(e) == Point:
        if self.last_point is None:
          self.gui.canvas.draw(self.stroke.color,
              self.stroke.thickness * e.p, e.pos)
        else:
          self.gui.canvas.draw(self.stroke.color,
              self.stroke.thickness * e.p, self.last_point.pos, e.pos)
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
    dur = self.get_duration()
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
      self.set_progress(val * self.get_duration())
      self.gui.redraw()



  ############################################################################
  # ------------------------------ File I/O -------------------------------- #
  ############################################################################

  def exp_png(self, fname, size, times):
    if fname.lower().endswith('.png'):
      exporter.to_png(self.lecture, fname[:-4], size, times)
    else:
      exporter.to_png(self.lecture, fname, size, times)

  def exp_pdf(self, fname, size, times):
    if fname.lower().endswith('.pdf'):
      exporter.to_pdf(self.lecture, fname[:-4], size, times)
    else:
      exporter.to_pdf(self.lecture, fname, size, times)

  def exp_swf(self, fname):
    exporter.to_swf(self.lecture, self.audio.make_data(), fname)

  def save(self, fname = 'save.dcb'):
    if self.is_recording():
      self.record(False)
    recorder.save(fname, self.lecture, self.audio.make_data())
    self.gui.canvas.dirty = False

  def load(self, fname = 'save.dcb'):
    try:
      rtn = recorder.load(fname)
      if len(rtn) > 0:
        self.lecture = rtn[0]
        self.audio.load_data(rtn[1])
        self.gui.canvas.dirty = False
        self.gui.set_fname(fname)
        return True
      return False
    except recorder.FormatError:
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
    elif arg == '--exp-pdf':
      config.export('pdf')
    elif arg == '--exp-swf':
      config.export('swf')
    else:
      fname = arg
  return config

if __name__ == '__main__':

  config = parse_args(sys.argv[1:])

  if config.help_req:
    Configuration.print_usage()
    sys.exit(0)

  if config.export_fmt is not None:
    if config.export_fmt == 'swf':
      lec, a = recorder.load(fname[0])
      exporter.to_swf(lec, a, fname[0][:-4] + '.swf')
    elif config.export_fmt == 'pdf':
      lec, a = recorder.load(fname[0])
      exporter.to_pdf(lec, fname[0][:-4] + '.swf')
    else:
      print 'Unknown flag "--exp-%s"' % fname[1]
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
