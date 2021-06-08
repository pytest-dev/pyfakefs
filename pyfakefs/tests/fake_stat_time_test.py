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

"""Unit tests for file timestamp updates."""
import time
import unittest
from collections import namedtuple

from pyfakefs.tests.test_utils import RealFsTestCase

FileTime = namedtuple('FileTime', 'st_ctime, st_atime, st_mtime')


class FakeStatTestBase(RealFsTestCase):

    def setUp(self):
        super().setUp()
        # we disable the tests for MacOS to avoid very long builds due
        # to the 1s time resolution - we know that the functionality is
        # similar to Linux
        self.check_linux_and_windows()
        self.file_path = self.make_path('some_file')
        # MacOS has a timestamp resolution of 1 second
        self.sleep_time = 1.1 if self.is_macos else 0.01
        self.mode = ''

    def stat_time(self, path):
        stat = self.os.stat(path)
        if self.use_real_fs():
            # sleep a bit so in the next call the time has changed
            time.sleep(self.sleep_time)
        else:
            # calling time.time() advances mocked time
            time.time()
        return FileTime(st_ctime=stat.st_ctime,
                        st_atime=stat.st_atime,
                        st_mtime=stat.st_mtime)

    def assertLessExceptWindows(self, time1, time2):
        if self.is_windows_fs:
            self.assertLessEqual(time1, time2)
        else:
            self.assertLess(time1, time2)

    def assertLessExceptPosix(self, time1, time2):
        if self.is_windows_fs:
            self.assertLess(time1, time2)
        else:
            self.assertEqual(time1, time2)

    def open_close_new_file(self):
        with self.mock_time():
            with self.open(self.file_path, self.mode):
                created = self.stat_time(self.file_path)
            closed = self.stat_time(self.file_path)
            return created, closed

    def open_write_close_new_file(self):
        with self.mock_time():
            with self.open(self.file_path, self.mode) as f:
                created = self.stat_time(self.file_path)
                f.write('foo')
                written = self.stat_time(self.file_path)
            closed = self.stat_time(self.file_path)

        return created, written, closed

    def open_close(self):
        with self.mock_time():
            self.create_file(self.file_path)

            before = self.stat_time(self.file_path)
            with self.open(self.file_path, self.mode):
                opened = self.stat_time(self.file_path)
            closed = self.stat_time(self.file_path)

            return before, opened, closed

    def open_write_close(self):
        with self.mock_time():
            self.create_file(self.file_path)

            before = self.stat_time(self.file_path)
            with self.open(self.file_path, self.mode) as f:
                opened = self.stat_time(self.file_path)
                f.write('foo')
                written = self.stat_time(self.file_path)
            closed = self.stat_time(self.file_path)

            return before, opened, written, closed

    def open_flush_close(self):
        with self.mock_time():
            self.create_file(self.file_path)

            before = self.stat_time(self.file_path)
            with self.open(self.file_path, self.mode) as f:
                opened = self.stat_time(self.file_path)
                f.flush()
                flushed = self.stat_time(self.file_path)
            closed = self.stat_time(self.file_path)

            return before, opened, flushed, closed

    def open_write_flush(self):
        with self.mock_time():
            self.create_file(self.file_path)

            before = self.stat_time(self.file_path)
            with self.open(self.file_path, self.mode) as f:
                opened = self.stat_time(self.file_path)
                f.write('foo')
                written = self.stat_time(self.file_path)
                f.flush()
                flushed = self.stat_time(self.file_path)
            closed = self.stat_time(self.file_path)

            return before, opened, written, flushed, closed

    def open_read_flush(self):
        with self.mock_time():
            self.create_file(self.file_path)

            before = self.stat_time(self.file_path)
            with self.open(self.file_path, 'r') as f:
                opened = self.stat_time(self.file_path)
                f.read()
                read = self.stat_time(self.file_path)
                f.flush()
                flushed = self.stat_time(self.file_path)
            closed = self.stat_time(self.file_path)

            return before, opened, read, flushed, closed

    def open_read_close_new_file(self):
        with self.mock_time():
            with self.open(self.file_path, self.mode) as f:
                created = self.stat_time(self.file_path)
                f.read()
                read = self.stat_time(self.file_path)
            closed = self.stat_time(self.file_path)

            return created, read, closed

    def open_read_close(self):
        with self.mock_time():
            self.create_file(self.file_path)

            before = self.stat_time(self.file_path)
            with self.open(self.file_path, self.mode) as f:
                opened = self.stat_time(self.file_path)
                f.read()
                read = self.stat_time(self.file_path)
            closed = self.stat_time(self.file_path)

            return before, opened, read, closed

    def check_open_close_new_file(self):
        """
        When a file is created on opening and closed again,
        no timestamps are updated on close.
        """
        created, closed = self.open_close_new_file()

        self.assertEqual(created.st_ctime, closed.st_ctime)
        self.assertEqual(created.st_atime, closed.st_atime)
        self.assertEqual(created.st_mtime, closed.st_mtime)

    def check_open_write_close_new_file(self):
        """
        When a file is created on opening, st_ctime is updated under Posix,
        and st_mtime is updated on close.
        """
        created, written, closed = self.open_write_close_new_file()

        self.assertEqual(created.st_ctime, written.st_ctime)
        self.assertLessExceptWindows(written.st_ctime, closed.st_ctime)

        self.assertEqual(created.st_atime, written.st_atime)
        self.assertLessEqual(written.st_atime, closed.st_atime)

        self.assertEqual(created.st_mtime, written.st_mtime)
        self.assertLess(written.st_mtime, closed.st_mtime)

    def check_open_close_w_mode(self):
        """
        When an existing file is opened with 'w' or 'w+' mode, st_ctime (Posix
        only) and st_mtime are updated on open (truncating), but not on close.
        """
        before, opened, closed = self.open_close()

        self.assertLessExceptWindows(before.st_ctime, opened.st_ctime)
        self.assertEqual(opened.st_ctime, closed.st_ctime)

        self.assertLessEqual(before.st_atime, opened.st_atime)
        self.assertEqual(opened.st_atime, closed.st_atime)

        self.assertLess(before.st_mtime, opened.st_mtime)
        self.assertEqual(opened.st_mtime, closed.st_mtime)

    def check_open_close_non_w_mode(self):
        """
        When an existing file is opened with any mode other than 'w' or 'w+',
        no timestamps are updated.
        """
        before, opened, closed = self.open_close()

        self.assertEqual(before.st_ctime, opened.st_ctime)
        self.assertEqual(opened.st_ctime, closed.st_ctime)

        self.assertEqual(before.st_atime, opened.st_atime)
        self.assertEqual(opened.st_atime, closed.st_atime)

        self.assertEqual(before.st_mtime, opened.st_mtime)
        self.assertEqual(opened.st_mtime, closed.st_mtime)

    def check_open_write_close_w_mode(self):
        """
        When an existing file is opened with 'w' or 'w+' mode and is then
        written to, st_ctime (Posix only) and st_mtime are updated on open
        (truncating) and again on close (flush), but not when written to.
        """
        before, opened, written, closed = self.open_write_close()

        self.assertLessExceptWindows(before.st_ctime, opened.st_ctime)
        self.assertEqual(opened.st_ctime, written.st_ctime)
        self.assertLessExceptWindows(written.st_ctime, closed.st_ctime)

        self.assertLessEqual(before.st_atime, opened.st_atime)
        self.assertEqual(opened.st_atime, written.st_atime)
        self.assertLessEqual(written.st_atime, closed.st_atime)

        self.assertLess(before.st_mtime, opened.st_mtime)
        self.assertEqual(opened.st_mtime, written.st_mtime)
        self.assertLess(written.st_mtime, closed.st_mtime)

    def check_open_flush_close_w_mode(self):
        """
        When an existing file is opened with 'w' or 'w+' mode (truncating),
        st_ctime (Posix only) and st_mtime are updated. No updates are done
        on flush or close.
        """
        before, opened, flushed, closed = self.open_flush_close()

        self.assertLessExceptWindows(before.st_ctime, opened.st_ctime)
        self.assertEqual(opened.st_ctime, flushed.st_ctime)
        self.assertEqual(flushed.st_ctime, closed.st_ctime)

        self.assertLessEqual(before.st_atime, opened.st_atime)
        self.assertEqual(opened.st_atime, flushed.st_atime)
        self.assertEqual(flushed.st_atime, closed.st_atime)

        self.assertLess(before.st_mtime, opened.st_mtime)
        self.assertEqual(opened.st_mtime, flushed.st_mtime)
        self.assertEqual(flushed.st_mtime, closed.st_mtime)

    def check_open_flush_close_non_w_mode(self):
        """
        When an existing file is opened with any mode other than 'w' or 'w+',
        flushed and closed, no timestamps are updated.
        """
        before, opened, flushed, closed = self.open_flush_close()

        self.assertEqual(before.st_ctime, opened.st_ctime)
        self.assertEqual(opened.st_ctime, flushed.st_ctime)
        self.assertEqual(flushed.st_ctime, closed.st_ctime)

        self.assertEqual(before.st_atime, opened.st_atime)
        self.assertEqual(opened.st_atime, flushed.st_atime)
        self.assertEqual(flushed.st_atime, closed.st_atime)

        self.assertEqual(before.st_mtime, opened.st_mtime)
        self.assertEqual(opened.st_mtime, flushed.st_mtime)
        self.assertEqual(flushed.st_mtime, closed.st_mtime)

    def check_open_read_close_non_w_mode(self):
        """
        Reading from a file opened with 'r', 'r+', or 'a+' mode updates
        st_atime under Posix.
        """
        before, opened, read, closed = self.open_read_close()

        self.assertEqual(before.st_ctime, opened.st_ctime)
        self.assertEqual(opened.st_ctime, read.st_ctime)
        self.assertEqual(read.st_ctime, closed.st_ctime)

        self.assertEqual(before.st_atime, opened.st_atime)
        self.assertLessEqual(opened.st_atime, read.st_atime)
        self.assertEqual(read.st_atime, closed.st_atime)

        self.assertEqual(before.st_mtime, opened.st_mtime)
        self.assertEqual(opened.st_mtime, read.st_mtime)
        self.assertEqual(read.st_mtime, closed.st_mtime)

    def check_open_read_close_new_file(self):
        """
        When a file is created with 'w+' or 'a+' mode and then read from,
        st_atime is updated under Posix.
        """
        created, read, closed = self.open_read_close_new_file()

        self.assertEqual(created.st_ctime, read.st_ctime)
        self.assertEqual(read.st_ctime, closed.st_ctime)

        self.assertLessEqual(created.st_atime, read.st_atime)
        self.assertEqual(read.st_atime, closed.st_atime)

        self.assertEqual(created.st_mtime, read.st_mtime)
        self.assertEqual(read.st_mtime, closed.st_mtime)

    def check_open_write_close_non_w_mode(self):
        """
        When an existing file is opened with 'a', 'a+' or 'r+' mode
        and is then written to, st_ctime (Posix only) and st_mtime are
        updated close (flush), but not on opening or when written to.
        """
        before, opened, written, closed = self.open_write_close()

        self.assertEqual(before.st_ctime, opened.st_ctime)
        self.assertEqual(opened.st_ctime, written.st_ctime)
        self.assertLessExceptWindows(written.st_ctime, closed.st_ctime)

        self.assertEqual(before.st_atime, opened.st_atime)
        self.assertEqual(opened.st_atime, written.st_atime)
        self.assertLessEqual(written.st_atime, closed.st_atime)

        self.assertEqual(before.st_mtime, opened.st_mtime)
        self.assertEqual(opened.st_mtime, written.st_mtime)
        self.assertLess(written.st_mtime, closed.st_mtime)

    def check_open_write_flush_close_w_mode(self):
        """
        When an existing file is opened with 'w' or 'w+' mode
        and is then written to, st_ctime (Posix only) and st_mtime are
        updated on open (truncating). Under Posix, st_mtime is updated on
        flush, under Windows, on close instead.
        """
        before, opened, written, flushed, closed = self.open_write_flush()

        self.assertLessEqual(before.st_ctime, opened.st_ctime)
        self.assertLessEqual(written.st_ctime, flushed.st_ctime)
        self.assertEqual(opened.st_ctime, written.st_ctime)
        self.assertEqual(flushed.st_ctime, closed.st_ctime)

        self.assertLessEqual(before.st_atime, opened.st_atime)
        self.assertEqual(opened.st_atime, written.st_atime)
        self.assertLessEqual(written.st_atime, flushed.st_atime)
        self.assertLessEqual(flushed.st_atime, closed.st_atime)

        self.assertLess(before.st_mtime, opened.st_mtime)
        self.assertEqual(opened.st_mtime, written.st_mtime)
        self.assertLessExceptWindows(written.st_mtime, flushed.st_mtime)
        self.assertLessEqual(flushed.st_mtime, closed.st_mtime)

    def check_open_write_flush_close_non_w_mode(self):
        """
        When an existing file is opened with 'a', 'a+' or 'r+' mode
        and is then written to, st_ctime and st_mtime are updated on flush
        under Posix. Under Windows, only st_mtime is updated on close instead.
        """
        before, opened, written, flushed, closed = self.open_write_flush()

        self.assertEqual(before.st_ctime, opened.st_ctime)
        self.assertEqual(opened.st_ctime, written.st_ctime)
        self.assertLessExceptWindows(written.st_ctime, flushed.st_ctime)
        self.assertEqual(flushed.st_ctime, closed.st_ctime)

        self.assertEqual(before.st_atime, opened.st_atime)
        self.assertEqual(opened.st_atime, written.st_atime)
        self.assertLessEqual(written.st_atime, flushed.st_atime)
        self.assertLessEqual(flushed.st_atime, closed.st_atime)

        self.assertEqual(before.st_mtime, opened.st_mtime)
        self.assertEqual(opened.st_mtime, written.st_mtime)
        self.assertLessExceptWindows(written.st_mtime, flushed.st_mtime)
        self.assertLessEqual(flushed.st_mtime, closed.st_mtime)


class TestFakeModeW(FakeStatTestBase):
    def setUp(self):
        super(TestFakeModeW, self).setUp()
        self.mode = 'w'

    def test_open_close_new_file(self):
        self.check_open_close_new_file()

    def test_open_write_close_new_file(self):
        self.check_open_write_close_new_file()

    def test_open_close(self):
        self.check_open_close_w_mode()

    def test_open_write_close(self):
        self.check_open_write_close_w_mode()

    def test_open_flush_close(self):
        self.check_open_flush_close_w_mode()

    def test_open_write_flush_close(self):
        self.check_open_write_flush_close_w_mode()

    def test_read_raises(self):
        with self.open(self.file_path, 'w') as f:
            with self.assertRaises(OSError):
                f.read()


class TestRealModeW(TestFakeModeW):
    def use_real_fs(self):
        return True


class TestFakeModeWPlus(FakeStatTestBase):
    def setUp(self):
        super(TestFakeModeWPlus, self).setUp()
        self.mode = 'w+'

    def test_open_close_new_file(self):
        self.check_open_close_new_file()

    def test_open_write_close_new_file(self):
        self.check_open_write_close_new_file()

    def test_open_read_close_new_file(self):
        self.check_open_read_close_new_file()

    def test_open_close(self):
        self.check_open_close_w_mode()

    def test_open_write_close(self):
        self.check_open_write_close_w_mode()

    def test_open_read_close(self):
        """
        When an existing file is opened with 'w+' mode and is then written to,
        st_ctime (Posix only) and st_mtime are updated on open
        (truncating) and again on close (flush). Under Posix, st_atime is
        updated on read.
        """
        before, opened, read, closed = self.open_read_close()

        self.assertLessExceptWindows(before.st_ctime, opened.st_ctime)
        self.assertEqual(opened.st_ctime, read.st_ctime)
        self.assertEqual(read.st_ctime, closed.st_ctime)

        self.assertLessEqual(before.st_atime, opened.st_atime)
        self.assertLessEqual(opened.st_atime, read.st_atime)
        self.assertEqual(read.st_atime, closed.st_atime)

        self.assertLess(before.st_mtime, opened.st_mtime)
        self.assertEqual(opened.st_mtime, read.st_mtime)
        self.assertEqual(read.st_mtime, closed.st_mtime)

    def test_open_flush_close(self):
        self.check_open_flush_close_w_mode()

    def test_open_write_flush_close(self):
        self.check_open_write_flush_close_w_mode()


class TestRealModeWPlus(TestFakeModeWPlus):
    def use_real_fs(self):
        return True


class TestFakeModeA(FakeStatTestBase):
    def setUp(self):
        super(TestFakeModeA, self).setUp()
        self.mode = 'a'

    def test_open_close_new_file(self):
        self.check_open_close_new_file()

    def test_open_write_close_new_file(self):
        self.check_open_write_close_new_file()

    def test_open_close(self):
        self.check_open_close_non_w_mode()

    def test_open_write_close(self):
        self.check_open_write_close_non_w_mode()

    def test_open_flush_close(self):
        self.check_open_flush_close_non_w_mode()

    def test_open_write_flush_close(self):
        self.check_open_write_flush_close_non_w_mode()

    def test_read_raises(self):
        with self.open(self.file_path, 'a') as f:
            with self.assertRaises(OSError):
                f.read()


class TestRealModeA(TestFakeModeA):
    def use_real_fs(self):
        return True


class TestFakeModeAPlus(FakeStatTestBase):
    def setUp(self):
        super(TestFakeModeAPlus, self).setUp()
        self.mode = 'a+'

    def test_open_close_new_file(self):
        self.check_open_close_new_file()

    def test_open_write_close_new_file(self):
        self.check_open_write_close_new_file()

    def test_open_read_close_new_file(self):
        self.check_open_read_close_new_file()

    def test_open_close(self):
        self.check_open_close_non_w_mode()

    def test_open_write_close(self):
        self.check_open_write_close_non_w_mode()

    def test_open_read_close(self):
        self.check_open_read_close_non_w_mode()

    def test_open_flush_close(self):
        self.check_open_flush_close_non_w_mode()

    def test_open_write_flush_close(self):
        self.check_open_write_flush_close_non_w_mode()


class TestRealModeAPlus(TestFakeModeAPlus):
    def use_real_fs(self):
        return True


class TestFakeModeR(FakeStatTestBase):
    def setUp(self):
        super(TestFakeModeR, self).setUp()
        self.mode = 'r'

    def test_open_close(self):
        self.check_open_close_non_w_mode()

    def test_open_read_close(self):
        self.check_open_read_close_non_w_mode()

    def test_open_flush_close(self):
        self.check_open_flush_close_non_w_mode()

    def test_open_read_flush_close(self):
        """
        When an existing file is opened with 'r' mode, read, flushed and
        closed, st_atime is updated after reading under Posix.
        """
        before, opened, read, flushed, closed = self.open_read_flush()

        self.assertEqual(before.st_ctime, opened.st_ctime)
        self.assertEqual(opened.st_ctime, read.st_ctime)
        self.assertEqual(read.st_ctime, flushed.st_ctime)
        self.assertEqual(flushed.st_ctime, closed.st_ctime)

        self.assertEqual(before.st_atime, opened.st_atime)
        self.assertLessEqual(opened.st_atime, read.st_atime)
        self.assertEqual(read.st_atime, flushed.st_atime)
        self.assertEqual(flushed.st_atime, closed.st_atime)

        self.assertEqual(before.st_mtime, opened.st_mtime)
        self.assertEqual(opened.st_mtime, read.st_mtime)
        self.assertEqual(read.st_mtime, flushed.st_mtime)
        self.assertEqual(flushed.st_mtime, closed.st_mtime)

    def test_open_not_existing_raises(self):
        with self.assertRaises(OSError):
            with self.open(self.file_path, 'r'):
                pass


class TestRealModeR(TestFakeModeR):
    def use_real_fs(self):
        return True


class TestFakeModeRPlus(FakeStatTestBase):
    def setUp(self):
        super(TestFakeModeRPlus, self).setUp()
        self.mode = 'r+'

    def test_open_close(self):
        self.check_open_close_non_w_mode()

    def test_open_write_close(self):
        self.check_open_write_close_non_w_mode()

    def test_open_read_close(self):
        self.check_open_read_close_non_w_mode()

    def test_open_flush_close(self):
        self.check_open_flush_close_non_w_mode()

    def test_open_write_flush_close(self):
        self.check_open_write_flush_close_non_w_mode()

    def test_open_not_existing_raises(self):
        with self.assertRaises(OSError):
            with self.open(self.file_path, 'r+'):
                pass


class TestRealModeRPlus(TestFakeModeRPlus):
    def use_real_fs(self):
        return True


if __name__ == '__main__':
    unittest.main()
