import sys
import time

from PyQt4.QtGui import *
from PyQt4 import QtCore
from PyQt4.QtCore import SLOT, SIGNAL
import PyQt4.uic

import deskcorder as dc

class Canvas(QGraphicsScene):
  def __init__(self, parent = None):
    # Setting the "size" of the scene to 0,0 x 1,1 disables scrolling.
    QGraphicsScene.__init__(self, .0, .0, 1., 1., parent)

    self.dirty = False
    self.frozen = False
    self.drawing = False

    self.trace = dc.Trace()
    self.trace.append(time.time())
    self.color = (.0, .0, .0) # each val in [0,1]
    self.pen_width = 5

    self.pen = QPen()
    self.pen.setColor(QColor(0, 0, 0))
    self.pen.setWidth(5)

    self.size_fun = None
    self.last_size = None

  def set_size_fun(self, fun):
    self.size_fun = fun
    self.size = (fun().width(), fun().height())

  def set_pen_color(self, r, g, b):
    self.pen.setColor(QColor(r * 255, g * 255, b * 255))
    self.color = (float(r), float(g), float(b))

  def set_pen_width(self, w):
    self.pen_width = w
    self.pen.setWidth(w)

  def resize(self, event):
    print event

  def get_size(self):
    return self.size_fun()

  def ensure_scale(self):
    size = (self.size_fun().width(), self.size_fun().height())
    if size != self.last_size:
      for item in self.items():
        self.removeItem(item)
      for stroke in self.trace.get_strokes():
        pen = QPen()
        pen.setColor(QColor(stroke.r(), stroke.g(), stroke.b()))
        for i in xrange(len(stroke.points[1:])):
          # XXX still need to set pen
          p0 = (stroke[i-1].x() * size[0] - size[0] / 2, stroke[i-1].y() * size[1] - size[1] / 2)
          p1 = (stroke[i].x() * size[0] - size[0] / 2,  stroke[i].y() * size[1] - size[1] / 2)
          self.addLine(p0[0], p0[1], p1[0], p1[1], pen)
    self.last_size = size

  # ---------------- Drawing -----------------------------

  def mousePressEvent(self, event):
    self.drawing = True
    self.dirty = True
    self.trace.last().append(self.color)

  def mouseReleaseEvent(self, event):
    self.drawing = False

  def mouseMoveEvent(self, event):
    self.ensure_scale()
    if self.drawing:
      curr = event.scenePos()
      curr_norm = (curr.x() / self.last_size[0] + .5, curr.y() / self.last_size[1] + .5)
      if 0 <= curr_norm[0] and curr_norm[0] <= 1 and 0 <= curr_norm[1] and curr_norm[1] <= 1:
        self.trace.last().last().append(curr_norm, time.time(), 1.)
        prev = event.lastScenePos()
        prev_norm = (prev.x() / self.last_size[0] + .5, prev.y() / self.last_size[1] + .5)
        if 0 <= prev_norm[0] and prev_norm[0] <= 1 and 0 <= prev_norm[1] and prev_norm[1] <= 1:
          self.addLine(prev.x(), prev.y(), curr.x(), curr.y(), self.pen)

  def get_time_of_first_event(self):
    return self.trace.get_time_of_first_event()

  def get_pressure(self):
    return 1.

  def freeze(self):
    self.frozen = True

  def unfreeze(self):
    self.frozen = False

  def clear(self):
    self.trace = dc.Trace()

  def refresh(self):
    pass
  def reset(self):
    pass
  def draw(self, color, r, pos1, pos2=None, pos3=None):
    pass



class GUI:
  DC_FORMATS = '''\
Deskcorder Binary (*.dcb);;\
Deskcorder XML (*.dcx);;\
Deskcorder Text (*.dct);;\
All Deskcorder Files (*.dcb *.dcx *.dct);;\
All Files (*.*)'''
  def __init__(self):
    self.app = QApplication(sys.argv);
    self.app.quitOnLastWindowClosed = False
    self.root = PyQt4.uic.loadUi('layout.ui')
    self.canvas = Canvas()
    self.root.gv.setScene(self.canvas)

    self.app.connect(self.root.color_box, SIGNAL('currentIndexChanged(QString)'), self.color_change)
    self.app.connect(self.root.brush_box, SIGNAL('currentIndexChanged(int)'), self.brush_change)

    self.last_save = None

    self.app.connect(self.root.action_open, SIGNAL('triggered()'), self.open)
    self.app.connect(self.root.action_save, SIGNAL('triggered()'), self.save)
    self.app.connect(self.root.action_save_as, SIGNAL('triggered()'), self.save_as)

#    self.app.connect(self.root.action_new, SIGNAL('triggered()'), self.reset)
#    self.app.connect(self.root.action_add, SIGNAL('triggered()'), lambda: self.canvas.trace.append(time.time()))
#
#    self.app.connect(self.root.action_record, SIGNAL('triggered(bool)'), self.record)
#    self.app.connect(self.root.action_play, SIGNAL('triggered(bool)'), self.play)
#    self.app.connect(self.root.action_pause, SIGNAL('triggered()'), self.pause)
#    self.app.connect(self.root.action_stop, SIGNAL('triggered()'), self.stop)

    self.app.connect(self.root.record_button, SIGNAL('clicked()'), self.root.action_record, SLOT('trigger()'))
    self.app.connect(self.root.play_button, SIGNAL('clicked()'), self.root.action_play, SLOT('trigger()'))
    self.app.connect(self.root.pause_button, SIGNAL('clicked()'), self.root.action_pause, SLOT('trigger()'))
    self.app.connect(self.root.stop_button, SIGNAL('clicked()'), self.root.action_stop, SLOT('trigger()'))

    self.app.connect(self.root.action_quit, SIGNAL('triggered()'), self.quit)
    #self.app.connect(self.app, SIGNAL('lastWindowClosed()'), self.quit)
    #self.app.connect(self.app, SIGNAL('lastWindowClosed()'), self.root, SLOT('show()'))

    self.timers = []

  def color_change(self, color_str):
    if str(color_str).lower() == 'black':
      self.canvas.set_pen_color(0,0,0)
    elif str(color_str).lower() == 'blue':
      self.canvas.set_pen_color(0,0,1)
    elif str(color_str).lower() == 'red':
      self.canvas.set_pen_color(1,0,0)
    elif str(color_str).lower() == 'orange':
      self.canvas.set_pen_color(1,.5,0)
    elif str(color_str).lower() == 'yellow':
      self.canvas.set_pen_color(1,1,0)
    elif str(color_str).lower() == 'green':
      self.canvas.set_pen_color(0,1,0)
    elif str(color_str).lower() == 'white':
      self.canvas.set_pen_color(1,1,1)
    else:
      print 'unrecognized color: %s' % color_str

  def brush_change(self, brush_idx):
    print 'brush'
    if brush_idx == 0:
      self.canvas.set_pen_width(1)
    elif brush_idx == 1:
      self.canvas.set_pen_width(3)
    elif brush_idx == 2:
      self.canvas.set_pen_width(5)
    else:
      print 'unrecognized brush_idx: %d' % brush_idx

  def quit(self):
    if not self.canvas.dirty or self.dirty_ok_save():
      self.app.quit()

  def open(self):
    if not self.canvas.dirty or self.dirty_ok_save():
      fname = str(QFileDialog.getOpenFileName(None, 'Open a Deskcorder Save File', 'saves', self.DC_FORMATS))
      if fname is not None and len(fname) > 0:
        self.last_save = fname
        if self.open_fun is not None:
          self.open_fun(fname)
        else:
          msg_box_err('Internal Error', 'Someone forgot to register an open handler!')

  def save(self):
    if self.last_save is None:
      self.save_as()
    elif self.save_fun is not None:
      self.save_fun(self.last_save)
    else:
      msg_box_err(QMessageBox.Critical, 'Internal Error', 'Someone forgot to register a save handler!')

  def save_as(self):
    fname = str(QFileDialog.getSaveFileName(None, 'Save your Deskcorder Progress', 'saves', self.DC_FORMATS))
    if fname is not None and len(fname) > 0:
      self.last_save = fname
      if self.save_fun is not None:
        self.save_fun(fname)
      else:
        msg_box_err(QMessageBox.Critical, 'Internal Error', 'Someone forgot to register a save handler!')

  @staticmethod
  def msg_box_err(title, msg):
    mb = QMessageBox(QMessageBox.Critical, title, msg)
    mb.setStandardButtons(QMessageBox.Ok)
    return mb.exec_() == QMessageBox.Ok

  def dirty_ok_save(self):
    mb = QMessageBox(QMessageBox.Warning,
        'The document has been modified.', "Are you sure you want to continue?")
    mb.setStandardButtons(QMessageBox.Save | QMessageBox.Cancel | QMessageBox.Discard)
    mb.setDefaultButton(QMessageBox.Cancel)
    rtn = mb.exec_()
    if rtn == QMessageBox.Save:
      self.save()
      return not self.canvas.dirty
    elif rtn == QMessageBox.Discard:
      return True
    return False

  def connect_new(self, fun):
    self.root.connect(self.root.action_new, SIGNAL('triggered()'), fun)

  def connect_add(self, fun):
    self.root.connect(self.root.action_new, SIGNAL('triggered()'), fun)

  def connect_record(self, fun):
    self.root.connect(self.root.action_record, SIGNAL('triggered(bool)'), fun)

  def connect_play(self, fun):
    self.root.connect(self.root.action_play, SIGNAL('triggered(bool)'), fun)

  def connect_pause(self, fun):
    self.root.connect(self.root.action_pause, SIGNAL('triggered(bool)'), fun)

  def connect_stop(self, fun):
    self.root.connect(self.root.action_stop, SIGNAL('triggered()'), fun)

  def connect_save(self, fun):
    self.save_fun = fun

  def connect_open(self, fun):
    self.open_fun = fun

  def connect_progress_fmt(self, fun):
    pass

  def connect_progress_moved(self, fun):
    pass

  def record_pressed(self, state = None):
    pass

  def connect_exp_png(self, fun):
    pass

  def connect_exp_pdf(self, fun):
    pass

  def play_pressed(self, state = None):
    pass

  def pause_pressed(self, state = None):
    pass

  def set_fname(self, fname):
    self.last_save = fname

  def timeout_add(self, delay, fun):
    self.timers.append(QTimer())
    self.timers[-1].connect(self.timers[-1], SIGNAL(''), lambda: self.remove_timer(self.timer[-1]) if not fun() else None)
    self.timers[-1].start(delay)

  def remove_timer(self, timer):
    timer.stop()
    for i in xrange(len(self.timers)):
      if self.timers[i] is timer:
        del self.timers[i]

  def init(self):
    self.root.show()
    self.canvas.set_size_fun(self.root.gv.size)

  def run(self):
    self.rtn_code = self.app.exec_()

  def deinit(self):
    pass
