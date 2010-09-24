#!/usr/bin/python

import math
import sys
import time
import thread
import os
import signal
from datatypes import *

import recorder
import exporter



############################################################################
# ---------------------------- Main Object ------------------------------- #
############################################################################

class Deskcorder:
  def __init__(self, gui_enabled=True, audio_enabled=True):
    # Playback variables.
    self.play_time = None
    self.break_times = []
    self.last_pause = None

    self.lecture = Lecture(time.time())

    self.audio = Audio()
    self.gui = GUI(self.lecture)

    self.gui.connect_new(self.reset)
    self.gui.connect_play(self.play)
    self.gui.connect_pause(self.pause)
    self.gui.connect_stop(self.stop)
    self.gui.connect_save(self.save)
    self.gui.connect_open(self.load)
    self.gui.connect_record(self.record)
    self.gui.connect_progress_fmt(self.fmt_progress)
    self.gui.connect_progress_moved(self.move_progress)
    self.gui.connect_exp_png(self.exp_png)
    self.gui.connect_exp_pdf(self.exp_pdf)

    if not audio_enabled: print 'Audio disabled'
    if not gui_enabled: print 'GUI disabled'

    self.progress = -1

  def is_empty(self):
    return self.lecture.is_empty() and self.audio.is_empty()

  def all_buttons_off(self):
    self.gui.record_pressed(False)
    self.gui.play_pressed(False)
    self.gui.pause_pressed(False)

  def set_progress(self, val):
    self.progress = val
    self.audio.set_progress(val + self.earliest_event_time())
    self.gui.canvas.ttpt = val + self.earliest_event_time()
    self.reset_iters_to_progress()

  def reset_iters_to_progress(self):
    self.slide_i = 0
    self.stroke_i = 0
    self.point_i = 0

    if self.lecture.is_empty(): return

    ttpt = self.progress + self.earliest_event_time()
    for i in xrange(1,len(self.gui.canvas.lecture)):
      if self.gui.canvas.lecture[i].t > ttpt:
        self.slide_i = i - 1
        while not self.play_iters_valid():
          continue
        return

    self.slide_i = len(self.gui.canvas.lecture) - 1
    self.play_iters_valid() # makes sure they are, if they can be.

  def get_duration(self):
    start_t = self.earliest_event_time()
    end_t = self.latest_event_time()
    return (end_t - start_t) if start_t >= 0 and end_t >= 0 else .0

  def earliest_event_time(self):
    video_t = self.gui.canvas.lecture.get_time_of_first_event()
    audio_t = self.audio.get_time_of_first_event()
    if audio_t >= 0 and video_t >= 0:
      return min(audio_t, video_t)
    elif video_t >= 0:
      return video_t
    else:
      return audio_t

  def latest_event_time(self):
    video_t = self.gui.canvas.lecture.get_time_of_last_event()
    audio_t = self.audio.get_time_of_last_event()
    return max(audio_t, video_t) if video_t >= 0 else audio_t

  def reset(self):
    '''Clears the state of the canvas and audio, as if the system had just
    started.'''
    if not self.gui.canvas.dirty or self.gui.dirty_new_ok():
      self.all_buttons_off()
      self.gui.progress_slider_value(.0)
      self.gui.canvas.reset()
      self.audio.reset()
      self.stop()

  def run(self, fname = None):
    '''Runs the program.'''
    self.gui.init()
    if fname is not None:
      try:
        self.load(fname)
      except IOError as e:
        print 'Could not load file, %s: %s"' % (fname, e.message)

    try:
      self.gui.run()
    except KeyboardInterrupt:
      pass
    self.gui.deinit()

  def is_recording(self):
    return self.audio.is_recording()

  def record(self, rec):
    '''Starts the mic recording.'''
    if rec:
      self.gui.disable_progress_bar()
      try:
        self.audio.record()
      except recorder.InvalidOperationError:
        self.gui.record_pressed(False)
    else:
      self.gui.enable_progress_bar()
      self.audio.stop()

  def is_playing(self):
    '''Determines if this is playing or not.'''
    return self.progress >= 0 and self.progress <= self.get_duration()

  def play(self, active):
    '''Start/stop playing what's in this file.'''
    if self.is_empty():
      self.all_buttons_off()
      return

    if not active:
      if self.is_paused():
        self.gui.play_pressed(True)
        self.gui.pause_pressed(False)
      else:
        self.stop()
      return
    elif self.is_playing():
      return

    if self.is_recording():
      self.stop()
      self.gui.play_pressed(True)

    self.audio.play_init()

    now = time.time()

    self.gui.canvas.freeze()
    self.lecture = self.gui.canvas.lecture

    # Playback iterators.
    self.slide_i = 0
    self.stroke_i = 0
    self.point_i = 0
    self.video_done = False

    # prev & curr time play_tick() was called and progress in seconds.
    self.play_time = now
    self.prev_now = now
    self.curr_now = self.prev_now
    self.progress = 0

    self.gui.canvas.clear() # XXX hack to clear initially for GTK+ version
    self.gui.timeout_add(50, self.play_tick)

  def play_tick(self):
    '''Do one 'tick' in the process of playing back what's stored in this
    program.'''

    if not self.is_playing():
      #print 'Not playing'
      return False
    if self.is_paused():
      #print 'Paused'
      return True
    if self.get_duration() <= 0:
      #print 'Empty'
      return False

    # "normal" update
    self.prev_now = self.curr_now
    self.curr_now = time.time()
    self.progress += self.curr_now - self.prev_now

    # adjustment for audio lag
    if self.audio.is_playing():
      a_start = self.audio.get_current_audio_start_time()
      a_time = self.audio.get_s_played()
      if a_start > 0:
        self.audio.play_tick(self.progress + self.earliest_event_time())
        if a_time <= 0 and not self.gui.audio_wait_pressed():
          a_time = .01
        if a_time > 0:
          self.progress = a_start + a_time - self.earliest_event_time()
    else:
      a_time = -1

    # updating GUI
    self.gui.progress_slider_value(self.progress / self.get_duration())
    ttpt = self.progress + self.earliest_event_time()
    self.gui.canvas.ttpt = ttpt
    #print 'prog:%.1fs' % self.progress

    # I'm simulating a do-while loop here.  This one is basically:
    #  1. While we still have stuff to iterate over, iterate.
    #  2. While the thing our iterator is pointing at is still old enough to
    #     draw, draw it.
    #  3. When we can't draw any more because the point our iterator is
    #     pointed at is too old, return True (run the function again later).
    #  4. When out iterator goes past the end of the lecture object, return
    #     false (stop calling this function).
    while not self.video_done and self.play_iters_valid():
      slide = self.lecture[self.slide_i]
      # if we are after the slide's clear time but are still on the first point
      # of its first stroke, then clear the canvas.
      if slide.t <= ttpt and self.point_i == 0 and self.stroke_i == 0:
        self.gui.canvas.clear()

      stroke = slide[self.stroke_i]
      if len(stroke) > 0:
        point = stroke[self.point_i]
        if point.t <= ttpt:
          if self.point_i > 1:
            self.gui.canvas.draw(stroke.color, stroke.thickness * point.p,
                stroke[self.point_i-2].pos,
                stroke[self.point_i-1].pos,
                stroke[self.point_i].pos)
          elif self.point_i > 0:
            self.gui.canvas.draw(stroke.color, stroke.thickness * point.p,
                stroke[self.point_i-1].pos,
                stroke[self.point_i].pos)
          else:
            self.gui.canvas.draw(stroke.color, stroke.thickness * point.p,
                stroke[self.point_i].pos)
        else:
          return True

      if not self.play_iters_inc() and a_time < 0:
        self.stop()
        return False
    return self.check_done()

  def play_iters_valid(self):
    if self.slide_i < len(self.lecture):
      if self.stroke_i < len(self.lecture[self.slide_i]):
        if self.point_i < len(self.lecture[self.slide_i][self.stroke_i]):
          return True
    return self.play_iters_inc()

  def play_iters_inc(self):
    '''Increments all the iterators that have to do with the playing
    process.'''
    if len(self.lecture) > 0:
      if len(self.lecture[self.slide_i]) > 0:
        self.point_i += 1
        if self.point_i < len(self.lecture[self.slide_i][self.stroke_i]):
          return self.play_iters_valid()
        self.point_i = 0

        self.stroke_i += 1
        if self.stroke_i < len(self.lecture[self.slide_i]):
          return self.play_iters_valid()
        self.stroke_i = 0

      self.slide_i += 1
      if self.slide_i < len(self.lecture):
        return self.play_iters_valid()

    self.slide_i = 0
    self.stroke_i = 0
    self.point_i = 0
    self.video_done = True
    return False

  def pause(self, checked):
    '''Pauses playback and audio recording.'''
    if self.is_empty():
      self.all_buttons_off()
      return

    now = time.time()
    if self.is_playing():
      if self.last_pause == None:
        self.last_pause = now
        self.gui.pause_pressed(True)
        self.audio.pause()
      else:
        self.break_times.append((self.last_pause, now))
        self.last_pause = None
        self.gui.pause_pressed(False)
        self.audio.unpause()
    else:
      self.gui.pause_pressed(False)

  def is_paused(self):
    return self.last_pause is not None

  def done(self):
    '''The drawing portion is done playing back.  Wait for the speech portion
    to finish also.'''
    self.gui.timeout_add(100, self.check_done)

  def check_done(self):
    '''Returns True if this should keep playing, False otherwise.'''
    if not self.is_playing():
      self.stop()
      return False
    return True

  def stop(self):
    if self.is_paused():
      self.pause(time.time())
    self.audio.stop()
    self.gui.record_pressed(False)
    self.gui.play_pressed(False)
    self.gui.canvas.unfreeze()
    self.last_pause = None
    self.break_times = []
    self.play_time = None
    self.progress = -1

  def fmt_progress(self, val):
    dur = self.get_duration()
    total = '%d:%02d' % (dur / 60, math.ceil(dur % 60))
    if self.is_empty():
      if self.gui.progress_slider_value() != 0:
        self.gui.progress_slider_value(.0)
      return '0:00 / 0:00'
    elif self.is_playing():
      return '%d:%02d / %s' % (round(self.progress / 60), self.progress % 60, total)
    else:
      return '0:00 / %s' % total

  def move_progress(self, val):
    if self.is_empty():
      self.all_buttons_off()
      # Can't set progress here, because may be in reaction to a mouse click,
      # in which case an update will get immediately overwritten by the
      # mouse-up event, or whatever is responsible for it.
      return
    elif self.is_recording():
      pass # do nothing?
    else:
      self.gui.play_pressed(True)
      self.gui.pause_pressed(True)
      self.set_progress(val * self.get_duration())



  ############################################################################
  # ------------------------------ File I/O -------------------------------- #
  ############################################################################

  def exp_png(self, fname, size, times):
    if fname.lower().endswith('.png'):
      exporter.to_png(self.gui.canvas.lecture, fname[:-4], size, times)
    else:
      exporter.to_png(self.gui.canvas.lecture, fname, size, times)

  def exp_pdf(self, fname, size, times):
    if fname.lower().endswith('.pdf'):
      exporter.to_pdf(self.gui.canvas.lecture, fname[:-4], size, times)
    else:
      exporter.to_pdf(self.gui.canvas.lecture, fname, size, times)

  def save(self, fname = 'save.dcb'):
    if self.is_recording():
      self.record(False)
    recorder.save(fname, self.gui.canvas.lecture, self.audio.make_data())
    self.gui.canvas.dirty = False

  def load(self, fname = 'save.dcb'):
    try:
      rtn = recorder.load(fname)
      if len(rtn) > 0:
        self.gui.canvas.lecture, a = recorder.load(fname)
        self.audio.load_data(a)
        self.gui.canvas.dirty = False
        self.gui.set_fname(fname)
        return True
      return False
    except recorder.FormatError:
      return False



##############################################################################
# -------------------------- Testing/Running ------------------------------- #
##############################################################################

def parse_args(args):
  fname, audio, video = None, None, None
  for arg in args:
    if arg == '-h' or arg == '--help':
      print 'Usage %s [-A|--no-audio]'
    elif arg == '-G' or arg == '--no-gui':
      has_gui = False
    elif arg == '-A' or arg == '--no-audio':
      audio = 'dummy'
    elif arg.startswith('--use-gui='):
      video = arg[10:]
    elif arg.startswith('--use-audio='):
      audio = arg[12:]
      pass
    else:
      fname = arg
  return fname, audio, video

if __name__ == '__main__':
  # valid video modules in preferred order
  VALID_AV_MODULES = ['linux', 'mac', 'qt', 'dummy']

  fname, audio, video = parse_args(sys.argv[1:])

  if audio is not None:
    try:
      Audio = __import__(audio).Audio
    except AttributeError:
      audio = None
      print 'audio module "%s" not found' % audio

  if audio is None:
    for a in VALID_AV_MODULES:
      try:
        Audio = __import__(a).Audio
        audio = a
        break
      except AttributeError:
        pass

  if video is not None:
    try:
      Canvas = __import__(video).Canvas
      GUI = __import__(video).GUI
    except AttributeError:
      video = None
      print 'video module "%s" not found' % video

  if video is None:
    for v in VALID_AV_MODULES:
      try:
        GUI = __import__(v).GUI
        video = v
        break
      except AttributeError:
        pass

  print 'using %s audio and %s gui' % (audio, video)
  Deskcorder().run(fname)
