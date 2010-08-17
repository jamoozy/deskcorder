from whiteboard import WBState, WBSlide, WBStroke

# Should appear on first line, to denote which version was used.
WB_REC_VERSION_PREFIX = 'WB v'

# Current default version.
WB_REC_VERSION = '0.0.0'

# Currently-supported formats.
FORMATS = {'wbx': "Whiteboard XML file",
           'wbt': "Whiteboard text file",
           'wbr': "Whiteboard raw file"}



############################################################################
# -------------------- Reading and writing functions --------------------- #
############################################################################

def read(fname):
  '''Reads in a file and returns a tuple-rific '''
  f = open(fname, 'r')
  try:
    while True:
      line = f.next()
      version = '0'
      if line.startswith(WB_REC_VERSION_PREFIX):
        version = line[len(WB_REC_VERSION_PREFIX):].strip()
      return _read_file(_parse_version_string(version), f)
  except StopIteration:
    print '''Warning: %s is empty.''' % fname

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

def __read_file(v, f):
  '''Reads the input 'f' and assumes that the file's pointer is already at one
  past the version string.  Returns a recursively-tupled representation of the
  contents of the file based on the version tuple given.'''
  if v == (0,0,0):
    state = 'tstamps'
    wbs = WBState()
    slide = None
    stroke = None
    slide_i = 0

    # FSM with 5 states:
    #   "tstamps"
    #     Start of file.  Parses a line of floats (clear times).
    #   "slides"
    #     Adds a new slide with a new stroke with a single point to the state.
    #   "slide-strokes"
    #     Appends
    try:
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
    except StopIteration:
      pass # Done reading!
  else:
    print "Warning: unsupported file version: %d.%d.%d" % v

def __read_point(line):
  sp1 = line.find(' ')
  sp2 = line.find(' ', sp1 + 1)

  if sp1 < 0 or sp2 < 0:
    raise 'Malformatted file on line "%s"' % line

  return int(line[:sp1]), int(line[sp1+1:sp2]), float(line[sp2+1:])

def __read_cts(line):
  def float_or_grace(x):
    try:
      return float(x)
    except ValueError:
      print 'Warning, %s not a float.' % x
    return 0
  return map(float_or_grace, line.split(' '))

def write(fname, state):
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
