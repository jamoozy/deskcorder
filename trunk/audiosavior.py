import alsaaudio
import wave
import time
import signal
import sys
import base64
import xml.dom.minidom

class AudioSavior:
  def __init__(self):
    self.data = []  # K.I.S.S.  Data stored as a string.
    # next version: store an array of strings.  Do smart things to determine
    # when no one is talking.

    self.startTime = time.time()

    self.playing = False
    self.recording = False

    self.rate = 44100
    self.channels = 1
    self.periodsize = 1000
    self.format = 'wav'

    self.inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE,alsaaudio.PCM_NONBLOCK)
    self.inp.setchannels(1)
    self.inp.setrate(44100)
    self.inp.setperiodsize(1000)
    self.inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)

    self.out = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK,alsaaudio.PCM_NORMAL)
    self.out.setchannels(1)
    self.out.setrate(44100)
    self.out.setperiodsize(1000)
    self.out.setformat(alsaaudio.PCM_FORMAT_S16_LE)

  def print_info(self):
    print 'Card name: %s' % a.inp.cardname()
    print 'PCM mode: %d'  % a.inp.pcmmode()
    print 'PCM type: %d'  % a.inp.pcmtype()

  def record(self):
    print "STARTED RECORDING" ; sys.stdout.flush()
    self.data.append('')
    while True:
      l,data = self.inp.read()
      if l > 0:
        self.data[-1] += data

  def play(self):
    print "PLAYING AUDIO"
    if self.format == 'wav':
      self.out.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    elif self.format == 'mp3':
      self.out.setformat(alsaaudio.PCM_FORMAT_MP3)
    else:
      raise 'Unrecognized format: "%s"' % self.format
    self.out.write(self.data)

  def pause(self):
    print 'pause() not implemented'

  def stop(self):
    print 'stop() not implemented'

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
