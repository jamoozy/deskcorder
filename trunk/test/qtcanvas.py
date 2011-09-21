import sys

from PyQt4 import QtCore
from PyQt4.QtCore import SIGNAL, SLOT
from PyQt4.QtGui import *
import PyQt4.uic


class Canvas(QGraphicsScene):
  def __init__(self, parent = None):
    QGraphicsScene.__init__(self, .0, .0, 1., 1., parent)
    self.trace = []
    self.size = (1., 1.)
    self.pen = QPen()
    self.pen.setColor(QColor(0,0,0))
    self.pen.setWidth(5)
    self.size_fun = None
    self.last_size = None

  def set_size_fun(self, fun):
    self.size_fun = fun
    self.size = (fun().width(), fun().height())

  def get_size(self):
    return self.size_fun()

#  def width(self):
#    return self.last_size[0]
#
#  def height(self):
#    return self.last_size[1]

  def resize(self, event):
    print event

  def ensure_scale(self):
    size = (self.size_fun().width(), self.size_fun().height())
    if size != self.last_size:
      for item in self.items():
        self.removeItem(item)
      for stroke in self.trace:
        for i in xrange(len(stroke[1:])):
          # Set pen
          self.addLine((stroke[i-1][0]) * size[0], (stroke[i-1][1]) * size[1], (stroke[i][0]) * size[0], (stroke[i][1]) * size[1])
    self.last_size = size

  def mousePressEvent(self, event):
    self.drawing = True
    self.trace.append([])

  def mouseReleaseEvent(self, event):
    self.drawing = False

  def mouseMoveEvent(self, event):
    self.ensure_scale()
    if self.drawing:
      curr = event.scenePos()
      curr_norm = (curr.x() / self.last_size[0] + .5, curr.y() / self.last_size[1] + .5)
      if 0 <= curr_norm[0] and curr_norm[0] <= 1 and 0 <= curr_norm[1] and curr_norm[1] <= 1:
        self.trace[-1].append((curr.x() / self.last_size[0], curr.y() / self.last_size[1]))
        prev = event.lastScenePos()
        prev_norm = (prev.x() / self.last_size[0] + .5, prev.y() / self.last_size[1] + .5)
        if 0 <= prev_norm[0] and prev_norm[0] <= 1 and 0 <= prev_norm[1] and prev_norm[1] <= 1:
          self.addLine(prev.x(), prev.y(), curr.x(), curr.y(), self.pen)
          print 'line (%3.3f,%3.3f) -- (%3.3f,%3.3f)' % (prev.x(), prev.y(), curr.x(), curr.y())
          print '     (%3.3f,%3.3f) -- (%3.3f,%3.3f)' % (prev_norm[0], prev_norm[1], curr_norm[0], curr_norm[1])
        else:
          print 'prev out'
      else:
        print 'curr out'
    else:
      print 'window size: %dx%d' % self.last_size

if __name__ == '__main__':
  app = QApplication(sys.argv)
  canvas = Canvas()
  gv = QGraphicsView(canvas)
  gv.connect(gv, SIGNAL("resize()"), canvas.resize)
  gv.show()
  canvas.set_size_fun(gv.size)
  app.exec_()
