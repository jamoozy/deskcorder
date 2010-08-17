#!/usr/bin/python

import pygtk
pygtk.require('2.0')
import gtk
import gtk.glade
import sys

class Calculator:
  def __init__(self, gladefile):
    self.stack = []
    self.WidgetTree = gtk.glade.XML(gladefile)
    self.MainWindow = self.WidgetTree.get_widget("mainwindow")
    self.Result = self.WidgetTree.get_widget("result")
    self.digitButtons = map(lambda x: self.WidgetTree.get_widget("button"+str(x+1)), range(10))
    for i in xrange(10):
      self.digitButtons[i].connect("button-release-event",
        lambda x,y: self.Result.set_label(str(int(self.Result.get_label() + x.get_label())))
      )
    self.WidgetTree.get_widget("button16").connect("button-release-event",
      lambda x,y: [self.stack.append(int(self.Result.get_label())), \
        self.Result.set_label("0")]
    )
    self.WidgetTree.get_widget("button11").connect("button-release-event",
      lambda x,y: self.Result.set_label(str(self.stack.pop() + int(self.Result.get_label())))
    )
    self.WidgetTree.get_widget("button12").connect("button-release-event",
      lambda x,y: self.Result.set_label(str(self.stack.pop() - int(self.Result.get_label())))
    )
    self.WidgetTree.get_widget("button13").connect("button-release-event",
      lambda x,y: self.Result.set_label(str(self.stack.pop() * int(self.Result.get_label())))
    )
    self.WidgetTree.get_widget("button14").connect("button-release-event",
      lambda x,y: self.Result.set_label(str(self.stack.pop() / int(self.Result.get_label())))
    )
    self.WidgetTree.get_widget("button15").connect("button-release-event",
      lambda x,y: sys.exit(0)
    )
  def Run(self):
    self.MainWindow.show()
    gtk.main()
    self.MainWindow.hide()

a = Calculator("calculator.glade")
if __name__ == '__main__':
  a.Run()
