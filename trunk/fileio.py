import os
import sys
import math
import base64
import xml.dom.minidom
import struct  # for binary conversions
import zlib    # to compress audio data in v0.1.x
import speex   # to compress audio data in v0.2.x
import wave
import tarfile
import tempfile
from shutil import rmtree

from datatypes import *

# Valid version numbers (ones we can load)
VALID_VERSIONS = [(0,1,0), (0,1,1), (0,1,2), (0,2,0)]

# Currently-supported formats.
FORMATS = {'dcx': "Deskcorder XML file",
           'dar': "Deskcorder archive",
           'dcb': "Deskcorder binary file"}

# Current default version.
DEFAULT_VERSION = (0,2,0)

# Magic number to appear at the beginning of every DCB file.
MAGIC_NUMBER = '\x42\xfa\x32\xba\x22\xaa\xaa\xbb'


class FormatError(Exception):
  '''Raised when an unrecoverable formatting error takes place.'''
  pass

class VersionError(FormatError):
  '''Raised when an unrecognized version is loaded.'''
  def __init__(self, v):
    FormatError.__init__(self, "Unrecognized version: %d.%d.%d" % v)


############################################################################
# -------------------- Reading and writing functions --------------------- #
############################################################################

def save_wavs(fname, audiofiles):
  audio = ''
  for af in audiofiles:
    audio += af[1]
  if fname.lower().endswith('.wav'):
    save_wav(fname, audio)
  else:
    save_wav(fname + '.wav', audio)

def save_wav(fname, audio):
  w = wave.open(fname, 'wb')
  w.setnchannels(1)
  w.setframerate(1024)
  w.setsampwidth(2)
  for data in audio:
    w.writeframes(data[1])
  w.close()

def load_wavs(fname):
  if fname.lower().endswith(".wav"):
    return load_wav(fname)
  else:
    return load_wav(fname + '.wav')

def load_wav(fname):
  w = wave.open(fname, 'rb')
  data = w.readframes(-1)
  w.close()
  return data



############################################################################
# ----------------------------- Public API ------------------------------- #
############################################################################

def load(fname, win_sz = (1,1)):
  '''Reads in a file and returns a 2-tuple of lecture an audio.'''
  try:
    if fname.lower().endswith(".dcx"):
      return _load_dcx(fname, win_sz)
    elif fname.lower().endswith(".dct"):
      return _load_dct(fname, win_sz)
    elif fname.lower().endswith(".dcb"):
      return DCB(fname, DEFAULT_VERSION).load()
    elif fname.lower().endswith(".dcd"):
      return DCD(fname, DEFAULT_VERSION).load()
    elif fname.lower().endswith(".dar"):
      return DAR(fname, DEFAULT_VERSION).load()
    else:
      return _load_dcb(fname, win_sz)
  except FormatError as e:
    print 'FormatError:', str(e)
    return ()

def save(fname, lec = None, adats = [], req_v = DEFAULT_VERSION):
  '''Writes out a lecture and set of audio snippets to a file.'''
  if lec is None: return
  if fname.lower().endswith(".dcx"):
    _save_dcx(fname, lec, adats, req_v)
  elif fname.lower().endswith(".dct"):
    _save_dct(fname, lec, adats, req_v)
  elif fname.lower().endswith(".dcb"):
    DCB(fname, req_v).save(lec, adats)
  elif fname.lower().endswith(".dcd"):
    DCD(fname, req_v).save(lec, adats)
  elif fname.lower().endswith(".dar"):
    DAR(fname, req_v).save(lec, adats)
  else:
    _save_dcb(fname, lec, adats, req_v)



############################################################################
# -------------------------------- DCB ----------------------------------- #
############################################################################

class DCB(object):
  '''Does Deskcorder Binary loading and saving.  Even after this format
  becomes deprecated, its functions are still used in its subclasses.'''
  def __init__(self, fname, version):
    '''Creates an empty DCB reader/writer.'''
    self.fname = fname
    self.v = version
    self.fp = None
    self.log = None
    self.lec = None
    self.adats = []

  def save(self, lec = None, adats = []):
    '''Writes a lecture and audio data to a file.'''
    if lec is None:
      return
    if self.v != DEFAULT_VERSION:
      raise VersionError(self.v)

    self.fp = open(self.fname, 'wb')
    self.log = open(self.fname + ".save_log", 'w')

    self.lec = lec
    self.adats = adats

    # --- header ---
    self.fp.write(DCB.MAGIC_NUMBER)
    self.fp.write(struct.pack("<III", self.v[0], self.v[1], self.v[2]))
    self.log.write("File version: (%d,%d,%d)\n" % self.v)
    if self.v[1] >= 2:
      self.fp.write(struct.pack("<f", lec.aspect_ratio))
      self.log.write('File has %d slides, ar = %.2f\n' \
          % (len(lec.slides), lec.aspect_ratio))
    else:
      self.log.write('File will have %d slides\n' % len(lec.slides))

    # --- slides ---
    self.fp.write(struct.pack("<I", len(lec)))
    for slide in lec.slides:  # Slide block
      self._save_slide(slide)

    # --- moves ---
    self.fp.write(struct.pack("<I", len(lec.moves)))  # number of moves sans mouse click
    self.log.write('%d positions\n' % len(lec.moves))
    self.log.flush()
    for m in lec.moves:
      self._save_move(m)

    # --- audio ---
    self.fp.write(struct.pack("<I", len(adats))) # number of audio files
    for af in self.adats:
      self._save_audio(af)

    self.fp.close()
    self.fp = None
    self.log.close()
    self.log = None

  def _save_slide(self, slide):
    '''Writes a slide to file in DCB format.'''
    self.fp.write(struct.pack("<QI", int(slide.t * 1000), len(slide))) # tstamp & number of strokes
    self.log.write('  slide: %d strokes at %.0fms\n' % (len(slide), slide.t))
    self.log.flush()
    for stroke in slide.strokes:  # Stroke block
      _save_stroke(fp, log, stroke, self.v)

  def _save_stroke(self, stroke):
    '''Writes a stroke to file in DCB format.'''
    self.fp.write(struct.pack("<I", len(stroke))) # number of points in stroke
    self.log.write('  stroke has %d points\n' % len(stroke))
    self.log.flush()
    if len(stroke) > 0:  # remainder of Stroke block
      # Stroke color
      if self.v == (0,2,0):
        self.fp.write(struct.pack("<ff", stroke.aspect_ratio, stroke.thickness))
        self.log.write("  stroke has ar = %.2f, th = %.2f\n" \
            % (stroke.aspect_ratio, stroke.thickness))
      self.fp.write(struct.pack("<fff", stroke.color[0], stroke.color[1], stroke.color[2]))
      self.log.write('  stroke color: (%.3f,%.3f,%.3f)\n' % stroke.color)
      self.log.flush()
      for point in stroke.points:
        self._save_point(point)

  def _save_point(self, point):
    '''Writes a point to file in DCB format.'''
    if self.v == (0,1,2):
      thickness = point.p / math.sqrt(2)
    else:
      thickness = point.p
    self.fp.write(struct.pack("<Qfff", point.t * 1000, point.x(), point.y(), thickness))
    self.log.write('    point (%.3f,%.3f) @ %.1f with %.2f%%\n' \
        % (point.x(), point.y(), point.t, thickness * 100))
    self.log.flush()

  def _save_move(self, move):
    '''Writes a move to file in DCB format.'''
    # point tstamp (ms), x, y
    self.fp.write(struct.pack("<Qff", move.t * 1000, move.x(), move.y()))
    self.log.write('  pos: (%.3f,%.3f) @ %fms\n' % (move.x(), move.y(), move.t))
    self.log.flush()

  def _save_audio(self, audio):
    '''Writes audio data to file in DCB format.'''
    if self.v[1] == 1:
      c_data = zlib.compress(audio[1], zlib.Z_BEST_COMPRESSION)
    elif self.v[1] == 2:
      s = speex.new(raw = True)
      c_data = s.encode(audio[1])

    # tstamp (ms), bytes of data in audio file
    self.fp.write(struct.pack("<QQ", int(audio[0] * 1000), len(c_data)))
    self.log.write('  audio @ %.2fs with %d bytes\n' % (audio[0], len(c_data)))
    self.log.flush()
    self.fp.write(c_data) # (compressed) audio data

  @staticmethod
  def bin_read(f, fmt):
    '''Reads file f using struct to get datatypes shown in fmt.'''
    return struct.unpack(fmt, f.read(struct.calcsize(fmt)))

  def load(self):
    '''Loads DCB-v0.x.x'''
    self.fp = open(self.fname, 'rb')
    self.log = open(self.fname + '.load_log', 'w')
    if self.fp.read(8) != MAGIC_NUMBER:
      raise FormatError("Magic number does not match.")
    self.log.write('Magic number!\n')

    self.v = DCB.bin_read(self.fp, "<III")  # file version
    self.log.write('version %d.%d.%d\n' % self.v)
    if self.v not in VALID_VERSIONS:
      raise VersionError(self.v)

    print 'File is DCB v%d.%d.%d' % self.v

    if self.v[0] == 0:
      self.lec = Lecture()
      self.log.write("We're at self.fp.tell():%d\n" % self.fp.tell())
      if self.v[1] == 2:
        aspect_ratio = DCB.bin_read(self.fp, "<f")[0]
        self.log.write('aspect ratio: %.2f\n' % aspect_ratio)
        self.log.flush()
        self.lec.aspect_ratio = aspect_ratio
      num_slides = DCB.bin_read(self.fp, "<I")[0]  # number of slides
      self.log.write('%d slides\n' % num_slides)
      self.log.flush()
      for slide_i in xrange(num_slides):
        self.log.write("  Slide %d\n" % slide_i)
        self._load_slide()

      # number of points
      self.log.write("We're at self.fp.tell():%d\n" % self.fp.tell())
      num_moves = DCB.bin_read(self.fp, "<I")[0]
      self.log.write('%d positions\n' % num_moves)
      self.log.flush()
      for pos_i in xrange(num_moves):
        self.log.write('  move %d\n' % pos_i)
        self.log.flush()
        self._load_move()

      self.adats = []
      if self.v != (0,1,0):
        # number of audio files
        self.log.write("We're at self.fp.tell():%d\n" % self.fp.tell())
        num_afs = DCB.bin_read(self.fp, "<I")[0]
        self.log.write('%d audio files\n' % num_afs)
        self.log.flush()
        for af_i in xrange(num_afs):
          self.log.write("  Audio %d\n" % af_i)
          self._load_audio()

    self.fp.close()
    self.log.close()
    try:
      return self.lec, self.adats
    finally:
      self.fp = None
      self.log = None
      self.lec = None
      self.adats = []

  def _load_slide(self):
    # tstamp of "clear" (ms), number of strokes in first slide
    self.log.write("  We're at self.fp.tell():%d\n" % self.fp.tell())
    t, num_strokes = DCB.bin_read(self.fp, "<QI")
    self.log.write('    %d strokes at %.1fs\n' \
        % (num_strokes, t / 1000.))
    self.log.flush()
    self.lec.append(t / 1000.)
    for stroke_i in xrange(num_strokes):
      self.log.write("  stroke %d\n" % stroke_i)
      self.log.flush()
      self._load_stroke()

  def _load_stroke(self):
    # number of points in this stroke, color (r,g,b)
    self.log.write("    We're at self.fp.tell():%d\n" % self.fp.tell())
    num_points = DCB.bin_read(self.fp, "<I")[0]
    if num_points > 0:
      if self.v[1] >= 2:
        aspect_ratio, thickness = DCB.bin_read(self.fp, "<ff")
        self.log.write('    thickness: %.2f\n' % thickness)
        self.log.flush()
      else:
        aspect_ratio = 4./3
        self.s_thickness = 0
      color = DCB.bin_read(self.fp, "<fff")
      self.log.write('    %d points with (%.1f,%.1f,%.1f)\n' \
          % ((num_points,) + color))
      self.log.flush()
      if self.v[1] >= 2:
        self.lec.last().append(Stroke(color, aspect_ratio, thickness))
      else:
        self.lec.last().append(color)
      for point_i in xrange(num_points):
        self.log.write("      point %d\n" % point_i)
        self._load_point()
    if self.v[1] < 2:  # finish pre-v0.2 conversion.
      self.lec.last().last().thickness = self.s_thickness / len(self.lec.last().last())
    else:
      self.log.write('    Empty stroke!\n')

  def _load_point(self):
    # timestamp (ms), x, y, "thickness"
    ts, x, y, th_pr = DCB.bin_read(self.fp, "<Qfff")
    self.log.write('        (%.3f,%.3f) @ %.1fs with %.1f%%\n' \
        % (x, y, ts / 1000., th_pr * 100))
    self.log.flush()
    if self.v[1] < 2:
      # if this is a previous version, "fake" the correct way of doing
      # thickness/pressure for the stroke/points.
      self.s_thickness += th_pr
      th_pr = 1.
    if self.v == (0,1,1) or self.v[1] == 2:
      self.lec[-1][-1].append((x, y), ts / 1000.0, th_pr)
    elif self.v == (0,1,2):
      self.lec[-1][-1].append((x, y), ts / 1000.0, th_pr * math.sqrt(2))

  def _load_move(self):
    # tstamp (ms), x, y
    self.log.write(  "We're at self.fp.tell():%d\n" % self.fp.tell())
    t, x, y = DCB.bin_read(self.fp, "<Qff")
    self.log.write('    (%.3f,%.3f) @ %.1fs\n' % (x, y, t / 1000.))
    self.log.flush()
    self.lec.add_move((x, y), t / 1000.)

  def _load_audio(self):
    '''Appends the audio entry at 'self.fp' to 'self.adats'.'''
    # tstamp (ms), bytes of (compressed) audio data
    self.log.write(  "We're at self.fp.tell():%d\n" % self.fp.tell())
    t, sz = DCB.bin_read(self.fp, "<QQ")
    self.log.write('    %d bytes at %.1fs\n' % (sz, t / 1000.))
    self.log.flush()
    # data
    if self.v[1] == 1:
      adat = [t / 1000, zlib.decompress(self.fp.read(sz))]
    elif self.v[1] == 2:
      s = speex.new(raw = True)
      adat = [t / 1000, s.decode(self.fp.read(sz))]
    self.adats.append(adat)



############################################################################
# -------------------------------- DCD ----------------------------------- #
############################################################################

class DCD(DCB):
  def __init__(self, fname, version):
    DCB.__init__(self, fname, version)

  def save(self, lecture = None, adats = []):
    if os.path.exists(self.fname):
      if os.path.isdir(self.fname):
        rmtree(self.fname)
      else:
        os.remove(self.fname)

    self.lec = lecture
    self.adats = adats

    os.mkdir(self.fname)
    self.fp = open(os.path.join(self.fname, "metadata"), "w")
    self.log = open(os.path.join(self.fname, "write.txt"), "w")
    self.fp.write(MAGIC_NUMBER + '\n')
    self.fp.write("%d.%d.%d\n" % self.v)
    self.fp.write("%f" % lecture.aspect_ratio)
    self.fp.close()
    i = 0
    for slide in lecture.slides:
      i += 1
      slide_dir = os.path.join(self.fname, "slide%03d" % i)
      os.mkdir(slide_dir)
      self.fp = open(os.path.join(slide_dir, "metadata"), "w")
      self.fp.write("%f\n" % slide.t)
      self.log.write("Slide started at %f\n" % slide.t)
      self.fp.close()
      j = 0
      for stroke in slide.strokes:
        j += 1
        fname = os.path.join(slide_dir, "stroke%03d" % j)
        self.log.write('\nStarting new stroke (%s) -------------\n\n' % fname)
        self.fp = open(fname, "w")
        self._save_stroke(stroke)
        self.fp.close()

    i = 0
    for adat in self.adats:
      i += 1
      fname = os.path.join(self.fname, "audio%03d" % i)
      self.fp = open(fname, "w")
      self.log.write("\nStarting new audio (%s) --------------\n\n" % fname)
      self._save_audio(adat)
      self.fp.close()

    self.log.write("\nDone.\n")
    self.log.close()
    self.log = None
    self.fp = None
    self.lec = None
    self.adats = None

  def load(self):
    if not os.path.exists(self.fname):
      raise IOError("No such directory: " + self.fname)

    # Get the information about the directory.
    info = os.walk(self.fname).next()
    info[1].sort()
    info[2].remove('metadata')
    if 'write_log.txt' in info[2]: info[2].remove('write_log.txt')
    if 'read_log.txt' in info[2]: info[2].remove('read_log.txt')
    info[2].sort()

    # Create the lecture.
    try:
      self.fp = open(os.path.join(self.fname, 'metadata'))
      self.log = open(os.path.join(self.fname, 'write-log.txt'), 'w')
      if self.fp.readline().strip() != MAGIC_NUMBER:
        raise FormatError("No (wrong) magic number.")
      v = tuple(map(lambda x: int(x), self.fp.readline().split('.')))
      ar = float(self.fp.readline())
      print 'File is DCD v%d.%d.%d' % v
    except IOError as e:
      print "Got error:", str(e)
      raise FormatError("Cannot parse file.")
    finally:
      self.fp.close()

    self.lec = Lecture()
    self.lec.aspect_ratio = ar
    
    # Populate it with stroke data.
    for slide_entry in info[1]:
      slide_dir = os.path.join(self.fname, slide_entry)
      slide_info = os.walk(slide_dir).next()
      slide_info[2].remove('metadata')
      slide_info[2].sort()

      self.fp = open(os.path.join(slide_dir, 'metadata'))
      self.lec.append(float(self.fp.readline()))
      self.fp.close()

      for stroke_entry in slide_info[2]:
        stroke_fname = os.path.join(slide_dir, stroke_entry)
        self.fp = open(stroke_fname, 'r')
        self._load_stroke()
        self.fp.close()

    # Populate it with audio data.
    adats = []
    for afile in info[2]:
      if afile.endswith('~') or afile.endswith(".txt"): continue
      afile_name = os.path.join(self.fname, afile)
      print 'audio file:', afile_name
      self.fp = open(afile_name, 'r')
      self._load_audio()
      self.fp.close()

    self.log.close()
    try:
      return self.lec, self.adats
    finally:
      self.log = None
      self.fp = None
      self.lec = None
      self.adats = []



############################################################################
# -------------------------------- DAR ----------------------------------- #
############################################################################

class DAR(DCD):
  def __init__(self, fname, version):
    self.fname = fname
    self.v = version
    self.fp = None
    self.log = None

  def save(self, lecture = None, adats = []):
    '''Saves the thing into a DAR archive.'''
    tempfile.mktemp(prefix='/home/jamoozy/.deskcorder/file-')
    pass # TODO write me

  def load(self):
    pass # TODO write me



############################################################################
# -------------------------------- DCX ----------------------------------- #
############################################################################

def _save_dcx(fname = 'save.dcx', lecture = [], audiofiles = [], req_v = DEFAULT_VERSION):
  '''Saves DCX-v0.1.1
  @lecture: A complex list.  See the Canvas object for details.
  @audiofiles: A list of (t,data) tuples'''
  f = open(fname, 'w')
  f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
  f.write('<document version="0.1.1">\n')
  for slide in lecture:
    if isinstance(slide, float):
      f.write('  <slide cleartime="%lf">\n' % slide)
    else:
      for stroke in slide:
        if len(stroke) <= 0: continue
        f.write('    <stroke color="#%s">\n' %
            reduce(lambda a,b: a+b,
              map(lambda x: '0' + x if len(x) == 1 else x,
              map(lambda x: hex(int(255*x))[2:], stroke[0][3]))))
        for point in stroke:
          thickness = point[2] / (math.sqrt(point[4][0] * point[4][0] +
                                            point[4][1] * point[4][1]))
          f.write('      <point x="%lf" y="%lf" time="%lf" thickness="%lf"/>\n' %
              (point[1][0] / float(point[4][0]), point[1][1] / float(point[4][1]), point[0], thickness))
        f.write('    </stroke>\n')
      f.write('  </slide>\n')
  for pos in positions:
    f.write('  <position x="%lf" y="%lf" time="%lf" />\n' %
        (pos[1][0] / float(pos[2][0]), pos[1][1] / float(pos[2][1]), pos[0]))
  if isinstance(audiofiles, list):
    for af in audiofiles:
      f.write('  <audiofile time="%lf" type="wav" encoding="base64">' % af[0])
      f.write(base64.b64encode(af[1]))
      f.write('</audiofile>\n')
  elif isinstance(audiofiles, str):
    f.write('  <audiofile type="wav" encoding="base64">')
    f.write(base64.b64encode(audiofiles))
    f.write('</audiofile>\n')
  f.write('</document>\n')
  f.flush()
  f.close()

def _load_dcx(fname = 'save.dcx', win_sz = (1,1)):
  '''Reads DCX-v*.
  @win_sz: Needed to scale the (x,y) coords.'''
  # TODO unify these functions.
  xmlDoc = xml.dom.minidom.parse(fname)
  document = xmlDoc.getElementsByTagName('document')[0]
  v_str = document.getAttribute('version')
  v = __parse_version_string(v_str) if v_str else (0,0,0)
  if v[0] == 0:
    if v[0] == 0:
      if v[1] == 0:
        trace, positions = load_dcx_0(fname, win_sz)
        return (trace, positions, [])
    if v[1] == 1:
      trace = []
      positions = []
      audiofiles = []
      for slide in document.getElementsByTagName('slide'):
        trace.append(float(slide.getAttribute('cleartime')))
        trace.append([])
        for stroke in slide.getElementsByTagName('stroke'):
          cs = stroke.getAttribute('color') # Of the form "#RRGGBB"
          color = tuple(map(lambda x: int(x, 16), (cs[1:3], cs[3:5], cs[5:])))
          trace[-1].append([])
          for point in stroke.getElementsByTagName('point'):
            trace[-1][-1].append((float(point.getAttribute('time')),
              (float(point.getAttribute('x')) * win_sz[0], float(point.getAttribute('y')) * win_sz[1]),
              float(point.getAttribute('thickness')) * math.sqrt(win_sz[0] * win_sz[0] + win_sz[1] * win_sz[1]),
              color, win_sz))
      for pos in document.getElementsByTagName('position'):
        positions.append((float(pos.getAttribute('time')),
          (float(pos.getAttribute('x')) * win_sz[0], float(pos.getAttribute('y')) * win_sz[1]),
          win_sz))
      for af in document.getElementsByTagName('audiofile'):
        if v[2] == 1:
          audiofiles.append((float(af.getAttribute('time')), base64.b64decode(af.firstChild.wholeText)))
        elif v[2] == 0:
          audiofiles.append(base64.b64decode(af.firstChild.wholeText))
        else:
          print 'Warning: unrecognized bug version: ' + v_str
      return trace, positions, audiofiles
  raise VersionError(v)


def save_dcx_0(fname = "save.dcx", trace = [], position = [], audiofiles = []):
  '''Saves DCX-v0.0.0'''
  output = open(fname, 'w')
  output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
  clears = []
  for clear in trace:
    if isinstance(clear, float):
      clears.append(clear)
  output.write('<document>\n')
  output.write('  <clears type="array">\n')
  for t in clears:
    output.write("    <clear type=\"float\">%lf</clear>\n" % (1000*t))
  output.write('  </clears>\n')
  output.write('  <slides type="array">\n')
  for slide in trace:
    if isinstance(slide, list):
      output.write('    <slide>\n')
      output.write('      <curves type="array">\n')
      for curve in slide:
        if len(curve) == 0:
          continue
        output.write('        <curve>\n')
        output.write('          <points type="array">\n')
        for pt in curve:
          output.write('            <point>\n')
          output.write("              <posx type=\"float\">%lf</posx>\n" % (pt[1][0]*640/pt[4][0]))
          output.write("              <posy type=\"float\">%lf</posy>\n" % (pt[1][1]*480/pt[4][1]))
          output.write("              <time type=\"float\">%lf</time>\n" % (1000*pt[0]))
          output.write("              <colorr type=\"integer\">%d</colorr>\n" % int(255*pt[3][0]))
          output.write("              <colorg type=\"integer\">%d</colorg>\n" % int(255*pt[3][1]))
          output.write("              <colorb type=\"integer\">%d</colorb>\n" % int(255*pt[3][2]))
          output.write("              <thickness type=\"float\">%lf</thickness>\n" % (pt[2]*(math.sqrt(640*640+480*480))/(math.sqrt(pt[4][0]*pt[4][0]+pt[4][1]*pt[4][1]))))
          output.write('            </point>\n')
        output.write('          </points>\n')
        output.write('        </curve>\n')
      output.write('      </curves>\n')
      output.write('    </slide>\n')
  output.write('  </slides>\n')
  output.write('  <positions type="array">\n')
  for pt in position:
    output.write('    <position>\n')
    output.write("      <posx type=\"float\">%lf</posx>\n" % (pt[1][0]*640/pt[2][0]))
    output.write("      <posy type=\"float\">%lf</posy>\n" % (pt[1][1]*480/pt[2][1]))
    output.write("      <time type=\"float\">%lf</time>\n" % (1000*pt[0]))
    output.write('    </position>\n')
  output.write('  </positions>\n')
  output.write('</document>\n')
  output.flush()
  output.close()

  save_wavs(fname, audiofiles)

def load_dcx_0(fname = 'strokes.dcx', window_size = (640,480)):
  '''Loads DCX-v0.0.0 into a (trace,position,audio) tuple.'''
  def get_xml_type(line, tag, typ):
    stag = '<%s type="%s">' % (tag, typ)
    etag = '</%s>' % tag
    if not line.startswith(stag):
      raise 'Bad dcx: expected %s' % stag
    substr = line[len(stag):line.find(etag)]
    num = float(substr) if typ == 'float' else int(substr)
    return num

  ifile = open(fname, 'r')
  state = 'start'
  trace = []
  position = []
  clears = []
  try:
    while True:
      line = ifile.next().strip()
      if state == 'start':
        if line != '<?xml version="1.0" encoding="UTF-8"?>':
          raise 'Bad dcx: expected <?xml version="1.0" encoding="UTF-8"?>'
        state = 'document'
      elif state == 'document':
        if line != '<document>':
          if line.startswith('<document'):
            raise VersionError(__parse_version_string(line[:-1] + '/' + line[-1]))
          else:
            raise "Bad dcx: expected <document>"
        state = 'clears'
      elif state == 'clears':
        if line != '<clears type="array">':
          raise 'Bad dcx: expected <clears type="array">'
        state = 'clear'
      elif state == 'clear':
        if line.startswith('<clear type="float">'):
          endpos = line.find('<', 20)
          try:
            clears.append(float(line[20:endpos]) / 1000.0)
          except ValueError:
            print 'Warning dcx has non-float clear: "%s"' % line[20:endpos]
        elif line == "</clears>":
          state = 'slides'
        else:
          raise 'Bad dcx: expected <clear type="float"> or </clears>'
      elif state == 'slides':
        if line != '<slides type="array">':
          raise 'Bad dcx: expected <slides type="array">'
        state = 'slide'
      elif state == 'slide':
        if line != '<slide>':
          raise 'Bad dcx: expected <slide>'
        trace.append(clears.pop(0))
        trace.append([])
        state = 'curves'
      elif state == 'curves':
        if line != '<curves type="array">':
          raise 'Bad dcx: expected <curves type="array">'
        state = 'curve'
      elif state == 'curve':
        if line != '<curve>':
          raise 'Bad dcx: <curve>'
        trace[-1].append([])
        state = 'points'
      elif state == 'points':
        if line != '<points type="array">':
          raise 'Bad dcx: expected <points type="array">'
        state = 'point'
      elif state == 'point':
        if line == '<point>':
          try:
            posx = get_xml_type(ifile.next().strip(), 'posx', 'float') * window_size[0]/640
            posy = get_xml_type(ifile.next().strip(), 'posy', 'float') * window_size[1]/480
            time = get_xml_type(ifile.next().strip(), 'time', 'float') / 1000.0
            colorr = get_xml_type(ifile.next().strip(), 'colorr', 'integer') / 255.0
            colorg = get_xml_type(ifile.next().strip(), 'colorg', 'integer') / 255.0
            colorb = get_xml_type(ifile.next().strip(), 'colorb', 'integer') / 255.0
            thickness = get_xml_type(ifile.next().strip(), 'thickness', 'float') * (math.sqrt(window_size[0]*window_size[0]+window_size[1]*window_size[1]))/(math.sqrt(640*640+480*480))
            trace[-1][-1].append((time, (posx, posy), thickness, (colorr, colorg, colorb), window_size))
            if ifile.next().strip() != '</point>':
              raise 'Bad dcx: expected </point>'
          except (StopIteration, ValueError):
            raise 'Bad dcx: expected posx, posy, time, colorr, colorg, colorb, thickness, and </point>'
        elif line == '</points>':
          state = '/curve'
        else:
          raise 'Bad dcx: expected <point>...</point>'
      elif state == '/curve':
        if line != '</curve>':
          raise 'Bad dcx: expected </curve>'
        state = '/curves'
      elif state == '/curves':
        if line == '</curves>':
          state = '/slide'
        elif line == '<curve>':
          trace[-1].append([])
          state = 'points'
        else:
          raise 'Bad dcx: expected </curves> or <curve>'
      elif state == '/slide':
        if line != '</slide>':
          raise 'Bad dcx: expected </slide>'
        state = '/slides'
      elif state == '/slides':
        if line == '<slide>':
          trace.append(clears.pop(0))
          trace.append([])
          state = 'curves'
        elif line == '</slides>':
          state = 'positions'
        else:
          raise 'Bad dcx: expected </slides> or <slide>'
      elif state == 'positions':
        if line != '<positions type="array">':
          raise 'Bad dcx: expected <positions type="array">'
        state = 'position'
      elif state == 'position':
        if line == '<position>':
          try:
            posx = get_xml_type(ifile.next().strip(), 'posx', 'float') * window_size[0] / 640.0
            posy = get_xml_type(ifile.next().strip(), 'posy', 'float') * window_size[1] / 480.0
            time = get_xml_type(ifile.next().strip(), 'time', 'float') * window_size[1] / 1000.0
            position.append((time, (posx,posy), window_size))
            if ifile.next().strip() != '</position>':
              raise 'Bad dcx: expected </position>'
          except (ValueError, StopIteration):
            raise 'Bad dcx: expected posx, posy, time'
        elif line == '</positions>':
          state = '/document'
        else:
          raise 'Bad dcx: expected <position>...</position> or </positions>'
      elif state == '/document':
        if line != '</document>':
          raise 'Bad dcx: expected </document>'
        state = 'done'
      elif state == 'done':
        if len(line) > 0:
          print "Warning, extra at end of file: %s" % line
  except StopIteration:
    pass
  ifile.close()
  return (trace, position)

def _save_dct(fname = "save.dct", trace = [], positions = [], audiofiles = [], req_v = DEFAULT_VERSION):
  '''Saves DCT-v0.0.0'''
  output = open(fname, 'w')
  clears = []
  for clear in trace:
    if isinstance(clear, float):
      clears.append(clear)
  for t in clears:
    output.write("%lf " % (1000*t))
  output.write("\n")
  for slide in trace:
    if isinstance(slide, list):
      for curve in slide:
        for pt in curve:
          output.write("%d %d %lf %d %d %d %lf\n" % (pt[1][0]*640/pt[4][0], pt[1][1]*480/pt[4][1], 1000*pt[0], int(255*pt[3][0]), int(255*pt[3][1]), int(255*pt[3][2]), pt[2]))
        output.write("\n")
      output.write("\n")
  output.flush()
  output.close()

  write_wavs(fname, audiofiles)


def __parse_version_string(version):
  '''Returns a tuple of (maj, min, bug) read from the version string.  If For
  each missing entry, 0 is assumed.'''
  dot1 = version.find('.')
  dot2 = version.find('.', dot1 + 1)

  # Negates the need to check if find() returned < 0.
  if dot1 < 0: dot1 = len(version)
  if dot2 < 0: dot2 = len(version)

  maj = version[:dot1]
  min = version[dot1+1:dot2]
  bug = version[dot2+1:]

  try:
    maj = int(maj) if len(maj) > 0 else 0
  except ValueError:
    print 'Warning, "%s" not a valid version sub-string (expected integer) assuming 0' % maj
    maj = 0

  try:
    min = len(min) > 0 and int(min) or 0
  except ValueError:
    print 'Warning, "%s" not a valid version sub-string (expected integer) assuming 0' % min
    min = 0

  try:
    bug = len(bug) > 0 and int(bug) or 0
  except ValueError:
    print 'Warning, "%s" not a valid version sub-string (expected integer) assuming 0' % bug
    bug = 0

  return maj, min, bug

def _load_dct(fname = 'save.dct', win_sz = (1,1)):
  '''Reads the input 'f' and assumes that the file's pointer is already at one
  past the version string.  Returns a recursively-tupled representation of the
  contents of the file based on the version tuple given.'''

  f = open(fname, 'r')

  trace = []
  clears = []

  # FSM with 5 states:
  #   "tstamps"
  #     Start of file.  Parses a line of floats (clear times).
  #   "slides"
  #     Adds a new slide with a new stroke with a single point to the state.
  #   "slide-strokes"
  #     Appends
  try:
    v = __parse_version_string(f.next())
    if v == (0,0,0):
      while True:  # Will be broken by StopIteration exception
        line = f.next()
        if state == 'tstamps':
          if line == '\n':
            state = 'strokes'
          else:
            wbs.cleartimes = __read_cts(line)
            state = 'slides'
        elif state == 'slides':
          slide = WBSlide()
          stroke = WBStroke()
          point = __read_point(line)
          stroke.append(point)
          slide.append(stroke)
          state = 'slide-strokes'
        elif state == 'slide-strokes':
          if line == '\n':
            state = 'slides' if len(wbs.cleartimes) < slide_i else 'strokes'
          else:
            stroke.append(__read_point(line))
        elif state == 'strokes':
          stroke = WBStroke()
          stroke.append(__read_point(line))
          state = 'stroke-points'
        elif state == 'stroke-points':
          if line == '\n':
            state = 'strokes'
          else:
            stroke.append(__read_point(line))
        else:
          raise 'Non-reachable code reached!'
    else:
      raise VersionError("Warning: unsupported file version: %d.%d.%d" % v)
  except StopIteration:
    pass # Done reading!

  f.close()
  return trace, [], []

def __read_point(line):
  sp1 = line.find(' ')
  sp2 = line.find(' ', sp1 + 1)

  if sp1 < 0 or sp2 < 0:
    raise 'Malformatted file on line "%s"' % line

  return int(line[:sp1]), int(line[sp1+1:sp2]), float(line[sp2+1:])

def __read_cts(line):
  '''Reads the line of clear times from a DCT file.'''
  def float_or_grace(x):
    try:
      return float(x)
    except ValueError:
      print 'Warning, %s not a float.' % x
    return 0
  return map(float_or_grace, line.split(' '))

def _save_dct(fname = 'save.dct', trace = [], positions = [], audiofiles = []):
  '''Writes the contents of state to a file using the most current file
  version.'''
  output = open(fname, 'w')

  # Version line.
  output.write(WB_REC_VERSION_PREFIX + WB_REC_VERSION + "\n")

  # Spit out all the times at which the user hit "clear screen."
  for t in state.cleartimes:
    output.write("%lf " % t)
  output.write("\n")

  # Spit out all the slides (there should be len(state.cleartimes) of these).
  for slide in state.slides:
    for stroke in slide:
      for pt in stroke:
        output.write("%d %d %lf\n" % tuple(pt))
      output.write("\n")
    output.write("\n")

  # Spit out all the strokes that make up the currently-displayed, uncleared
  # slide.
  for stroke in state.strokes:
    for pt in stroke:
      output.write("%d %d %lf\n" % tuple(pt))
    output.write("\n")
  output.flush()
  output.close()


if __name__ == '__main__':
  t = [1000.0,
        [
          [(1000.1, (.0, .0), 1., (.0,.0,.0), (1,1)),
           (1000.2, (.2, .2), 1., (.0,.0,.0), (1,1)),
           (1000.3, (.4, .4), 1., (.0,.0,.0), (1,1))],
          [(1000.4, (.6, .6), 1., (.0,.0,.0), (1,1)),
           (1000.5, (.8, .8), 1., (.0,.0,.0), (1,1)),
           (1000.6, (1., 1.), 1., (.0,.0,.0), (1,1))]
        ],
       1005.0,
        [
          [(1005.1, (1., .0), 1., (.0,.0,.0), (1,1)),
           (1005.2, (.8, .2), 1., (.0,.0,.0), (1,1)),
           (1005.3, (.6, .4), 1., (.0,.0,.0), (1,1))],
          [(1005.4, (.4, .6), 1., (.0,.0,.0), (1,1)),
           (1005.5, (.2, .8), 1., (.0,.0,.0), (1,1)),
           (1005.6, (.0, 1.), 1., (.0,.0,.0), (1,1))]
        ]
      ]
  p = [(1003.1, (.1, 1.), (1,1)),
       (1003.2, (.1, .8), (1,1)),
       (1003.3, (.1, .6), (1,1)),
       (1003.3, (.1, .4), (1,1)),
       (1003.3, (.1, .2), (1,1)),
       (1003.4, (.1, .0), (1,1))]
  a = []
  lec = Lecture()
  lec.load_trace_data(t)
  lec.load_position_data(p)

  save('test.dcb', lec, a)
  tb,ab = load('test.dcb')

  if t != tb.make_trace_data() or p != tb.make_position_data() or a != ab:
    print "Binary errors detected."
    f = open('test_errors.log', 'w')
    f.write("wrote: " + str(t) + "\n")
    f.write("  got: " + str(tb.make_trace_data()) + "\n")
    f.write("wrote: " + str(p) + "\n")
    f.write("  got: " + str(tb.make_position_data()) + "\n")
    f.write("wrote: " + str(a) + "\n")
    f.write("  got: " + str(ab) + "\n")
    f.flush()
    f.close()
