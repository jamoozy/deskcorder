import time
#import traceback

##############################################################################
# ----------------------------- State classes ------------------------------ #
##############################################################################

class Lecture(object):
  '''The highest-level state object.

This object is the representation of one run of the program.  It's called a
``Lecture'' because originally, that's what it was, a lecture---the time
between when a professor or a TA started a class, to the time he or she ended
it.  More generally, you can think of this as a ``session''.'''
  class State(object):
    def __init__(self):
      self.color = (.0,.0,.0)
      self.thickness = .01
      self.win_sz = (1.,1.)

    def aspect_ratio(self):
      return self.win_sz[0] / float(self.win_sz[1])

    def width(self):
      return self.win_sz[0]

    def height(self):
      return self.win_sz[1]

  class Iterator(object):
    '''Iterates over the events in a Lecture object.'''
    def __init__(self, events):
      self.events = events
      self.state = Lecture.State()
      self.offset = events[0].utime() if len(events) > 0 else 0
      self.i = 0  # i is always the next to be returned.
                  # When i has passed the end of lec, we're done.

    def __next__(self):
      '''Implements the "default" iterator next() function.'''
      return self.next()

    def seek_to_time(self, prog):
      '''Continue as though the last call to next() brought the iterator to
      prog.'''
      abs_prog = self.offset + prog
      self.i = 0  # reset
      # Increment until we're at one before what should be the next one.
      while self.events[self.i].utime() <= abs_prog: self.i += 1

    def seek(self, idx):
      '''Continue as though lecture[idx] is next.'''
      self.i = idx

    def has_next(self):
      return len(self.events) > self.i

    def _update_state(self, event):
      '''Updates the iterator state (the state of Deskcorder at the time
      this event was made) based on the event.'''
      if isinstance(event, Clear):
        pass
      elif isinstance(event, Thickness):
        self.state.thickness = event.thickness
      elif isinstance(event, Start):
        self.state.win_sz = (event.width(), event.height())
      elif isinstance(event, Color):
        self.state.color = event.color

    def peek(self):
      '''Return the next value without iterating.'''
      return self.events[self.i] if self.has_next() else None

    def next(self, prog = None):
      '''Two modes of operation:
  (1) Call without 'prog'ress and you will simply get the next element (slide,
     stroke, or point)
  (2) Call with progress, and you will get all elements between the last time
     you called this function and now.
     
[Note]: The only exception to (2) is when you use a seek().'''
      if prog is None:  # Default "get me the next one"
        if self.has_next():
          try:
            self._update_state(self.peek())
            return self.peek()
          finally:
            self.i += 1
        else:
          raise StopIteration("End of lecture.")
      # Get me everything not yet returned, that should be displayed (may skip
      # the end part of a slide if between this call and the previous one
      # those things were drawn, but the screen was already cleared.  Poor
      # them -_- )
      else:
        abs_prog = self.offset + prog
        elems = []
        while self.has_next():
          if self.peek().utime() > abs_prog: break
          self._update_state(self.peek())
          elems.append(self.peek())
          self.i += 1
        return elems

  def __init__(self):
    '''Initialize a blank state object.  If you have internal data (formerly
known as a "trace"), then you can just pass that here.'''
    self.state = Lecture.State() # keep track of line thickness, etc.
    self.events = []
    self.adats = []
    self.vdats = []  # XXX For a future release.

  def __str__(self):
    return 'Lecture with %d events, %d audio blocks, and %d video blocks' \
        % (len(self.events), len(self.adats), len(self.vdats))

  def __iter__(self):
    return Lecture.Iterator(self.events)

  def __getitem__(self, i):
    return self.events[i]

  def __len__(self):
    return len(self.events)

  def append(self, e):
    if isinstance(e, AudioRecord):
      self.adats.append(e.get_media())
    elif isinstance(e, VideoRecord):
      self.vdats.append(e.get_media())
    elif isinstance(e, ScreenEvent):
      print '''Warning: I'd prefer you use Lecture.resize((w,h))
             to Lecture.append(Resize(t,(w,h)))'''
      #print '  This grievous offense was committed at:', traceback.print_last()
      self.resize(e.size)
      return  # because resize handles everything
    elif isinstance(e, Color):
      self.state.color = e.color
    elif isinstance(e, Thickness):
      self.state.thickness = e.thickness
    elif isinstance(e, float):
      e = Clear(e, None)
    self.events.append(e)

  def resize(self, size):
    '''Registers with the lecture that the canvas has been resized.'''
    if isinstance(self.last(), ScreenEvent):
      self.last().size = size
    else:
      self.events.append(Resize(time.time(), size))
    self.state.win_sz = size

  def first(self):
    return self.events[0] if len(self.events) else None

  def last(self, typ = None):
    '''Gets the last event.  If typ is specified, gets the last event with
    type typ.  If there is no event with type = typ or the lecture is empty,
    returns None.'''
    if len(self.events) <= 0: return None
    if typ is None:
      return self.events[-1]
    else:
      i = -1
      try:  # search backward for type
        while not isinstance(self.events[i], typ): i -= 1
      except IndexError:
        return None
      return self.events[i]

  def last_points(self, max_num):
    '''Returns an array of up to 'max_num' of the last point events.  If the
    last event wasn't a point event, this will return [].'''
    events = []
    it = reversed(self.events)
    try:
      e = it.next()
      if isinstance(e, Point):
        events.append(e)
      else:
        return []
      while len(events) < max_num:
        e = it.next()
        if isinstance(e, Point): raise StopIteration
        events.append(e)
    except StopIteration:
      pass
    events.reverse()
    return events

  def last_slide_iter(self):
    '''Returns an iterator pointing to the first element of the last slide.'''
    it = Lecture.Iterator(self.last_slide())
    tevent = self.last(Thickness)
    if tevent is not None: it.state.thickness = tevent.thickness
    cevent = self.last(Color)
    if cevent is not None: it.state.color = cevent.color
    sevent = self.last(ScreenEvent)
    if sevent is not None: it.state.win_sz = sevent.size
    return it

  def last_slide(self):
    '''Convenience function that accumulates all the events between the last
    clear (which may be the start of the lecture) and the end of the
    lecture.'''
    events = []
    it = reversed(self.events)
    try:
      while True:
        e = it.next()
        if isinstance(e, Start) or isinstance(e, Clear): raise StopIteration
        events.append(e)
    except StopIteration:
      pass
    events.reverse()
    return events

  def events_to_time(self, t):
    '''Get all the events from the start of the slide that was active during
    time t up to and including the event with utime() == t.'''
    if len(self.events) <= 0: return []

    # Iterator and amount to change it on fail.
    i = len(self.events) / 2
    di = len(self.events) / 4

    # binary search to find element with utime() at point
    while self.events[i].utime() != t and di > 0:
      if self.events[i].utime() > t:
        i += di
      else:
        i -= di
      di /= 2    # Next time, only jump half.

    if i == 0: return [self.events[i]]

    events = [self.events[i]]  # what to return
    i -= 1

    # reverse linear "search" for first appearance of a clear screen-type of
    # event
    while isinstance(self.events[i], Clear) or isinstance(self.events[i], Start):
      events.append(self.events[i])
      i -= 1

    # TODO Include state.
    events.reverse()
    it = Lecture.Iterator(events)
    return it

  def num_events(self):
    return len(self.events)

  def is_empty(self):
    return self.num_events() <= 0

  def duration(self):
    '''Computes the duration in s of the lecture.'''
    if self.num_events() > 0:
      return self.last().utime() - self.first().utime()
    else:
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
    return self.t

class MouseEvent(Event):
  '''An event that has an (x,y) and time.'''
  def __init__(self, t, pos):
    Event.__init__(self, t)
    self.pos = pos

  def x(self):
    return self.pos[0]

  def y(self):
    return self.pos[1]

class Move(MouseEvent):
  '''Undrawn point (the pen is up).'''
  def __init__(self, t, pos):
    MouseEvent.__init__(self, t, pos)

class Point(MouseEvent):
  '''Drawn point (the pen is down).'''
  def __init__(self, t, pos, p):
    MouseEvent.__init__(self, t, pos)
    self.p = p  # \in [0,1] meaning no--full pressure

  def __str__(self):
    return 'Point: (%f,%f) @ %f with %f%%' % (self.pos + (self.t, self.p * 100))

class Drag(MouseEvent):
  '''Dragging something across the screen.'''
  def __init__(self, t, pos, i):
    MouseEvent.__init__(self, t, pos)
    self.i = i  # "object ID" of what's being dragged

  def x(self):
    Event.Error("Drag.x() invalid")

  def y(self):
    Event.Error("Drag.y() invalid")

  def dx(self):
    return self.pos[0]

  def dy(self):
    return self.pos[1]

class Click(MouseEvent):
  '''The mouse was clicked.  a.k.a. "mouse-down"'''
  pass

class Release(MouseEvent):
  '''The mouse was released.  a.k.a. "mouse-up"'''
  pass

class MediaEvent(Event):
  def __init__(self, t, i):
    '''Creates a new MediaEvent with a pointer to the media it effected.'''
    Event.__init__(self, t)
    self.i = i

  def get_media(self):
    raise Event.Error("%s.get_media() not implemented" \
        % self.__class__.__name__)

class MediaRecordEvent(MediaEvent):
  def __init__(self, t, i, media):
    MediaEvent.__init__(self, t, i)
    self.media = media

  def get_media(self):
    return self.media

class AudioRecord(MediaRecordEvent):
  '''Microphone started recording.'''
  def __init__(self, t, i, media):
    MediaRecordEvent.__init__(self, t, i, media)
    if not isinstance(media, AudioData):
      raise Event.Error("Data should be AudioData, not %s" % type(media))

class VideoRecord(MediaRecordEvent):
  '''Something (A/V) stopped recording.'''
  def __init__(self, t, i, media):
    MediaEvent.__init__(self, t, i, media)
    if not isinstance(media, VideoData):
      raise Event.Error("Data should be VideoData, not %s" % type(media))

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

class ScreenEvent(Event):
  '''Size-based event (event that affects the screen, only).'''
  def __init__(self, t, size):
    Event.__init__(self, t)
    self.size = size

  def width(self):
    return self.size[0]

  def height(self):
    return self.size[1]

  def aspect_ratio(self):
    return self.width() / float(self.height())

class Start(ScreenEvent):
  '''The program was started.'''
  pass

class End(ScreenEvent):
  '''The program was ended.'''
  pass

class Resize(ScreenEvent):
  '''The screen was resized.'''
  pass



############################################################################
# -------------------- Media (Audio and Video data) ---------------------- #
############################################################################

class Media(object):
  def __init__(self, t):
    self.dats = {}
    self.t = t

  def utime(self):
    '''Returns the timestamp.'''
    if t is None:
      return self.t
    else:
      self.t = t

class AudioData(Media):
  '''Audio data.'''

  # Enumeration of the various types that are used.
  RAW = 0
  MP3 = 1
  WAV = 2
  SPX = 3
  ZLB = 4
  NUM_TYPES = 5

  def __init__(self, t):
    Media.__init__(self, t)

  def add_type(self, key, data):
    if key not in range(self.NUM_TYPES):
      raise Event.Error("Invalid data type key: %s" % key)
    self.dats[key] = data

  def append(self, data):
    self.dats[RAW].append(data)

class VideoData(Media):
  '''Video data.'''

  # Enumeration of the various types that are used.
  RAW = 0
  MOV = 1
  MPG = 2
  NUM_TYPES = 3

  def load_media(self, key, data):
    if key not in range(self.NUM_TYPES):
      raise Event.Error("Invalid data type key: %s" % key)
    self.dats[key] = data
