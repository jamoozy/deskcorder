#!/usr/bin/python

import sys
sys.path.append('..')
import fileio
from datatypes import *

if len(sys.argv) <= 0: sys.exit()

lec = fileio.load('../saves/ll2.dcb')
ofile = open('tmp.csv', 'w')

it = iter(lec)
try:
  last_point = None
  while True:
    e = it.next()
    if isinstance(e, Point):
      if last_point is None or last_point.x() != e.x() and last_point.y() != e.y():
        ofile.write("%d,%d,%d," % (e.x() * 800, e.y() * 600, e.t * 1000))
      last_point = e
    elif last_point is not None:
      last_point = None
      ofile.write("\n")

except StopIteration:
  pass

print 'Done!'
ofile.close()
