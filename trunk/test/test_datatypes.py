'''
Created on Sep 23, 2011

@author: jamoozy
'''
import unittest
import sys
sys.path.append("../src")
from datatypes import *

class TestLecture(unittest.TestCase):
  def setUp(self):
    self.lec = Lecture()
    
  def test_init(self):
    self.assertEqual(1, self.lec.aspect_ratio())

class TestLectureState(unittest.TestCase):
  def setUp(self):
    self.state = Lecture.State()
    
  def test_init(self):
    self.assertEqual(1, self.state.aspect_ratio())

class TestLectureIterator(unittest.TestCase):
  def setUp(self):
    pass
    
  def test_init(self):
    iterator = iter(Lecture())
    self.assertRaises(StopIteration, next, iterator)


if __name__ == "__main__":
  #import sys;sys.argv = ['', 'Test.testName']
  unittest.main()