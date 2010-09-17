'''
This is a module that serves 2 functions:
  1) it supplies basic, empty classes in lieu of working ones.
  2) it shows the functions that are required for these classes for them to
     work with the rest of the deskcroder system.
'''

class Audio:
  def __init__(self):
    print 'Audio::__init__() not implemented'
  def make_data(self):
    print 'Audio::make_data() not implmented'
    return []
  def load_data(self, data):
    print 'Audio::make_data(data) not implmented'
  def reset(self):
    print 'Audio::reset() not implmented'
  def is_recording(self):
    print 'Audio::is_recording() not implmented'
    return False
  def record(self, t = None):
    print 'Audio::record(time=None) not implmented'
  def record_tick(self):
    print 'Audio::record(time=None) not implmented'
    return False
  def play(self):
    print 'Audio::play() not implmented'
  def play_init(self):
    print 'Audio::play_init() not implmented'
  def play_tick(self, ttpt = None):
    print 'Audio::play_tick(time_to_play_til=None) not implmented'
    return False
  def is_playing(self):
    print 'Audio::is_playing() not implmented'
    return False
  def get_s_played(self):
    print 'Audio::get_s_played() not implmented'
    return -1
  def get_time_of_first_event(self):
    print 'Audio::get_time_of_first_event() not implmented'
    return -1
  def get_current_audio_start_time(self):
    print 'Audio::get_current_audio_start_time() not implmented'
    return -1
  def pause(self):
    print 'Audio::pause() not implmented'
  def unpause(self):
    print 'Audio::unpause() not implmented'
  def stop(self):
    print 'Audio::stop() not implmented'
  def reset(self):
    print 'Audio::reset() not implmented'

class GUI:
  def __init__(self):
    print 'GUI::__init__() not implemented'
  def __getitem__(self, key):
    print 'GUI["%s"] not found!' % key
    return None
  def quit(self, event):
    print 'GUI::quit(event) not implemented'
  def open(self):
    print 'GUI::open() not implemented'
  def save(self):
    print 'GUI::save() not implemented'
  def save_as(self):
    print 'GUI::save_as() not implemented'
  def dirty_ok(self):
    print 'GUI::dirty_ok() not implemented'
    return False
  def connect_new(self, fun):
    print 'GUI::connect_new(function) not implemented'
  def connect_record(self, fun):
    print 'GUI::connect_record(function) not implemented'
  def connect_play(self, fun):
    print 'GUI::connect_play(function) not implemented'
  def connect_pause(self, fun):
    print 'GUI::connect_pause(function) not implemented'
  def connect_stop(self, fun):
    print 'GUI::connect_stop(function) not implemented'
  def connect_save(self, fun):
    print 'GUI::connect_save(function) not implemented'
  def connect_open(self, fun):
    print 'GUI::connect_open(function) not implemented'
  def record_pressed(self, state = None):
    print 'GUI::record_pressed(state) not implemented'
  def play_pressed(self, state = None):
    print 'GUI::play_pressed(state) not implemented'
  def pause_pressed(self, state = None):
    print 'GUI::pause_pressed(state) not implemented'
  def timeout_add(self, delay, fun):
    print 'GUI::timeout_add(delay, function) not implemented'
  def init(self):
    print 'GUI::init() not implemented'
  def run(self):
    print 'GUI::run() not implemented'
  def deinit(self):
    print 'GUI::deinit() not implemented'
