'''
This is a module that serves 2 functions:
  1) it supplies basic, empty classes in lieu of working ones.
  2) it shows the functions that are required for these classes for them to
     work with the rest of the deskcroder system.
'''

class Audio:
  def __init__(self):
    pass
  def make_data(self):
    return []
  def load_data(self, data):
    pass
  def reset(self):
    pass
  def is_recording(self):
    return False
  def record(self, t = None):
    pass
  def record_tick(self):
    return False
  def play(self):
    pass
  def play_init(self):
    pass
  def play_tick(self, ttpt = None):
    return False
  def is_playing(self):
    return return False
  def get_s_played(self):
    return -1
  def get_time_of_first_event(self):
    return -1
  def get_current_audio_start_time(self):
    return -1
  def pause(self):
    pass
  def unpause(self):
    pass
  def stop(self):
    pass
  def reset(self):
    pass

class Canvas:
  def __init__(self):
    pass
  def get_time_of_first_event(self):
    return -1
  def freeze(self):
    pass
  def unfreeze(self):
    pass
  def clear(self):
    pass
  def refresh(self):
    pass
  def reset(self):
    pass
  def draw(self, color, r, pos1, pos2=None, pos3=None):
    pass

class GUI:
  def __init__(self, gladefile):
    pass
  def quit(self, event):
    pass
  def open(self):
    pass
  def save(self):
    pass
  def save_as(self):
    pass
  def dirty_ok(self):
    return False
  def connect_new(self, fun):
    pass
  def connect_record(self, fun):
    pass
  def connect_play(self, fun):
    pass
  def connect_pause(self, fun):
    pass
  def connect_stop(self, fun):
    pass
  def connect_save(self, fun):
    pass
  def connect_open(self, fun):
    pass
  def record_pressed(self, state = None):
    pass
  def play_pressed(self, state = None):
    pass
  def pause_pressed(self, state = None):
    pass
  def timeout_add(self, delay, fun):
    pass
  def init(self):
    pass
  def run(self):
    pass
  def deinit(self):
    pass

