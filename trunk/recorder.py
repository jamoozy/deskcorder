import math
import base64
import xml.dom.minidom
import struct  # for binary conversions
import zlib    # to compress audio data
import wave

# Should appear on first line, to denote which version was used.
WB_REC_VERSION_PREFIX = 'WB v'

# Current default version.
WB_REC_VERSION = '0.0.0'

# Currently-supported formats.
FORMATS = {'dcx': "Whiteboard XML file",
           'dct': "Whiteboard text file",
           'dcr': "Whiteboard raw file"}

# Magic number to appear at the beginning of every DCB file.
DCB_MAGIC_NUMBER = '\x42\xfa\x32\xba\x22\xaa\xaa\xbb'


def VersionError(Exception):
  '''Raised when an unexpected version is encountered by one of the load
  functions.'''
  def __init__(self, v):
    Exception.__init__(self, "Could not import version %d.%d.%d" % v)

def FormatError(Exception):
  '''Raised when an unrecoverable formatting error takes place.'''
  def __init__(self, v):
    Exception.__init__(self, "File could not be read.")



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

def load(fname, win_sz = (640, 480)):
  '''Reads in a file and returns a tuple-rific trace, positions, audio'''
  if fname.lower().endswith(".dcx"):
    return load_dcx(fname, win_sz)
  elif fname.lower().endswith(".dct"):
    return load_dct(fname, win_sz)
  else:
    return load_dcb(fname, win_sz)

def save(fname, trace = [], positions = [], audiofiles = []):
  '''Writes out a file and returns a tuple-rific trace, positions, audio'''
  if fname.lower().endswith(".dcx"):
    return save_dcx(fname, win_sz)
  elif fname.lower().endswith(".dct"):
    return save_dct(fname, win_sz)
  else:
    return save_dcb(fname, win_sz)

def save_dcb(fname = 'save.dcb', trace = [], positions = [], audiofiles = []):
  '''Writes DCB-v0.1.1'''
  f = open(fname, 'wb')
  f.write(DCB_MAGIC_NUMBER)
  f.write(struct.pack("<III", 0, 1, 1))  # file version
  f.write(struct.pack("<I", len(trace) / 2))
  for slide in trace:
    if type(slide) == float:
      f.write(struct.pack("<Q", int(slide * 1000)))
    else:
      f.write(struct.pack("<I", len(slide)))
      for stroke in slide:
        f.write(struct.pack("<I", len(stroke)))
        if len(stroke) > 0:
          f.write(struct.pack("<fff", stroke[0][3][0], stroke[0][3][1], stroke[0][3][2]))
          for point in stroke:
            x = point[1][0] / float(point[4][0])
            y = point[1][1] / float(point[4][1])
            thickness = point[2] / (math.sqrt(point[4][0] * point[4][0] +
                                              point[4][1] * point[4][1]))
            f.write(struct.pack("<Qfff", point[0] * 1000, x, y, thickness))
      f.write(struct.pack("<I", len(positions)))
      for pos in positions:
        x = pos[1][0] / float(pos[2][0])
        y = pos[1][1] / float(pos[2][1])
        f.write(struct.pack("<Qff", pos[0], x, y))
      f.write(struct.pack("<I", len(audiofiles)))
      for af in audiofiles:
        c_data = zlib.compress(af[1], zlib.Z_BEST_COMPRESSION)
        f.write(struct.pack("<QQ", af[0], len(c_data)))
        f.write(c_data)
  f.flush()
  f.close()

def load_dcb(fname = 'save.dcb', win_sz = (640,480)):
  '''Saves DCB-v0.1.1'''
  f = open(fname, 'rb')
  if f.read(8) != DCB_MAGIC_NUMBER:
    raise AttributeError("Magic number does not match.")

  v = struct.unpack("<III", f.read(4 + 4 + 4))  # file version
  if v[0] == 0:
    if v[1] == 1:
      trace = []
      positions = []
      audiofiles = []
      num_slides = struct.unpack("<I", f.read(4))[0]
      for slide_i in range(num_slides):
        t, num_strokes = struct.unpack("<QI", f.read(8 + 4))
        trace.append(t / 1000.0)
        trace.append([])
        for stroke_i in range(num_strokes):
          trace[-1].append([])
          num_points, r, g, b = struct.unpack("<Ifff", f.read(4 * 4))
          for point_i in range(num_points):
            ts, x, y, th = struct.unpack("<Qfff", f.read(8 + 4 * 3))
            trace[-1][-1].append((ts / 1000.0, (x * win_sz[0], y * win_sz[1]), th * math.sqrt(win_sz[0] * win_sz[0] + win_sz[1] * win_sz[1]), (r,g,b), win_sz))
      num_positions = struct.unpack("<I", f.read(4))[0]
      for pos_i in range(num_positions):
        t, x, y = struct.unpack("<Qff", f.read(8 + 4 + 4))
        positions.append((t, (x * win_sz[0], y * win_sz[1]), win_sz))
      num_afs = struct.unpack("<I", f.read(4))[0]
      for af_i in range(num_afs):
        t, sz = struct.unpack("<QQ", f.read(8 + 8))
        audiofiles.append([t, zlib.decompress(f.read(sz))])
  f.close()
  return trace, positions, audiofiles

def save_dcx(fname = 'save.dcx', trace = [], positions = [], audiofiles = []):
  '''Saves DCX-v0.1.1
  @trace: A complex list.  See the Canvas object for details.
  @positions: A list of (t,(x,y),(w,h)) tuples
  @audiofiles: A list of (t,data) tuples'''
  f = open(fname, 'w')
  f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
  f.write('<document version="0.1.1">\n')
  for slide in trace:
    if type(slide) == float:
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
  if type(audiofiles) == list:
    for af in audiofiles:
      f.write('  <audiofile time="%lf" type="wav" encoding="base64">' % af[0])
      f.write(base64.b64encode(af[1]))
      f.write('</audiofile>\n')
  elif type(audiofiles) == str:
    f.write('  <audiofile type="wav" encoding="base64">')
    f.write(base64.b64encode(audiofiles))
    f.write('</audiofile>\n')
  f.write('</document>\n')
  f.flush()
  f.close()

def load_dcx(fname = 'save.dcx', win_sz = (640, 480)):
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
        trace, positions = openXML(fname, win_sz)
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


def write_dcx_0(fname = "save.dcx", trace = [], position = [], audiofiles = []):
  '''Saves DCX-v0.0.0'''
  output = open(fname, 'w')
  output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
  clears = []
  for clear in trace:
    if type(clear) == float:
      clears.append(clear)
  output.write('<document>\n')
  output.write('  <clears type="array">\n')
  for t in clears:
    output.write("    <clear type=\"float\">%lf</clear>\n" % (1000*t))
  output.write('  </clears>\n')
  output.write('  <slides type="array">\n')
  for slide in trace:
    if type(slide) == list:
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

def load_dcx_O(fname = 'strokes.dcx', window_size = (640,480)):
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

def save_dct(fname = "save.dct", trace = [], positions = [], audiofiles = []):
  '''Saves DCT-v0.0.0'''
  output = open(fname, 'w')
  clears = []
  for clear in trace:
    if type(clear) == float:
      clears.append(clear)
  for t in clears:
    output.write("%lf " % (1000*t))
  output.write("\n")
  for slide in trace:
    if type(slide) == list:
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

def load_dct(fname = 'save.dct', win_sz = (640, 480)):
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

def save_dct(fname = 'save.dct', trace = [], positions = [], audiofiles = []):
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
