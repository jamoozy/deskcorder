
class Canvas():
  def __init__(self):
    pass

class GUI():
  def __init__(self, dc):
    self.dc = dc

  def connect_new(self, new):
    self.reset = new

  def connect_play(self, play):
    self.play = play

  def connect_pause(self, pause):
    self.pause = pause

  def connect_stop(self, stop):
    self.stop = stop

  def connect_save(self, save):
    self.save = save

  def connect_open(self, load):
    self.load = load

  def connect_record(self, record):
    self.record = record

  def connect_progress_fmt(self, fmt_progress):
    self.fmt_progress = fmt_progress

  def connect_progress_moved(self, move_progress):
    self.move_progress = move_progress

  def connect_exp_png(self, exp_png):
    self.exp_png = exp_png

  def connect_exp_pdf(self, exp_pdf):
    self.exp_pdf = exp_pdf

  def connect_exp_swf(self, exp_swf):
    self.exp_swf = exp_swf
  
  def init(self):
    pass
  
  def get_size(self):
    pass
  
  def run(self):
    pass
  
  def deinit(self):
    pass

class Audio():
  def __init__(self, dc):
    self.dc = dc
