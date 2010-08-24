#!/usr/bin/python

import math
import sys
import time
import thread
import os
import signal
import recorder


############################################################################
# ---------------------------- State classes ----------------------------- #
############################################################################

class Trace(object):
  '''A state object.  This object is the representation of the trace (get the
  name now???) of the pen through the run of a program.'''
  def __init__(self, t = None):
    '''Initialize a blank state object.  If you have internal data (formerly
    known as a "trace"), then you can just pass that here.'''
    self.slides = [] if t is None else [Slide(t)]
    self.moves = []  # like strokes, except the pen is up

  def load_trace_data(self, data):
    '''Load from the old, tuple-ized format.'''
    self.slides = []
    for s in data:
      if type(s) == float:
        self.slides.append(Slide(s))
      elif type(s) == list:
        self.slides[-1].load_trace_data(s)
      else:
        raise RuntimeError('Unrecognized type')

  def load_position_data(self, data):
    '''Load the position information from the old tuple-ized format.'''
    self.moves = [Point.from_position_data(p) for p in data]

  def make_trace_data(self):
    '''Converts this data into the old tuple-rific format.'''
    data = []
    for s in self.slides:
      data += s.make_trace_data()
    return data

  def make_position_data(self):
    return [m.make_position_data() for m in self.moves]

  def __str__(self):
    return 'Trace with %d slides' % len(self.slides)

  def __getitem__(self, i):
    return self.slides[i]

  def __len__(self):
    return len(self.slides)

  def first(self):
    return self.slides[0] if len(self.slides) else []

  def last(self):
    '''Returns [] (not None) if empty so len() works.'''
    return self.slides[-1] if len(self.slides) > 0 else []

  def add_move(self, pos, t = None):
    if type(pos) == tuple:
      if t is None:
        self.moves.append(Point(pos, time.time(), 0.))
      else:
        self.moves.append(Point(pos, t, 0.))
    elif type(pos) == Point:
      self.moves.append(pos)
    else:
      raise RuntimeError('Expected list, tuple, or Point')

  def append(self, s):
    if type(s) == Slide:
      self.slides.append(s)
    elif type(s) == float:
      self.slides.append(Slide(s))
    else:
      raise RuntimeError('Expected Slide or timestamp')

  def get_strokes(self):
    return [stroke for slide in self.slides for stroke in slide.strokes]

  def get_points(self):
    return [point for stroke in self.get_strokes() for point in stroke.points]

  def get_time_of_first_event(self):
    try:
      return self.slides[0].strokes[0].points[0].t
    except IndexError:
      return -1


class Slide(object):
  def __init__(self, t):
    self.t = t
    self.strokes = []

  def load_trace_data(self, data):
    for s in data:
      self.strokes.append(Stroke())
      self.strokes[-1].load_trace_data(s)

  def make_trace_data(self):
    return [self.t] + [[s.make_trace_data() for s in self.strokes]]

  def __str__(self):
    return "Slide with %d strokes" % len(self.strokes)

  def __getitem__(self, i):
    return self.strokes[i]

  def __len__(self):
    return len(self.strokes)

  def first(self):
    return self.strokes[0] if len(self.strokes) > 0 else []

  def last(self):
    '''Returns [] (not None) if empty so len() works.'''
    return self.strokes[-1] if len(self.strokes) > 0 else []

  def append(self, r, g = None, b = None):
    if type(r) == Stroke:
      self.strokes.append(r)
    elif type(r) == tuple:
      self.strokes.append(Stroke(r))
    elif g is not None and b is not None:
      self.strokes.append(Stroke((r,g,b)))
    else:
      raise RuntimeError('Expected Stroke, not %s' % str(type(r)))


class Stroke(object):
  def __init__(self, color = (0.,0.,0.)):
    self.color = color
    self.points = []

  def load_trace_data(self, data):
    self.color = data[0][3]
    for p in data:
      self.points.append(Point.from_trace_data(p))

  def make_trace_data(self):
    return [p.make_trace_data() + (self.color, (1, 1)) for p in self.points]

  def __str__(self):
    return 'Stroke with %d points' % len(self.points)

  def __getitem__(self, i):
    return self.points[i]

  def __len__(self):
    return len(self.points)

  def first(self):
    return self.points[0] if len(self.points) > 0 else []

  def last(self):
    '''Returns [] (not None) if empty so len() works.'''
    return self.points[-1] if len(self.points) > 0 else []

  def append(self, pos, t = None, r = None):
    if type(pos) == tuple:
      self.points.append(Point(pos, t, r))
    elif type(pos) == Point:
      self.points.append(pos)
    else:
      raise RuntimeError('Excpected tuple, list, or Point')

class Point(object):
  @staticmethod
  def from_trace_data(p):
    return Point((p[1][0]/p[4][0],p[1][1]/p[4][1]), p[0], p[2])

  @staticmethod
  def from_position_data(p):
    return Point((p[1][0]/p[2][0],p[1][1]/p[2][1]), p[0], .0)

  def __init__(self, pos, t, p):
    self.pos = pos
    self.t = t
    self.p = p

  def load_trace_data(self, data):
    self.pos = data[1]
    self.t = data[0]
    self.p = data[2]

  def make_trace_data(self):
    '''Return this as a (time, pos, pressure) tuple.'''
    return (self.t, self.pos, self.p)

  def make_position_data(self):
    return (self.t, self.pos, (1,1))

  def __str__(self):
    return 'Point: (%f,%f) @ %f with %f%%' % (self.pos + (self.t, self.p * 100))

  def x(self):
    return self.pos[0]

  def y(self):
    return self.pos[1]



############################################################################
# ---------------------------- Main Object ------------------------------- #
############################################################################

class Deskcorder:
  def __init__(self, layout, gui_enabled=True, audio_enabled=True):
    # Playback variables.
    self.play_time = None
    self.play_timer_id = None
    self.break_times = []
    self.last_pause = None

    self.gui = GUI(layout)
    self.gui.connect_new(self.reset)
    self.gui.connect_play(self.play)
    self.gui.connect_pause(self.pause)
    self.gui.connect_stop(self.stop)
    self.gui.connect_save(self.save)
    self.gui.connect_open(self.load)

    # Set up audio (or not).
    self.audio = Audio()
    self.gui.connect_record(self.record)

    if not audio_enabled: print 'Audio disabled'
    if not gui_enabled: print 'GUI disabled'

  def reset(self):
    '''Clears the state of the canvas and audio, as if the system had just
    started.'''
    if not self.gui.canvas.dirty or self.gui.dirty_ok():
      print 'resetting'
      self.gui.canvas.reset()
      self.audio.reset()
    else:
      print 'not resetting'

  def run(self, fname = None):
    '''Runs the program.'''
    self.gui.init()
    if fname is not None:
      try:
        self.load(fname)
      except IOError as e:
        print 'Error: %s"' % e.message

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
      try:
        self.audio.record()
      except recorder.InvalidOperationError:
        self.gui.record_pressed(False)
    else:
      self.audio.stop()

  def is_playing(self):
    '''Determines if this is playing or not.'''
    return self.play_time is not None

  def play(self, active):
    '''Start/stop playing what's in this file.'''
    if not active:
      self.stop()
      return

    if self.is_recording():
      self.stop()
      self.gui.play_pressed(True)

    self.audio.play_init()

    now = time.time()

    if self.is_playing() and self.is_paused():
      self.pause(now)

    self.gui.canvas.freeze()
    self.trace = self.gui.canvas.trace
    self.play_time = now

    # Playback iterators.
    self.slide_i = 0
    self.stroke_i = 0
    self.point_i = 0
    self.video_done = False

    self.gui.canvas.clear() # HACK to clear initially
    self.gui.timeout_add(50, self.play_tick)

  def earliest_event_time(self):
    return min(self.audio.get_time_of_first_event(), self.gui.canvas.trace.first().first().first().t)

  def play_tick(self):
    '''Do one 'tick' in the process of playing back what's stored in this
    program.'''

    if not self.is_playing(): return False
    if self.is_paused(): return True

    # dt is the difference between when the trace was recorded and when the
    # play button was hit.
    dt = self.play_time - self.earliest_event_time()
    for pause in self.break_times:
      dt += pause[1] - pause[0]

    now = time.time()

    if self.audio.is_playing():
      a_start = self.audio.get_current_audio_start_time()
      a_time = self.audio.get_s_played()
      print 'type(a_time):%s' % str(type(a_time))
      print 'audio: [%.3f,%.3f]' % (a_start, a_time)
      if a_start > 0:
        self.audio.play_tick(now - dt)
        if a_time > 0:
          a_prog = a_start + a_time - self.earliest_event_time()
          v_prog = now - self.play_time
          print 'audio:%3.2f' % a_prog
          print 'video:%3.2f' % v_prog
          print 'dt was %.2f' % dt
          dt += a_prog - v_prog
          print 'dt  is %.2f' % dt

    progress = now - dt

    print 'Progress: %.3fs' % progress

    # I'm simulating a do-while loop here.  This one is basically:
    #  1. While we still have stuff to iterate over, iterate.
    #  2. While the thing our iterator is pointing at is still old enough to
    #     draw, draw it.
    #  3. When we can't draw any more because the point our iterator is
    #     pointed at is too old, return True (run the function again later).
    #  4. When out iterator goes past the end of the trace object, return
    #     false (stop calling this function).
    while True:
      slide = self.trace[self.slide_i]
      # if we are after the slide's clear time but are still on the first point
      # of its first stroke, then clear the canvas.
      if slide.t <= progress and self.point_i == 0 and self.stroke_i == 0:
        self.gui.canvas.clear()

      stroke = slide[self.stroke_i]
      if len(stroke) > 0:

        point = stroke[self.point_i]
        if point.t <= progress:
          if self.point_i > 1:
            self.gui.canvas.draw(stroke.color, point.p, stroke[self.point_i-2].pos, stroke[self.point_i-1].pos, stroke[self.point_i].pos)
          elif self.point_i > 0:
            self.gui.canvas.draw(stroke.color, point.p, stroke[self.point_i-1].pos, stroke[self.point_i].pos)
          else:
            self.gui.canvas.draw(stroke.color, point.p, stroke[self.point_i].pos)
        else:
          return True

      if not self.play_iters_inc():
        if self.audio.get_current_audio_start_time() < 0:
          self.stop()
          return False
        return True


  def play_iters_inc(self):
    '''Increments all the iterators that have to do with the playing
    process.'''
    if len(self.trace) > 0:
      if len(self.trace[self.slide_i]) > 0:
        self.point_i += 1
        if self.point_i < len(self.trace[self.slide_i][self.stroke_i]):
          return True
        self.point_i = 0

        self.stroke_i += 1
        if self.stroke_i < len(self.trace[self.slide_i]):
          return True
        self.stroke_i = 0

      self.slide_i += 1
      if self.slide_i < len(self.trace):
        return True

    self.slide_i = 0
    self.stroke_i = 0
    self.point_i = 0
    self.video_done = True
    return False

  def pause(self, t):
    '''Pauses playback and audio recording.'''
    if self.is_playing():
      if self.last_pause == None:
        self.last_pause = t
        self.gui.pause_pressed(True)
        self.audio.pause()
      else:
        self.break_times.append((self.last_pause, t))
        self.last_pause = None
        self.gui.pause_pressed(False)
        self.audio.unpause()
    else:
      self.gui.pause_pressed(False)


  def is_paused(self):
    return self.last_pause is not None

  def done(self):
    '''The drawing portion is done playing back.  Wait for the speech portion
    to finish also.'''
    gobject.timeout_add(100, self.check_done)

  def check_done(self):
    if not self.audio.is_playing():
      self.stop()
      return False
    return True

  def stop(self):
    if self.is_paused():
      self.pause(time.time())
    self.audio.stop()
    self.gui.record_pressed(False)
    self.gui.play_pressed(False)
    self.gui.canvas.unfreeze()
    self.last_pause = None
    self.break_times = []
    self.play_time = None



  ############################################################################
  # ------------------------------ File I/O -------------------------------- #
  ############################################################################

  def save(self, fname = 'save.dcb'):
    if self.is_recording():
      self.record(False)
    if fname.lower().endswith(".dcx"):
      self.save_dcx(fname)
    elif fname.lower().endswith(".dct"):
      self.save_dct(fname)
    else:
      self.save_dcb(fname)
    self.gui.canvas.dirty = False

  def save_dcx(self, fname = "strokes.dcx"):
    recorder.save_dcx(fname, self.gui.canvas.trace, self.audio.make_data())

  def save_dct(self, fname = "strokes.dct"):
    recorder.save_dct(fname, self.gui.canvas.trace, self.audio.make_data())

  def save_dcb(self, fname = "strokes.dcb"):
    recorder.save_dcb(fname, self.gui.canvas.trace, self.audio.make_data())

  def load(self, fname = 'save.dcb'):
    if fname.lower().endswith('.dcx'):
      self.load_dcx(fname)
    elif fname.lower().endswith('.dct'):
      self.load_dct(fname)
    else:
      self.load_dcb(fname)
    self.gui.canvas.dirty = False

  def load_dcb(self, fname = 'save.dcb'):
    self.gui.canvas.trace, a = recorder.load_dcb(fname)
    self.audio.load_data(a)

  def load_dcx(self, fname = 'save.dcx'):
    self.gui.canvas.trace, a = recorder.load_dcx(fname)
    self.audio.load_data(a)

  def load_dct(self, fname = 'save.dcx'):
    self.gui.canvas.trace, a = recorder.load_dct(fname)
    self.audio.load_data(a)



##############################################################################
# -------------------------- Testing/Running ------------------------------- #
##############################################################################

if __name__ == '__main__':
  try: # to import a GUI module
    from qtgui import Canvas, GUI
    has_gui = True
  except ImportError:
    try:
      from gtkgui import Canvas, GUI
      has_gui = True
    except ImportError:
      from dummy import Canvas, GUI
      has_gui = False

  try: # to import an audio module
    from qtaudio import Audio
    audio = True
  except ImportError:
    try:
      from alsa import Audio
      audio = True
    except ImportError:
      from dummy import Audio
      audio = False

  fname = None
  if len(sys.argv) > 1:
    if sys.argv[1] == '-h' or sys.argv[1] == '--help':
      print 'Usage %s [-A|--no-audio]'
    elif sys.argv[1] == '-G' or sys.argv[1] == '--no-gui':
      has_gui = False
    elif sys.argv[1] == '-A' or sys.argv[1] == '--no-audio':
      audio = False
    elif sys.argv[1].startswith('--open='):
      fname = sys.argv[1][7:]
    else:
      print 'Unrecognized command: "%s"' % sys.argv[1]
  Deskcorder("layout.glade").run(fname)
