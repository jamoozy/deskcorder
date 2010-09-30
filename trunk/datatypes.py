
##############################################################################
# ----------------------------- State classes ------------------------------ #
##############################################################################

class Lecture(object):
  '''The highest-level state object.

This object is the representation of one run of the program.  It's called a
``Lecture'' because originally, that's what it was, a lecture---the time
between when a professor or a TA started a class, to the time he or she ended
it.  More generally, you can think of this as a ``session''.'''
  class Iterator(object): def __init__(self, lec, offset = None):
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

    def seek(self, offset):
      self.offset = offset

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
      # Get me everything not yet returned, that should be displayed (may skip
      # the end part of a slide if between this call and the previous one
      # those things were drawn, but the screen was already cleared.  Poor
      # them -_- )
      else:
        abs_prog = self.offset + prog
        elems = []
        while self.has_next():
          e = self.next()
          if e.t <= self.last_prog: # shouldn't ever happen
            print "weird, it does happen"
          elif e.t <= abs_prog:
            elems.append(e)
          else:
            self._next.append(e)
            break
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
    self.events = []
    self.adats = []
    self.vdats = []  # XXX For a future release.

  def __str__(self):
    return 'Lecture with %d events, %d audio blocks, and %d video blocks' \
        % (len(self.events), len(self.adats), len(self.vdats))

  def __iter__(self):
    return Lecture.Iterator(self)

  def __getitem__(self, i):
    return self.events[i]

  def __len__(self):
    return len(self.events)

  def first(self):
    return self.events[0] if len(self.events) else None

  def last(self):
    '''Returns [] (not None) if empty so len() works.'''
    return self.events[-1] if len(self.events) > 0 else None

  def is_empty(self):
    return self.num_events() <= 0

  def get_first_event(self):
    try:
      return self.slides[0].strokes[0].points[0]
    except IndexError:
      return None

  def get_time_of_first_event(self):
    f = self.get_first_event()
    return f.utime() if f is not None else -1

  def get_last_event(self):
    try:
      return self.slides[-1].strokes[-1].points[-1]
    except IndexError:
      return None

  def get_time_of_last_event(self):
    l = self.get_last_event()
    return l.utime() if l is not None else -1

  def get_duration(self):
    '''Computes the duration in s of the lecture.'''
    return .0



############################################################################
# -------------------------------- Events -------------------------------- #
############################################################################

class Event(object):
  class Error(Exception):
    '''Represents a missing function in a class that extends Event.'''
    pass

  def __init__(self, t):
    self.t = t

  def utime(self):
    '''Returns the time this data was created.''' 
    raise self.t

  def make_data(self):
    '''Make data for this object.  This will be written or something to
    things and stuff.'''
    raise Event.Error('%s.make_data() not defined', self.__class__.__name__)

  def load_data(self, data):
    '''Load data into this object.  Class-specific.  Should be the same as
    what make_data() returns.'''
    raise Event.Error('%s.load_data() not defined', self.__class__.__name__)

class MouseEvent(Event):
  '''An event that has an (x,y) and time.'''
  def __init__(self, pos, t):
    Event.__init__(self, t)
    self.pos = pos

  def x(self):
    return self.pos[0]

  def y(self):
    return self.pos[1]

class Move(MouseEvent):
  '''Undrawn point (the pen is up).'''
  def __init__(self, pos, t, p):
    MouseEvent.__init__(self, pos, t)
    self.p = p  # \in [0,1] meaning no--full pressure

class Point(MouseEvent):
  '''Drawn point (the pen is down).'''
  def __init__(self, pos, t, p):
    MouseEvent.__init__(self, pos, t)
    self.p = p  # \in [0,1] meaning no--full pressure

  def __str__(self):
    return 'Point: (%f,%f) @ %f with %f%%' % (self.pos + (self.t, self.p * 100))

# FIXME Is this really needed?  Isnt' this just a Move with the state different?
class Drag(MouseEvent):
  '''Dragging something across the screen.'''
  def __init__(self, pos, t, i):
    MouseEvent.__init__(self, pos, t)
    self.i = i  # event ID of the thing we're dragging

class Click(MouseEvent):
  '''The mouse was clicked.  a.k.a. "mouse-down"'''
  pass

class Release(MouseEvent):
  '''The mouse was released.  a.k.a. "mouse-up"'''
  pass

class Record(Event):
  '''Something (A/V) started recording.'''
  def __init__(self, t, dat, dat_i):
    Event.__init__(self, t)
    self.lec_i = lec_i
    self.dat = dat

class Stop(Event):
  '''Something (A/V) stopped recording.'''
  def __init__(self, t, lec_i):
    Event.__init__(self, t)
    self.lec_i = lec_i

class Clear(Event):
  '''Clear the screen and set a new background.'''
  def __init__(self, t, bg):
    Event.__init__(self, t)
    self.bg = bg  # TODO something intelligent...

class Color(Event):
  '''The color changed.'''
  def __init__(self, t, color):
    Event.__init__(self, t)
    self.color = color

  def r(self):
    return self.color[0]

  def g(self):
    return self.color[1]

  def b(self):
    return self.color[2]

class Thickness(Event):
  '''The thickness changed.'''
  def __init__(self, t, thickness):
    Event.__init__(self, t)
    self.thickness = thickness

class Start(Event):
  '''The program was started.'''
  def __init__(self, t, ar):
    Event.__init__(self, t)
    self.aspect_ration = ar

class End(Event):
  '''The program was ended.'''
  def __init__(self, t):
    Event.__init__(self, t)

class Resize(Event):
  '''The screen was resized.'''
  def __init__(self, t, ar):
    Event.__init__(self, t)
    self.aspect_ration = ar



############################################################################
# --------------------- ?
############################################################################

class AudioData(object):
  '''Audio data.'''
  def __init__(self):
    pass

  def append(self, dat):
    pass

class VideoData(object):
  '''Video data.'''
  def __init__(self):
    pass

  def append(self, dat):
    pass
