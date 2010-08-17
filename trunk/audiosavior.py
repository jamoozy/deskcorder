import alsaaudio
import wave
import time
import signal
import sys

class AudioSavior:
  def __init__(self):
    self.samples = []
    self.startTime = time.time()
    self.inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE,alsaaudio.PCM_NONBLOCK)
    self.inp.setchannels(1)
    self.inp.setrate(44100)
    self.inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    self.inp.setperiodsize(1000)
  def record(self):
    print "STARTED RECORDING" ; sys.stdout.flush()
    while True:
      l,data = self.inp.read()
      if l:
        self.samples.append(data)
  def save(self, fname = "strokes.wav"):
    w = wave.open('strokes.wav', 'wb')
    w.setnchannels(1)
    w.setframerate(44100)
    w.setsampwidth(2)
    for datum in self.samples:
      w.writeframes(datum)
    w.close()
    print "%d samples saved" % len(self.samples) ; sys.stdout.flush()
  def reset(self):
    self.samples = []
    self.startTime = time.time()

if __name__ == "__main__":
  import os
  a = AudioSavior()
  try:
    signal.signal(signal.SIGTERM, lambda signum, frame: a.save())
    a.record()
  except KeyboardInterrupt:
    a.save()
