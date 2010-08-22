import alsaaudio
import wave
import time
import signal
import sys
import base64
import xml.dom.minidom
import gobject

class InvalidOperationError(RuntimeError):
  def __init__(self, msg):
    RuntimeError.__init__(self, msg)

class Audio:
  def __init__(self):
    self.data = []  # K.I.S.S.  Data stored as a string.
    # next version: store an array of strings.  Do smart things to determine
    # when no one is talking.

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
    print 'Card name: %s' % a.inp.cardname()
    print ' PCM mode: %d' % a.inp.pcmmode()
    print ' PCM type: %d' % a.inp.pcmtype()

  def reset(self):
    self.data = []
    self.play_start = None
    self.recording = False
    self.paused = False

  def load_data(self, data, format):
    self.data = data
    self.format = format
    self.out.setformat(format)

  def is_recording(self):
    return self.inp is not None

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
    self.data.append([t, ''])
    self.recording = True
    gobject.timeout_add(100, self.record_tick)

  def record_tick(self):
    while self.recording:
      l,data = self.inp.read()
      # Drops 0-length data and data recorded while this is paused.
      if l > 0:
        if not self.paused:
          self.data[-1][1] += data
      else:
        return True
    else:
      return False

#  def compress_data(self):
#    '''Turns all list-type data into str-type.'''
#    for i in range(len(self.data)):
#      if type(self.data[i][1]) == list:
#        self.data[-1][1] = reduce(lambda a,b: a+b, self.data[-1][1])

  def play(self):
    if len(self.data) == 0 or len(self.data[0][1]) == 0:
      return
    self.play_init()
    gobject.timeout_add(100, self.play_tick)

  def play_init(self):
    self.play_start = time.time()
    self.play_iter1 = 0
    self.play_iter2 = self.period_size
    self.data_iter = 0

  def play_tick(self, ttpt = None):
    '''ttpt == "time to play to" so that things will only play when they
    should.'''
    if self.is_playing():
#      self.compress_data()
      if self.paused: return True
      # This has the effect of a do-while loop that loops until no more data
      # can be written to the speakers.
      while ttpt is None or ttpt >= self.data[self.data_iter][0]:
        data = self.data[self.data_iter][1][self.play_iter1:self.play_iter2]
        dt = time.time() - self.data[self.data_iter][0]
        if self.out.write(data) != 0:
          self.play_iter1 = self.play_iter2
          self.play_iter2 += self.period_size
          if self.play_iter1 >= len(self.data[self.data_iter][1]):
            self.play_iter1 = 0
            self.play_iter2 = self.period_size
            self.data_iter += 1
            if self.data_iter >= len(self.data):
              self.stop()
              return False
          elif self.play_iter2 > len(self.data[self.data_iter][1]):
            self.play_iter2 = len(self.data[self.data_iter][1])
        else:
          return self.is_playing()
      return self.is_playing()
    else:
      return False

  def is_playing(self):
    return self.play_start is not None

  def get_s_played(self):
    '''Computes and returns number of seconds played in this recording.'''
    if self.is_playing() and len(self.data) > 0 and self.play_iter1 < len(self.data[self.data_iter][1]):
      return self.play_iter1 / float(self.bytes_per_second)
    else:
      return -1

  def get_time_of_first_event(self):
    return self.data[0][0] if len(self.data) > 0 else -1

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

  def save(self, fname = "strokes.wav"):
    w = wave.open(fname, 'wb')
    w.setnchannels(self.channels)
    w.setframerate(self.period_size)
    w.setsampwidth(2)
    for data in self.data:
      w.writeframes(data[1])
    w.close()

  def open(self, fname = "strokes.wav"):
    dot = fname.rfind('.')
    self.format = '' if dot < 0 else fname[dot+1:]

    if self.format != 'wav': raise 'Not a wave file.'

    w = wave.open(fname, 'rb')
    self.data = [[0, w.readframes(-1)]]
    w.close()

  def reset(self):
    self.data = []
    self.startTime = time.time()

  def to_xml_tag(self, samples_per_tag = 1000):
    xml = ''
    for data in self.data:
      xml += '<audiofile time="%lf" format="%s" encode="b64">' % (self.data[0], self.format)
      xml += base64.b64encode(reduce(lambda a,b: a+b, self.data[1]))
      xml += '</audiofile>\n'
    return xml

  def from_xml_tag(self, tag):
    xmlDoc = xml.dom.minidom.parseString(tag)
    afs = xmlDoc.getElementsByTagName("audiofile")
    if len(afs) == 0:
      raise IOError('No <audiofile> tags found.')

    self.data = []
    for af in afs:
      self.data.append([float(af.getAttribute('time')), base64.b64decode(af.firstChild.wholeText)])

if __name__ == "__main__":
  import os
  a = Audio()

  if len(sys.argv) > 1 and sys.argv[1] == '--play':
    a.open()
    a.play()
  else:
    try:
      signal.signal(signal.SIGTERM, lambda signum, frame: a.save())
      a.record()
    except KeyboardInterrupt:
      a.save()
