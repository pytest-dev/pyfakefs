#!/usr/bin/python2.4
#
# Copyright 2009 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the fake_tempfile module."""

import stat
import StringIO
import unittest

import fake_filesystem
import fake_tempfile


class FakeLogging(object):
  """Fake logging object for testGettempprefix."""

  def __init__(self, test_case):
    self._message = None
    self._test_case = test_case

  # pylint: disable-msg=C6409
  def error(self, message):
    if self._message is not None:
      self.FailOnMessage(message)
    self._message = message

  def FailOnMessage(self, message):
    self._test_case.fail('Unexpected message received: %s' % message)

  warn = FailOnMessage
  info = FailOnMessage
  debug = FailOnMessage
  fatal = FailOnMessage

  def message(self):
    return self._message


class FakeTempfileModuleTest(unittest.TestCase):
  """Test the 'tempfile' module mock."""

  def setUp(self):
    self.filesystem = fake_filesystem.FakeFilesystem()
    self.tempfile = fake_tempfile.FakeTempfileModule(self.filesystem)
    self.orig_logging = fake_tempfile.logging
    self.fake_logging = FakeLogging(self)
    fake_tempfile.logging = self.fake_logging

  def tearDown(self):
    fake_tempfile.logging = self.orig_logging

  def testTempFilename(self):
    # pylint: disable-msg=C6002
    # TODO: test that tempdir is init'ed
    filename_a = self.tempfile._TempFilename()
    # expect /tmp/tmp######
    self.assertTrue(filename_a.startswith('/tmp/tmp'))
    self.assertEquals(14, len(filename_a))

    # see that random part changes
    filename_b = self.tempfile._TempFilename()
    self.assertTrue(filename_b.startswith('/tmp/tmp'))
    self.assertEquals(14, len(filename_b))
    self.assertNotEquals(filename_a, filename_b)

  def testTempFilenameSuffix(self):
    """test tempfile._TempFilename(suffix=)."""
    filename = self.tempfile._TempFilename(suffix='.suffix')
    self.assertTrue(filename.startswith('/tmp/tmp'))
    self.assertTrue(filename.endswith('.suffix'))
    self.assertEquals(21, len(filename))

  def testTempFilenamePrefix(self):
    """test tempfile._TempFilename(prefix=)."""
    filename = self.tempfile._TempFilename(prefix='prefix.')
    self.assertTrue(filename.startswith('/tmp/prefix.'))
    self.assertEquals(18, len(filename))

  def testTempFilenameDir(self):
    """test tempfile._TempFilename(dir=)."""
    filename = self.tempfile._TempFilename(dir='/dir')
    self.assertTrue(filename.startswith('/dir/tmp'))
    self.assertEquals(14, len(filename))

  def testTemporaryFile(self):
    obj = self.tempfile.TemporaryFile()
    self.assertEquals('<fdopen>', obj.name)
    self.assertTrue(isinstance(obj, StringIO.StringIO))

  def testNamedTemporaryFile(self):
    obj = self.tempfile.NamedTemporaryFile()
    created_filenames = self.tempfile.FakeReturnedMktempValues()
    self.assertEquals(created_filenames[0], obj.name)
    self.assertTrue(self.filesystem.GetObject(obj.name))
    obj.close()
    self.assertRaises(IOError, self.filesystem.GetObject, obj.name)

  def testNamedTemporaryFileNoDelete(self):
    obj = self.tempfile.NamedTemporaryFile(delete=False)
    obj.write('foo')
    obj.close()

    file_obj = self.filesystem.GetObject(obj.name)
    self.assertEquals('foo', file_obj.contents)

  def testMkstemp(self):
    temporary = self.tempfile.mkstemp()
    self.assertEquals(2, len(temporary))
    self.assertTrue(temporary[1].startswith('/tmp/tmp'))
    created_filenames = self.tempfile.FakeReturnedMktempValues()
    self.assertEquals(9999, temporary[0])
    self.assertEquals(temporary[1], created_filenames[0])
    self.assertTrue(self.filesystem.Exists(temporary[1]))
    self.assertEquals(self.filesystem.GetObject(temporary[1]).st_mode,
                      stat.S_IFREG|0600)

  def testMkstempDir(self):
    """test tempfile.mkstemp(dir=)."""
    # expect fail: /dir does not exist
    self.assertRaises(OSError, self.tempfile.mkstemp, dir='/dir')
    # expect pass: /dir exists
    self.filesystem.CreateDirectory('/dir')
    temporary = self.tempfile.mkstemp(dir='/dir')
    self.assertEquals(2, len(temporary))
    self.assertEquals(9999, temporary[0])
    self.assertTrue(temporary[1].startswith('/dir/tmp'))
    created_filenames = self.tempfile.FakeReturnedMktempValues()
    self.assertEquals(temporary[1], created_filenames[0])
    self.assertTrue(self.filesystem.Exists(temporary[1]))
    self.assertEquals(self.filesystem.GetObject(temporary[1]).st_mode,
                      stat.S_IFREG|0600)
    # pylint: disable-msg=C6002
    # TODO: add a test that /dir is actually writable.

  def testMkdtemp(self):
    dirname = self.tempfile.mkdtemp()
    self.assertTrue(dirname)
    created_filenames = self.tempfile.FakeReturnedMktempValues()
    self.assertEquals(dirname, created_filenames[0])
    self.assertTrue(self.filesystem.Exists(dirname))
    self.assertEquals(self.filesystem.GetObject(dirname).st_mode,
                      stat.S_IFDIR|0700)

  def testGettempdir(self):
    self.assertEquals(None, self.tempfile.tempdir)
    self.assertEquals('/tmp', self.tempfile.gettempdir())
    self.assertEquals('/tmp', self.tempfile.tempdir)

  def testGettempprefix(self):
    """test tempfile.gettempprefix() and the tempfile.template setter."""
    self.assertEquals('tmp', self.tempfile.gettempprefix())
    # set and verify
    self.tempfile.template = 'strung'
    self.assertEquals('strung', self.tempfile.gettempprefix())
    self.assertEquals('tempfile.template= is a NOP in python2.4',
                      self.fake_logging.message())

  def testMktemp(self):
    self.assertRaises(NotImplementedError, self.tempfile.mktemp)

  def testTemplateGet(self):
    """verify tempfile.template still unimplemented."""
    self.assertRaises(NotImplementedError, getattr,
                      self.tempfile, 'template')


if __name__ == '__main__':
  unittest.main()
