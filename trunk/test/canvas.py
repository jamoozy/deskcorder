#!/usr/bin/python

import pygame, time, sys

import recorder



class WBStroke:
  '''A series of timestamped points, recorded from a "mouse down" to a "mouse
  up" event.'''
  def __init__(self, points=[]):
    '''Creates a new stroke as a series of points.'''
    if type(points) == list:
      self.points = points
    elif type(points) == tuple:
      self.points = [points]
    else:
      raise 'Invalid type for points: %s expected tuple or list' % type(points)

    # Check the points are a list of 3-tuples.
    for point in self.points:
      if type(point) != tuple or len(point) != 3:
        raise 'Internal error: Mal-formatted points'

  def append(self, x, y, t):
    '''Appends a point to this stroke.'''
    self.points.append((x, y, t))


class WBSlide:
  '''A series of strokes that appear simultaneously on the canvas.  These are
  between the start, end, or canvas-clear events.'''
  def __init__(self, strokes=[]):
    '''Create a slide that contains several strokes.'''
    if type(strokes) == WBStroke():
      self.strokes = [strokes]
    elif type(strokes) == list:
      self.strokes = strokes
    else:
      raise "Invalid type for argument 'strokes': %s" % type(strokes)

  def append(stroke):
    '''Appends the stroke to this slide.'''
    if type(stroke) != WBStroke:
      raise 'Unrecognized type appended: "%s" expected WBStroke' % type(stroke)
    self.strokes.append(stroke)


class WBState:
  '''Succinctly, collection of slides.  Contains the data to reproduce (in
  real-time) the run of a program.'''
  def __init__(self, cleartimes=[], slides=[], strokes=[]):
    assert type(cleartimes) == list
    assert type(slides) == list
    assert type(strokes) == list
    self.cleartimes = cleartimes
    self.slides = slides
    self.strokes = strokes

  def append(item):
    '''Appends a WBSlide or WBStroke to this WBState.'''
    if type(item) == WBSlide:
      self.slides.append(item)
      self.cleartimes.append
    elif type(item) == WBStroke:
      self.strokes.append(item)
    elif type(item) == float:
      self.cleartimes.append(item)
    else:
      raise "Invalid type for appending to a WBState: %s" % type(item)



white = 255,255,255
black =   0,  0,  0

class WBCanvas:
  def __init__(self, screen, colorscheme='default', width=640, height=480):
    self.screen = screen
    self.height = height
    self.width = width
    self.toolnum = 0
    self.state = recorder.WBState
    self.is_running = True
    if colorscheme == 'default':
      self.bgcolor = black
      self.strokecolor = white
    elif colorscheme == 'black-on-white':
      self.bgcolor = white
      self.strokecolor = black
    else:
      self.bgcolor = black
      self.strokecolor = white
      print 'Unrecognized colorscheme: "%s", using "default"' % colorscheme
    self.screen.fill(self.bgcolor)

  def mousedown(self, button, x):
    self.oldpos = x
    self.current = []
    self.current.append(x + (1000*time.time(),))

  def mousemove(self, buttons, x, dx):
    if buttons[0] == 1:
      pygame.draw.line(self.screen, white, self.oldpos, x, 2)
      self.oldpos = x
      self.current.append(x + (1000*time.time(),))
#    elif buttons == (0,0,1):
#      pygame.draw.circle(self.screen, black, x, 10)

  def mouseup(self, button, x):
    self.state.strokes.append(self.current)
    self.current = []
    pass

  def keydown(self, key):
    if (key == pygame.K_q or key == pygame.K_q) and pygame.key.get_mods() & pygame.KMOD_CTRL:
      self.is_running = False
    elif key == pygame.K_c:
      self.state.cleartimes.append(1000*time.time())
      self.state.slides.append(self.state.strokes)
      self.state.strokes = []
      self.screen.fill(self.bgcolor)
    elif key == pygame.K_s:
      recorder.write('strokes.out', self.state)

  def keyup(self, key):
    pass

  def selecttool(self, toolnum):
    self.toolnum = toolnum

  def whichtool(self):
    return self.toolnum

  def handleevent(self, event):
    if event.type == pygame.MOUSEBUTTONDOWN:
      self.mousedown(event.button, event.pos)
    if event.type == pygame.MOUSEBUTTONUP:
      self.mouseup(event.button, event.pos)
    if event.type == pygame.MOUSEMOTION:
      self.mousemove(event.buttons, event.pos, event.rel)
    if event.type == pygame.KEYDOWN:
      self.keydown(event.key)
    if event.type == pygame.KEYUP:
      self.keyup(event.key)

class ProgArgs:
  def __init__(self, needhelp=False, inname=None, colorscheme='default', width=640, height=480):
    self.needhelp = needhelp
    self.inname = inname
    self.colorscheme = colorscheme
    self.width = width
    self.height = height
    pass

def main(progargs=ProgArgs()):
  import sys, time

  pygame.init()
  size = width,height = progargs.width,progargs.height
  screen = pygame.display.set_mode(size)
  wbc = WBCanvas(screen, progargs.colorscheme, width, height)
  while wbc.is_running:
    for event in pygame.event.get():
      if event.type == pygame.QUIT or \
         event.type == pygame.KEYUP and event.key \
         in [pygame.K_q, pygame.K_ESCAPE]: sys.exit()
      wbc.handleevent(event)
    pygame.display.flip()
    time.sleep(0.05)
  pygame.quit()



##############################################################################
# --------------------- Argument parsing begins here ----------------------- #
##############################################################################

def parse_dims(progargs, dims):
  '''Parse the argument to the '--dimensions=' argument.  Expects [int]x[int]
and complains if that's not what's given.'''
  xloc = dims.find('x')
  try:
    progargs.width = int(dims[:xloc])
    progargs.height = int(dims[xloc+1:])
  except:
    progargs.needhelp = True
    print "Invalid format: %s\nExpected [int]x[int]\n" % dims

def parse_args(args):
  '''Parses the arguments to the program.  See print_help() for full details,
or just run this program with '-h' or '--help'.'''
  progargs = ProgArgs()
  skip = False
  for i in range(len(args)):
    if skip: continue
    if args[i] == '-h' or args[i] == '--help':
      progargs.needhelp = True
    elif args[i] == '--infile':
      skip = True
      progargs.inname = args[i+1]
    elif args[i].startswith('--infile='):
      progargs.inname = args[i][9:]
    elif args[i] == '--colorscheme':
      skip = True
      progargs.colorscheme = args[i+1]
    elif args[i].startswith('--colorscheme='):
      progargs.colorscheme = args[i][14:]
    elif args[i] == '--dimensions':
      progargs,
    elif args[i].startswith('--dimensions='):
      parse_dims(progargs, args[i][13:])
    else:
      print "Unrecognized argument: %s" % args[i]
  return progargs

def print_help():
  '''Prints the usage and help details for this program.'''
  print '''Usage: %s [args]
  args:
    -h --help
      Print this help and exit.
    --infile=[infile]
      Load the file and play its contents, then give control back to the user.
    --colorscheme=[colorscheme]
      Choose the colorscheme.  Choices are:
          'default'
          'black-on-white'
    --dimensions=[dims]
      Choose the dimensions of the canvas.  Default is 640x480.  Format is
      [int]x[int]
  Equal signs optional for all arguments.
''' % sys.argv[0]

if __name__ == '__main__':
  '''Typical "Parse args and run main() if main" function.'''
  if len(sys.argv) > 1:
    progargs = parse_args(sys.argv[1:])
    if progargs.needhelp:
      print_help()
    else:
      main(progargs)
  else:
    main()
