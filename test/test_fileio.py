'''
Created on Sep 23, 2011

@author: jamoozy
'''
import unittest
import sys
sys.path.append("../src")
import fileio
import tempfile
import datatypes

class TestDCT(unittest.TestCase):
  def setUp(self):
    self.dct = fileio.DCT(tempfile.NamedTemporaryFile(prefix='TestDCT-').name)

  def test_init(self):
    self.assertNotEqual(None, self.dct.fname)
    self.assertEqual(fileio.DEFAULT_VERSION, self.dct.v)
    self.assertEqual(None, self.dct.fp)
    self.assertEqual(None, self.dct.log)
    self.assertEqual(None, self.dct.lec)

  def test_simple_lecture(self):
    lec = datatypes.Lecture()
    lec.append(datatypes.Start(12345, (500,400)))
    lec.append(datatypes.Color(12345, (1, 0, 0)))
    lec.append(datatypes.Click(12678, (40, 80)))
    lec.append(datatypes.Point(16789, (40, 90), 1))
    lec.append(datatypes.Point(23456, (50, 90), 1))
    lec.append(datatypes.Point(24567, (60, 90), 1))
    lec.append(datatypes.Point(25678, (80, 90), 1))
    lec.append(datatypes.Release(34567, (90,100)))
    lec.append(datatypes.End(40000, (500,400)))

    self.dct.save(lec)
    l2 = self.dct.load()
    self.assertFalse(l2.is_empty())

class TestDCB(unittest.TestCase):
  def setUp(self):
    self.dcb = fileio.DCB(tempfile.NamedTemporaryFile(prefix='TestDCB-').name)

  def test_init(self):
    self.assertNotEqual(None, self.dcb.fname)
    self.assertEqual(fileio.DEFAULT_VERSION, self.dcb.v)
    self.assertEqual(None, self.dcb.fp)
    self.assertEqual(None, self.dcb.log)
    self.assertEqual(None, self.dcb.lec)

  def test_simple_lecture(self):
    lec = datatypes.Lecture()
    lec.append(datatypes.Start(12345, (500,400)))
    lec.append(datatypes.Color(12345, (1, 0, 0)))
    lec.append(datatypes.Click(12678, (40, 80)))
    lec.append(datatypes.Point(16789, (40, 90), 1))
    lec.append(datatypes.Point(23456, (50, 90), 1))
    lec.append(datatypes.Point(24567, (60, 90), 1))
    lec.append(datatypes.Point(25678, (80, 90), 1))
    lec.append(datatypes.Release(34567, (90,100)))
    lec.append(datatypes.End(40000, (500,400)))

    self.dcb.save(lec)
    l2 = self.dcb.load()

    self.assertFalse(l2.is_empty())

class TestDCD(unittest.TestCase):
  def setUp(self):
    self.dcd = fileio.DCD(tempfile.NamedTemporaryFile(prefix='TestDCD-').name)
    
  def test_init(self):
    self.assertNotEqual(None, self.dcd.fname)
    self.assertEqual(fileio.DEFAULT_VERSION, self.dcd.v)
    self.assertEqual(None, self.dcd.fp)
    self.assertEqual(None, self.dcd.log)
    self.assertEqual(None, self.dcd.lec)

  def test_simple_lecture(self):
    lec = datatypes.Lecture()
    lec.append(datatypes.Start(12345, (500,400)))
    lec.append(datatypes.Color(12345, (1, 0, 0)))
    lec.append(datatypes.Click(12678, (40, 80)))
    lec.append(datatypes.Point(16789, (40, 90), 1))
    lec.append(datatypes.Point(23456, (50, 90), 1))
    lec.append(datatypes.Point(24567, (60, 90), 1))
    lec.append(datatypes.Point(25678, (80, 90), 1))
    lec.append(datatypes.Release(34567, (90,100)))
    lec.append(datatypes.End(40000, (500,400)))

    self.dcd.save(lec)
    l2 = self.dcd.load()

    self.assertFalse(l2.is_empty())


if __name__ == "__main__":
  #import sys;sys.argv = ['', 'Test.testName']
  unittest.main()
