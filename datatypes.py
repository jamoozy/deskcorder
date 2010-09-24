
##############################################################################
# ----------------------------- State classes ------------------------------ #
##############################################################################

class Lecture(object):
  '''The highest-level state object.

This object is the representation of one run of the program.  It's called a
``Lecture'' because originally, that's what it was, a lecture---the time
between when a professor or a TA started a class, to the time he or she ended
it.  More generally, you can think of this as a ``session''.'''
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
    self.aspect_ratio = 4./3 # default-ish
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
  def __init__(self, color = (0.,0.,0.), aspect_ratio = 4./3, thickness = 0.01):
    self.color = color
    self.points = []
    self.aspect_ratio = aspect_ratio
    self.thickness = thickness

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
    self.p = p  # \in [0,1] meaning no--full pressure

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

