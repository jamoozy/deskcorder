import alsaaudio
import wave
import time
import signal
import sys
import base64
import xml.dom.minidom
import gobject

class AudioSavior:
  def __init__(self):
    self.data = []  # K.I.S.S.  Data stored as a string.
    # next version: store an array of strings.  Do smart things to determine
    # when no one is talking.

    self.startTime = time.time()

    self.playing = False
    self.recording = False
    self.paused = False

    self.rate = 44100
    self.channels = 1
    self.period_size = 1000
    self.format = 'wav'

    # Once it's init'd, it will start to collect data, so don't init it until
    # it's time to record.
    self.inp = None

    self.out = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK,alsaaudio.PCM_NONBLOCK)
    self.out.setchannels(self.channels)
    self.out.setrate(self.rate)
    self.out.setperiodsize(self.period_size)
    self.out.setformat(alsaaudio.PCM_FORMAT_S16_LE)

  def print_info(self):
    print 'Card name: %s' % a.inp.cardname()
    print 'PCM mode: %d'  % a.inp.pcmmode()
    print 'PCM type: %d'  % a.inp.pcmtype()

  def record(self):
    '''Start recording.  This will not block.  It init's the recording process.
    This AudioSavior will continue recording until stop() gets called.'''
    if self.playing: raise 'Already playing.'

    print "STARTED RECORDING" ; sys.stdout.flush()
    self.inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE,alsaaudio.PCM_NONBLOCK)
    self.inp.setchannels(1)
    self.inp.setrate(44100)
    self.inp.setperiodsize(1000)
    self.inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    self.data.append('')
    self.recording = True
    gobject.timeout_add(100, self.record_tick)

  def record_tick(self):
    while self.recording:
      l,data = self.inp.read()
      # Drops 0-length data and data recorded while this is paused.
      if l > 0:
        if not self.paused:
          self.data[-1] += data
      else:
        print 'Out of data.'
        return True
    else:
      print 'Stopped.'
      return False

  def play(self):
    if self.format == 'wav':
      self.out.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    elif self.format == 'mp3':
      self.out.setformat(alsaaudio.PCM_FORMAT_MP3)
    else:
      raise 'Unrecognized format: "%s"' % self.format

    if len(self.data) == 0 or len(self.data[0]) == 0:
      return

    self.playing = True
    self.play_iter1 = 0
    self.play_iter2 = self.period_size
    self.data_iter = 0
    gobject.timeout_add(100, self.play_tick)

  def play_tick(self):
    if self.playing:
      if self.paused: return True
      # This has the effect of a do-while loop that loops until no more data
      # can be written to the speakers.
      while True:
        data = self.data[self.data_iter][self.play_iter1:self.play_iter2]
        if self.out.write(data) != 0:
          self.play_iter1 = self.play_iter2
          self.play_iter2 += self.period_size
          if self.play_iter1 >= len(self.data[self.data_iter]):
            self.play_iter1 = 0
            self.play_iter2 = self.period_size
            self.data_iter += 1
            if self.data_iter >= len(self.data):
              self.stop()
              return False
          elif self.play_iter2 > len(self.data[self.data_iter]):
            self.play_iter2 = len(self.data[self.data_iter])
        else:
          return self.playing
    else:
      return False

  def pause(self):
    self.paused = True

  def unpause(self):
    self.paused = False

  def stop(self):
    self.paused = False
    self.recording = False
    self.playing = False
    if self.inp is not None:
      self.inp.close()
      self.inp = None

  def save(self, fname = "strokes.wav"):
    w = wave.open(fname, 'wb')
    w.setnchannels(1)
    w.setframerate(44100)
    w.setsampwidth(2)
    w.writeframes(self.data)
    w.close()
    print "%d of audio data saved" % len(self.data) ; sys.stdout.flush()

  def open(self, fname = "strokes.wav"):
    dot = fname.rfind('.')
    self.format = '' if dot < 0 else fname[dot+1:]

    if self.format != 'wav': raise 'Not a wave file.'

    w = wave.open(fname, 'rb')
    self.data = w.readframes(-1)
    w.close()

  def reset(self):
    self.data = []
    self.startTime = time.time()

  def to_xml_tag(self, samples_per_tag = 1000):
    xml  = '<audio format="%s" encode="b64">\n' % self.format
    xml += '  <sample size="%d">' % len(self.data)
    xml += base64.b64encode(reduce(lambda a,b: a+b, self.data))
    xml += '  </sample>\n'
    xml += '</audio>\n'
    return xml

  def from_xml_tag(self, tag):
    xmlDoc = xml.dom.minidom.parseString(tag)
    audios = xmlDoc.getElementsByTagName("audio")
    if len(audios) == 0:
      raise 'No <audio> tags found.'
    elif len(audios) > 1:
      print 'Warning: expected one <audio> tag but got %d.  Using first.' % len(tags)

    audio = audios[0]
    self.data = ''
    for sample in audio.getElementsByTagName("sample"):
      self.data += base64.b64decode(sample.childNodes[0].wholeText)

if __name__ == "__main__":
  import os
  a = AudioSavior()

  if len(sys.argv) > 1 and sys.argv[1] == '--play':
    a.open()
    a.play()
  else:
    try:
      signal.signal(signal.SIGTERM, lambda signum, frame: a.save())
      a.record()
    except KeyboardInterrupt:
      a.save()
