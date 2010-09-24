#!/usr/bin/python

import math
import sys
import time
import thread
import os
import signal

import recorder
import exporter


############################################################################
# ---------------------------- State classes ----------------------------- #
############################################################################

class Lecture(object):
  '''A state object.  This object is the representation of the lecture (get
  the name now???) of the pen through the run of a program.'''
  class Iterator(object):
    def __init__(self, lec, offset = None):
      self.lecture = lec
      self.last_prog = 0

      # This tells me what I'm returning.
      self._return_type = 'slide'

      # Difference between "I'm just about to start" and "I just finished" is
      # the difference in the value of this boolean.
      self.complete = False
      self.slide_i = 0
      self.strok_i = 0
      self.point_i = -1
      self._next = []
      self._inc(newStroke = True)
      self.offset = offset or self.lecture.get_time_of_first_event()

    def next(self, prog = None):
      '''Two modes of operation:
  1) Call without 'prog'ress and you will simply get the next element (slide,
     stroke, or point)
  2) Call with progress, and you will get all elements between the last time
     you called this function and now.'''
      if prog is None:  # Default "get me the next one"
        if self.has_next():
          if len(self._next) > 0:
            return self._next.pop()
          try:
            return self.lecture[self.slide_i][self.strok_i][self.point_i]
          finally:
            self._inc()
        else:
          return None
      # Get me everything not yet returned, that should be displayed
      # (may skip the end part of a slide if between this call and the previous
      # one those things were drawn, but the screen was already cleared.
      # Poor them -_- )
      else:
        abs_prog = self.offset + prog
        elems = []
        while self.has_next():
          e = self.next()
          if e.t <= self.last_prog: # shouldn't ever happen
            print "weird, it does happen"
            pass
          elif e.t <= abs_prog:
            elems.append(e)
          else:
            self._next.append(e)
            break
#          print e
        self.last_prog = abs_prog
        return elems
    
    def has_next(self):
      return (len(self._next) > 0) or (not self.complete)
    
    def _validate(self):
      if self.slide_i < len(self.lecture):
        while self.strok_i < len(self.lecture[self.slide_i]):
          if self.point_i < len(self.lecture[self.slide_i][self.strok_i]):
            return
          self.point = 0
          self.strok_i += 1
      self.complete = True
    
    def _inc(self, newStroke = False):
      self.point_i += 1
      newSlide = False
      while self.slide_i < len(self.lecture):
        if newSlide:
          self._next.insert(0, self.lecture[self.slide_i])
        while self.strok_i < len(self.lecture[self.slide_i]):
          if self.point_i < len(self.lecture[self.slide_i][self.strok_i]):
            if newStroke:
              self._next.insert(0, self.lecture[self.slide_i][self.strok_i])
            return
          self.point_i = 0
          self.strok_i += 1
          newStroke = True
        self.point_i = 0
        self.strok_i = 0
        self.slide_i += 1
        newSlide = True
      self.complete = True

  def __init__(self, t = None):
    '''Initialize a blank state object.  If you have internal data (formerly
    known as a "trace"), then you can just pass that here.'''
    self.slides = [] if t is None else [Slide(t)]
    self.moves = []  # like strokes, except the pen is up

  def __iter__(self):
    return Lecture.Iterator(self)

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
    return 'Lecture with %d slides' % len(self.slides)

  def __getitem__(self, i):
    return self.slides[i]

  def __len__(self):
    return len(self.slides)

  def first(self):
    return self.slides[0] if len(self.slides) else []

  def last(self):
    '''Returns [] (not None) if empty so len() works.'''
    return self.slides[-1] if len(self.slides) > 0 else []

  def is_empty(self):
    return self.num_strokes() <= 0

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

  def num_strokes(self):
    return reduce(lambda a,b: a+b, map(lambda x: len(x), self.slides), 0)

  def get_points(self):
    return [point for stroke in self.get_strokes() for point in stroke.points]

  def get_first_event(self):
    try:
      return self.slides[0].strokes[0].points[0]
    except IndexError:
      return None

  def get_time_of_first_event(self):
    f = self.get_first_event()
    return f.t if f is not None else -1

  def get_last_event(self):
    try:
      return self.slides[-1].strokes[-1].points[-1]
    except IndexError:
      return None

  def get_time_of_last_event(self):
    l = self.get_last_event()
    return l.t if l is not None else -1

  def percentage_to_tstring(self, pct):
    dur = self.get_duration()
    if dur == 0:
      return "0:00"
    else:
      amt = int(dur * pct)
      return "%d:%02d" % (amt / 60, amt % 60)

  def get_duration(self):
    '''Computes the duration in s of the lecture.'''
    last = self.get_time_of_last_event()
    first = self.get_time_of_first_event()
    print 'last:%f first:%f' % (last, first)
    return last - first


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

  def r(self):
    return self.color[0]

  def g(self):
    return self.color[1]

  def b(self):
    return self.color[2]

  def append(self, pos, t = None, r = None):
    if type(pos) == tuple:
      self.points.append(Point(pos, t, r))
    elif type(pos) == Point:
      self.points.append(pos)
    else:
      raise RuntimeError('Excpected tuple, list, or Point')

  def get_start_t(self):
    if len(self) == 0:
      return 0
    return self.first().t

  t = property(get_start_t)

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
  def __init__(self, gui_enabled=True, audio_enabled=True):
    # Playback variables.
    self.play_time = None
    self.break_times = []
    self.last_pause = None

    self.lecture = Lecture(time.time())

    self.audio = Audio()
    self.gui = GUI(self.lecture)

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
    self.reset_iters_to_progress()

  def reset_iters_to_progress(self):
    self.slide_i = 0
    self.stroke_i = 0
    self.point_i = 0

    if self.lecture.is_empty(): return

    ttpt = self.progress + self.earliest_event_time()
    for i in xrange(1,len(self.gui.canvas.lecture)):
      if self.gui.canvas.lecture[i].t > ttpt:
        self.slide_i = i - 1
        while not self.play_iters_valid():
          continue
        return

    self.slide_i = len(self.gui.canvas.lecture) - 1
    self.play_iters_valid() # makes sure they are, if they can be.

  def get_duration(self):
    start_t = self.earliest_event_time()
    end_t = self.latest_event_time()
    return (end_t - start_t) if start_t >= 0 and end_t >= 0 else .0

  def earliest_event_time(self):
    video_t = self.gui.canvas.lecture.get_time_of_first_event()
    audio_t = self.audio.get_time_of_first_event()
    if audio_t >= 0 and video_t >= 0:
      return min(audio_t, video_t)
    elif video_t >= 0:
      return video_t
    else:
      return audio_t

  def latest_event_time(self):
    video_t = self.gui.canvas.lecture.get_time_of_last_event()
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

  def run(self, fname = None):
    '''Runs the program.'''
    self.gui.init()
    if fname is not None:
      try:
        self.load(fname)
      except IOError as e:
        print 'Could not load file, %s: %s"' % (fname, e.message)

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
    return self.progress >= 0 and self.progress <= self.get_duration()

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
    self.lecture = self.gui.canvas.lecture

    # Playback iterators.
    self.slide_i = 0
    self.stroke_i = 0
    self.point_i = 0
    self.video_done = False

    # prev & curr time play_tick() was called and progress in seconds.
    self.play_time = now
    self.prev_now = now
    self.curr_now = self.prev_now
    self.progress = 0

    self.gui.canvas.clear() # XXX hack to clear initially for GTK+ version
    self.gui.timeout_add(50, self.play_tick)

  def play_tick(self):
    '''Do one 'tick' in the process of playing back what's stored in this
    program.'''

    if not self.is_playing():
      #print 'Not playing'
      return False
    if self.is_paused():
      #print 'Paused'
      return True
    if self.get_duration() <= 0:
      #print 'Empty'
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

    # updating GUI
    self.gui.progress_slider_value(self.progress / self.get_duration())
    ttpt = self.progress + self.earliest_event_time()
    self.gui.canvas.ttpt = ttpt
    #print 'prog:%.1fs' % self.progress

    # I'm simulating a do-while loop here.  This one is basically:
    #  1. While we still have stuff to iterate over, iterate.
    #  2. While the thing our iterator is pointing at is still old enough to
    #     draw, draw it.
    #  3. When we can't draw any more because the point our iterator is
    #     pointed at is too old, return True (run the function again later).
    #  4. When out iterator goes past the end of the lecture object, return
    #     false (stop calling this function).
    while not self.video_done and self.play_iters_valid():
      slide = self.lecture[self.slide_i]
      # if we are after the slide's clear time but are still on the first point
      # of its first stroke, then clear the canvas.
      if slide.t <= ttpt and self.point_i == 0 and self.stroke_i == 0:
        self.gui.canvas.clear()

      stroke = slide[self.stroke_i]
      if len(stroke) > 0:
        point = stroke[self.point_i]
        if point.t <= ttpt:
          if self.point_i > 1:
            self.gui.canvas.draw(stroke.color, point.p,
                stroke[self.point_i-2].pos,
                stroke[self.point_i-1].pos,
                stroke[self.point_i].pos)
          elif self.point_i > 0:
            self.gui.canvas.draw(stroke.color, point.p,
                stroke[self.point_i-1].pos,
                stroke[self.point_i].pos)
          else:
            self.gui.canvas.draw(stroke.color, point.p,
                stroke[self.point_i].pos)
        else:
          return True

      if not self.play_iters_inc() and a_time < 0:
        self.stop()
        return False
    return self.check_done()

  def play_iters_valid(self):
    if self.slide_i < len(self.lecture):
      if self.stroke_i < len(self.lecture[self.slide_i]):
        if self.point_i < len(self.lecture[self.slide_i][self.stroke_i]):
          return True
    return self.play_iters_inc()

  def play_iters_inc(self):
    '''Increments all the iterators that have to do with the playing
    process.'''
    if len(self.lecture) > 0:
      if len(self.lecture[self.slide_i]) > 0:
        self.point_i += 1
        if self.point_i < len(self.lecture[self.slide_i][self.stroke_i]):
          return self.play_iters_valid()
        self.point_i = 0

        self.stroke_i += 1
        if self.stroke_i < len(self.lecture[self.slide_i]):
          return self.play_iters_valid()
        self.stroke_i = 0

      self.slide_i += 1
      if self.slide_i < len(self.lecture):
        return self.play_iters_valid()

    self.slide_i = 0
    self.stroke_i = 0
    self.point_i = 0
    self.video_done = True
    return False

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
    print 'progress moved to %.0f%%' % (val * 100)
    if self.is_empty():
      print "  --> but I'm empty"
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



  ############################################################################
  # ------------------------------ File I/O -------------------------------- #
  ############################################################################

  def exp_png(self, fname, size, times):
    if fname.lower().endswith('.png'):
      exporter.to_png(self.gui.canvas.lecture, fname[:-4], size, times)
    else:
      exporter.to_png(self.gui.canvas.lecture, fname, size, times)

  def exp_pdf(self, fname, size, times):
    if fname.lower().endswith('.pdf'):
      exporter.to_pdf(self.gui.canvas.lecture, fname[:-4], size, times)
    else:
      exporter.to_pdf(self.gui.canvas.lecture, fname, size, times)

  def save(self, fname = 'save.dcb'):
    if self.is_recording():
      self.record(False)
    recorder.save(fname, self.gui.canvas.lecture, self.audio.make_data())
    self.gui.canvas.dirty = False

  def load(self, fname = 'save.dcb'):
    try:
      rtn = recorder.load(fname)
      if len(rtn) > 0:
        self.gui.canvas.lecture, a = recorder.load(fname)
        self.audio.load_data(a)
        self.gui.canvas.dirty = False
        self.gui.set_fname(fname)
        return True
      return False
    except recorder.FormatError:
      return False



##############################################################################
# -------------------------- Testing/Running ------------------------------- #
##############################################################################

def parse_args(args):
  fname, audio, video = None, None, None
  for arg in args:
    if arg == '-h' or arg == '--help':
      print 'Usage %s [-A|--no-audio]'
    elif arg == '-G' or arg == '--no-gui':
      has_gui = False
    elif arg == '-A' or arg == '--no-audio':
      audio = 'dummy'
    elif arg.startswith('--use-gui='):
      video = arg[10:]
    elif arg.startswith('--use-audio='):
      audio = arg[12:]
      pass
    else:
      fname = arg
  return fname, audio, video

if __name__ == '__main__':
  # valid video modules in preferred order
  VALID_AV_MODULES = ['linux', 'mac', 'qt', 'dummy']

  fname, audio, video = parse_args(sys.argv[1:])

  if audio is not None:
    try:
      Audio = __import__(audio).Audio
    except AttributeError:
      audio = None
      print 'audio module "%s" not found' % audio

  if audio is None:
    for a in VALID_AV_MODULES:
      try:
        Audio = __import__(a).Audio
        audio = a
        break
      except AttributeError:
        pass

  if video is not None:
    try:
      Canvas = __import__(video).Canvas
      GUI = __import__(video).GUI
    except AttributeError:
      video = None
      print 'video module "%s" not found' % video

  if video is None:
    for v in VALID_AV_MODULES:
      try:
        GUI = __import__(v).GUI
        video = v
        break
      except AttributeError:
        pass

  print 'using %s audio and %s gui' % (audio, video)
  Deskcorder().run(fname)
