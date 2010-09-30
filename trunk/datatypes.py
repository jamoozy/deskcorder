
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
    class State(object):
      def __init__(self):
        self.color = (.0,.0,.0)
        self.thickness = .01
        self.win_sz = (1.,1.)

      def aspect_ratio(self):
        return self.win_sz[0] / float(self.win_sz[1])

    def __init__(self):
      self.lec = lec
      self.state = Lecture.Iterator.State()
      self.offset = lec.first.utime()
      self.i = 0  # i is always the next to be returned.
                  # When i has passed the end of lec, we're done.

    def seek_to_time(self, prog):
      abs_prog = self.offset + prog
      self.i = 0  # reset
      # Increment until we're at one before what should be the next one.
      while self.lec.events[self.i].utime() <= abs_prog: self.i += 1

    def seek(self, idx):
      '''Continue as though lecture[idx] is next.'''
      self.i = idx

    def has_next(self):
      return self.lec.num_events() > self.i

    def _update_state(self, event):
      '''Updates the iterator state (the state of Deskcorder at the time
      this event was made) based on the event.'''
      if type(event) == Clear:
        pass
      elif type(event) == Thickness:
        self.state.thickness = event.thickness
      elif type(event) == Start:
        self.state.win_sz = (event.w, event.h)
      elif type(event) == Color:
        self.color = event.color

    def peek(self):
      '''Return the next value without iterating.'''
      return self.lec[self.i] if self.has_next() else None

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
          elems.append(self.peek())
          self.i += 1
        return elems

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

  def append(self, e):
    if type(e) == AudioRecord:
      self.adats.append(e.get_media())
    elif type(e) == VideoRecord:
      self.vdats.append(e.get_media())
    self.events.append(e)

  def first(self):
    return self.events[0] if len(self.events) else None

  def last(self):
    '''Returns [] (not None) if empty so len() works.'''
    return self.events[-1] if len(self.events) > 0 else None

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
    raise self.t

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
    MouseEvent.__init__(self, pos, t)

class Point(MouseEvent):
  '''Drawn point (the pen is down).'''
  def __init__(self, t, pos, p):
    MouseEvent.__init__(self, pos, t)
    self.p = p  # \in [0,1] meaning no--full pressure

  def __str__(self):
    return 'Point: (%f,%f) @ %f with %f%%' % (self.pos + (self.t, self.p * 100))

class Drag(MouseEvent):
  '''Dragging something across the screen.'''
  def __init__(self, t, pos, i):
    MouseEvent.__init__(self, pos, t)
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
  def __init__(self, t, i);
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
    if type(media) != AudioData:
      raise Event.Error("Data should be AudioData, not %s" % type(media))

class VideoRecord(MediaRecordEvent):
  '''Something (A/V) stopped recording.'''
  def __init__(self, t, i, media):
    MediaEvent.__init__(self, t, i, media)
    if type(media) != VideoData:
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

class Start(Event):
  '''The program was started.'''
  def __init__(self, t, ar):
    Event.__init__(self, t)
    self.aspect_ratio = ar

class End(Event):
  '''The program was ended.'''
  def __init__(self, t):
    Event.__init__(self, t)

class Resize(Event):
  '''The screen was resized.'''
  def __init__(self, t, w, h):
    Event.__init__(self, t)
    self.w = w
    self.h = h

  def aspect_ratio(self):
    return self.w / float(self.h)



############################################################################
# --------------------- ?
############################################################################

class Media(object):
  def __init__(self):
    self.files = []

class AudioData(Media):
  '''Audio data.'''

  # Enumeration of the various types that are used.
  MP3 = 0
  WAV = 1
  SPX = 2
  TYPES = [None] * 3

  def load_media(self, key, data):
    if key not in self.TYPES:
      raise Event.Error("Invalid data type key: %s" % key)
    self.files[key] = data

class VideoData(Media):
  '''Video data.'''

  # Enumeration of the various types that are used.
  MOV = 0
  MPG = 1
  RAW = 2
  TYPES = [None] * 3

  def load_media(self, key, data):
    if key not in self.TYPES:
      raise Event.Error("Invalid data type key: %s" % key)
    self.files[key] = data
