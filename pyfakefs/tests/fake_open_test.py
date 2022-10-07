# -*- coding: utf-8 -*-
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

"""Unit tests for fake_filesystem.FakeOsModule."""

import errno
import io
import locale
import os
import stat
import sys
import time
import unittest

from pyfakefs import fake_filesystem
from pyfakefs.fake_filesystem import is_root, PERM_READ, FakeIoModule
from pyfakefs.fake_filesystem_unittest import PatchMode
from pyfakefs.tests.test_utils import RealFsTestCase


class FakeFileOpenTestBase(RealFsTestCase):
    def setUp(self):
        super(FakeFileOpenTestBase, self).setUp()
        if self.use_real_fs():
            self.open = io.open
        else:
            self.fake_io_module = FakeIoModule(self.filesystem)
            self.open = self.fake_io_module.open

    def path_separator(self):
        return '!'


class FakeFileOpenTest(FakeFileOpenTestBase):
    def setUp(self):
        super(FakeFileOpenTest, self).setUp()
        self.orig_time = time.time

    def tearDown(self):
        super(FakeFileOpenTest, self).tearDown()
        time.time = self.orig_time

    def test_open_no_parent_dir(self):
        """Expect raise when opening a file in a missing directory."""
        file_path = self.make_path('foo', 'bar.txt')
        self.assert_raises_os_error(errno.ENOENT, self.open, file_path, 'w')

    def test_delete_on_close(self):
        self.skip_real_fs()
        file_dir = 'boo'
        file_path = 'boo!far'
        self.os.mkdir(file_dir)
        self.open = fake_filesystem.FakeFileOpen(self.filesystem,
                                                 delete_on_close=True)
        with self.open(file_path, 'w'):
            self.assertTrue(self.filesystem.exists(file_path))
        self.assertFalse(self.filesystem.exists(file_path))

    def test_no_delete_on_close_by_default(self):
        file_path = self.make_path('czar')
        with self.open(file_path, 'w'):
            self.assertTrue(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.exists(file_path))

    def test_compatibility_of_with_statement(self):
        self.skip_real_fs()
        self.open = fake_filesystem.FakeFileOpen(self.filesystem,
                                                 delete_on_close=True)
        file_path = 'foo'
        self.assertFalse(self.os.path.exists(file_path))
        with self.open(file_path, 'w'):
            self.assertTrue(self.os.path.exists(file_path))
        # After the 'with' statement, the close() method should have been
        # called.
        self.assertFalse(self.os.path.exists(file_path))

    def test_unicode_contents(self):
        file_path = self.make_path('foo')
        # note that this will work only if the string can be represented
        # by the locale preferred encoding - which under Windows is
        # usually not UTF-8, but something like Latin1, depending on the locale
        text_fractions = 'Ümläüts'
        try:
            with self.open(file_path, 'w') as f:
                f.write(text_fractions)
        except UnicodeEncodeError:
            # see https://github.com/pytest-dev/pyfakefs/issues/623
            self.skipTest("This test does not work with an ASCII locale")

        with self.open(file_path) as f:
            contents = f.read()
        self.assertEqual(contents, text_fractions)

    def test_byte_contents(self):
        file_path = self.make_path('foo')
        byte_fractions = b'\xe2\x85\x93 \xe2\x85\x94 \xe2\x85\x95 \xe2\x85\x96'
        with self.open(file_path, 'wb') as f:
            f.write(byte_fractions)
        # the encoding has to be specified, otherwise the locale default
        # is used which can be different on different systems
        with self.open(file_path, encoding='utf-8') as f:
            contents = f.read()
        self.assertEqual(contents, byte_fractions.decode('utf-8'))

    def test_write_str_read_bytes(self):
        file_path = self.make_path('foo')
        str_contents = 'Äsgül'
        try:
            with self.open(file_path, 'w') as f:
                f.write(str_contents)
        except UnicodeEncodeError:
            # see https://github.com/pytest-dev/pyfakefs/issues/623
            self.skipTest("This test does not work with an ASCII locale")
        with self.open(file_path, 'rb') as f:
            contents = f.read()
        self.assertEqual(str_contents, contents.decode(
            locale.getpreferredencoding(False)))

    def test_open_valid_file(self):
        contents = [
            'I am he as\n',
            'you are he as\n',
            'you are me and\n',
            'we are all together\n'
        ]
        file_path = self.make_path('bar.txt')
        self.create_file(file_path, contents=''.join(contents))
        with self.open(file_path) as fake_file:
            self.assertEqual(contents, fake_file.readlines())

    def test_open_valid_args(self):
        contents = [
            "Bang bang Maxwell's silver hammer\n",
            'Came down on her head',
        ]
        file_path = self.make_path('abbey_road', 'maxwell')
        self.create_file(file_path, contents=''.join(contents))

        with self.open(file_path, buffering=1) as f:
            self.assertEqual(contents, f.readlines())
        with self.open(file_path, buffering=1,
                       errors='strict', newline='\n', opener=None) as f:
            expected_contents = [contents[0][:-1] + self.os.linesep,
                                 contents[1]]
            self.assertEqual(expected_contents, f.readlines())

    def test_open_valid_file_with_cwd(self):
        contents = [
            'I am he as\n',
            'you are he as\n',
            'you are me and\n',
            'we are all together\n'
        ]
        file_path = self.make_path('bar.txt')
        self.create_file(file_path, contents=''.join(contents))
        self.os.chdir(self.base_path)
        with self.open(file_path) as f:
            self.assertEqual(contents, f.readlines())

    def test_iterate_over_file(self):
        contents = [
            "Bang bang Maxwell's silver hammer",
            'Came down on her head',
        ]
        file_path = self.make_path('abbey_road', 'maxwell')
        self.create_file(file_path, contents='\n'.join(contents))
        with self.open(file_path) as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def test_next_over_file(self):
        contents = [
            'Live long\n',
            'and prosper\n'
        ]
        result = []
        file_path = self.make_path('foo.txt')
        self.create_file(file_path, contents=''.join(contents))
        with self.open(file_path) as fake_file:
            result.append(next(fake_file))
            result.append(next(fake_file))
        self.assertEqual(contents, result)

    def test_open_directory_error(self):
        directory_path = self.make_path('foo')
        self.os.mkdir(directory_path)
        if self.is_windows:
            self.assert_raises_os_error(errno.EACCES, self.open.__call__,
                                        directory_path)
        else:
            self.assert_raises_os_error(errno.EISDIR, self.open.__call__,
                                        directory_path)

    def test_create_file_with_write(self):
        contents = [
            "Here comes the sun, little darlin'",
            'Here comes the sun, and I say,',
            "It's alright",
        ]
        file_dir = self.make_path('abbey_road')
        file_path = self.os.path.join(file_dir, 'here_comes_the_sun')
        self.os.mkdir(file_dir)
        with self.open(file_path, 'w') as fake_file:
            for line in contents:
                fake_file.write(line + '\n')
        with self.open(file_path) as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def test_create_file_with_append(self):
        contents = [
            "Here comes the sun, little darlin'",
            'Here comes the sun, and I say,',
            "It's alright",
        ]
        file_dir = self.make_path('abbey_road')
        file_path = self.os.path.join(file_dir, 'here_comes_the_sun')
        self.os.mkdir(file_dir)
        with self.open(file_path, 'a') as fake_file:
            for line in contents:
                fake_file.write(line + '\n')
        with self.open(file_path) as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def test_exclusive_create_file_failure(self):
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('bar')
        self.create_file(file_path)
        self.assert_raises_os_error(errno.EEXIST, self.open, file_path, 'x')
        self.assert_raises_os_error(errno.EEXIST, self.open, file_path, 'xb')

    def test_exclusive_create_file(self):
        file_dir = self.make_path('foo')
        file_path = self.os.path.join(file_dir, 'bar')
        self.os.mkdir(file_dir)
        contents = 'String contents'
        with self.open(file_path, 'x') as fake_file:
            fake_file.write(contents)
        with self.open(file_path) as fake_file:
            self.assertEqual(contents, fake_file.read())

    def test_exclusive_create_binary_file(self):
        file_dir = self.make_path('foo')
        file_path = self.os.path.join(file_dir, 'bar')
        self.os.mkdir(file_dir)
        contents = b'Binary contents'
        with self.open(file_path, 'xb') as fake_file:
            fake_file.write(contents)
        with self.open(file_path, 'rb') as fake_file:
            self.assertEqual(contents, fake_file.read())

    def test_overwrite_existing_file(self):
        file_path = self.make_path('overwite')
        self.create_file(file_path, contents='To disappear')
        new_contents = [
            'Only these lines',
            'should be in the file.',
        ]
        with self.open(file_path, 'w') as fake_file:
            for line in new_contents:
                fake_file.write(line + '\n')
        with self.open(file_path) as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(new_contents, result)

    def test_append_existing_file(self):
        file_path = self.make_path('appendfile')
        contents = [
            'Contents of original file'
            'Appended contents',
        ]

        self.create_file(file_path, contents=contents[0])
        with self.open(file_path, 'a') as fake_file:
            for line in contents[1:]:
                fake_file.write(line + '\n')
        with self.open(file_path) as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def test_open_with_wplus(self):
        # set up
        file_path = self.make_path('wplus_file')
        self.create_file(file_path, contents='old contents')
        self.assertTrue(self.os.path.exists(file_path))
        with self.open(file_path, 'r') as fake_file:
            self.assertEqual('old contents', fake_file.read())
        # actual tests
        with self.open(file_path, 'w+') as fake_file:
            fake_file.write('new contents')
            fake_file.seek(0)
            self.assertTrue('new contents', fake_file.read())

    def test_open_with_wplus_truncation(self):
        # set up
        file_path = self.make_path('wplus_file')
        self.create_file(file_path, contents='old contents')
        self.assertTrue(self.os.path.exists(file_path))
        with self.open(file_path, 'r') as fake_file:
            self.assertEqual('old contents', fake_file.read())
        # actual tests
        with self.open(file_path, 'w+') as fake_file:
            fake_file.seek(0)
            self.assertEqual('', fake_file.read())

    def test_open_with_append_flag(self):
        contents = [
            'I am he as\n',
            'you are he as\n',
            'you are me and\n',
            'we are all together\n'
        ]
        additional_contents = [
            'These new lines\n',
            'like you a lot.\n'
        ]
        file_path = self.make_path('appendfile')
        self.create_file(file_path, contents=''.join(contents))
        with self.open(file_path, 'a') as fake_file:
            with self.assertRaises(io.UnsupportedOperation):
                fake_file.read(0)
            with self.assertRaises(io.UnsupportedOperation):
                fake_file.readline()
            expected_len = len(''.join(contents))
            expected_len += len(contents) * (len(self.os.linesep) - 1)
            self.assertEqual(expected_len, fake_file.tell())
            fake_file.seek(0)
            self.assertEqual(0, fake_file.tell())
            fake_file.writelines(additional_contents)
        with self.open(file_path) as fake_file:
            self.assertEqual(
                contents + additional_contents, fake_file.readlines())

    def check_append_with_aplus(self):
        file_path = self.make_path('aplus_file')
        self.create_file(file_path, contents='old contents')
        self.assertTrue(self.os.path.exists(file_path))
        with self.open(file_path, 'r') as fake_file:
            self.assertEqual('old contents', fake_file.read())

        if self.filesystem:
            # need to recreate FakeFileOpen for OS specific initialization
            self.open = fake_filesystem.FakeFileOpen(self.filesystem,
                                                     delete_on_close=True)
        with self.open(file_path, 'a+') as fake_file:
            self.assertEqual(12, fake_file.tell())
            fake_file.write('new contents')
            self.assertEqual(24, fake_file.tell())
            fake_file.seek(0)
            self.assertEqual('old contentsnew contents', fake_file.read())

    def test_append_with_aplus_mac_os(self):
        self.check_macos_only()
        self.check_append_with_aplus()

    def test_append_with_aplus_linux_windows(self):
        self.check_linux_and_windows()
        self.check_append_with_aplus()

    def test_append_with_aplus_read_with_loop(self):
        # set up
        file_path = self.make_path('aplus_file')
        self.create_file(file_path, contents='old contents')
        self.assertTrue(self.os.path.exists(file_path))
        with self.open(file_path, 'r') as fake_file:
            self.assertEqual('old contents', fake_file.read())
        # actual tests
        with self.open(file_path, 'a+') as fake_file:
            fake_file.seek(0)
            fake_file.write('new contents')
            fake_file.seek(0)
            for line in fake_file:
                self.assertEqual('old contentsnew contents', line)

    def test_read_empty_file_with_aplus(self):
        file_path = self.make_path('aplus_file')
        with self.open(file_path, 'a+') as fake_file:
            self.assertEqual('', fake_file.read())

    def test_read_with_rplus(self):
        # set up
        file_path = self.make_path('rplus_file')
        self.create_file(file_path, contents='old contents here')
        self.assertTrue(self.os.path.exists(file_path))
        with self.open(file_path, 'r') as fake_file:
            self.assertEqual('old contents here', fake_file.read())
        # actual tests
        with self.open(file_path, 'r+') as fake_file:
            self.assertEqual('old contents here', fake_file.read())
            fake_file.seek(0)
            fake_file.write('new contents')
            fake_file.seek(0)
            self.assertEqual('new contents here', fake_file.read())

    def create_with_permission(self, file_path, perm_bits):
        self.create_file(file_path)
        self.os.chmod(file_path, perm_bits)
        if perm_bits & PERM_READ:
            st = self.os.stat(file_path)
            self.assert_mode_equal(perm_bits, st.st_mode)
            self.assertTrue(st.st_mode & stat.S_IFREG)
            self.assertFalse(st.st_mode & stat.S_IFDIR)

    def test_open_flags700(self):
        # set up
        self.check_posix_only()
        file_path = self.make_path('target_file')
        self.create_with_permission(file_path, 0o700)
        # actual tests
        self.open(file_path, 'r').close()
        self.open(file_path, 'w').close()
        self.open(file_path, 'w+').close()
        with self.assertRaises(ValueError):
            self.open(file_path, 'INV')

    def test_open_flags400(self):
        # set up
        self.check_posix_only()
        file_path = self.make_path('target_file')
        self.create_with_permission(file_path, 0o400)
        # actual tests
        self.open(file_path, 'r').close()
        if not is_root():
            self.assert_raises_os_error(
                errno.EACCES, self.open, file_path, 'w')
            self.assert_raises_os_error(
                errno.EACCES, self.open, file_path, 'w+')
        else:
            self.open(file_path, 'w').close()
            self.open(file_path, 'w+').close()

    def test_open_flags200(self):
        # set up
        self.check_posix_only()
        file_path = self.make_path('target_file')
        self.create_with_permission(file_path, 0o200)
        # actual tests
        self.open(file_path, 'w').close()
        if not is_root():
            with self.assertRaises(OSError):
                self.open(file_path, 'r')
            with self.assertRaises(OSError):
                self.open(file_path, 'w+')
        else:
            self.open(file_path, 'r').close()
            self.open(file_path, 'w+').close()

    def test_open_flags100(self):
        # set up
        self.check_posix_only()
        file_path = self.make_path('target_file')
        self.create_with_permission(file_path, 0o100)
        # actual tests
        if not is_root():
            with self.assertRaises(OSError):
                self.open(file_path, 'r')
            with self.assertRaises(OSError):
                self.open(file_path, 'w')
            with self.assertRaises(OSError):
                self.open(file_path, 'w+')
        else:
            self.open(file_path, 'r').close()
            self.open(file_path, 'w').close()
            self.open(file_path, 'w+').close()

    def test_follow_link_read(self):
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('foo', 'bar', 'baz')
        target = self.make_path('tarJAY')
        target_contents = 'real baz contents'
        self.create_file(target, contents=target_contents)
        self.create_symlink(link_path, target)
        self.assert_equal_paths(target, self.os.readlink(link_path))
        fh = self.open(link_path, 'r')
        got_contents = fh.read()
        fh.close()
        self.assertEqual(target_contents, got_contents)

    def test_follow_link_write(self):
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('foo', 'bar', 'TBD')
        target = self.make_path('tarJAY')
        target_contents = 'real baz contents'
        self.create_symlink(link_path, target)
        self.assertFalse(self.os.path.exists(target))

        with self.open(link_path, 'w') as fh:
            fh.write(target_contents)
        with self.open(target, 'r') as fh:
            got_contents = fh.read()
        self.assertEqual(target_contents, got_contents)

    def test_follow_intra_path_link_write(self):
        # Test a link in the middle of of a file path.
        self.skip_if_symlink_not_supported()
        link_path = self.os.path.join(
            self.base_path, 'foo', 'build', 'local_machine', 'output', '1')
        target = self.make_path('tmp', 'output', '1')
        self.create_dir(self.make_path('tmp', 'output'))
        self.create_symlink(self.os.path.join(
            self.base_path, 'foo', 'build', 'local_machine'),
            self.make_path('tmp'))

        self.assertFalse(self.os.path.exists(link_path))
        self.assertFalse(self.os.path.exists(target))

        target_contents = 'real baz contents'
        with self.open(link_path, 'w') as fh:
            fh.write(target_contents)
        with self.open(target, 'r') as fh:
            got_contents = fh.read()
        self.assertEqual(target_contents, got_contents)

    def test_open_raises_on_symlink_loop(self):
        # Regression test for #274
        self.check_posix_only()
        file_dir = self.make_path('foo')
        self.os.mkdir(file_dir)
        file_path = self.os.path.join(file_dir, 'baz')
        self.os.symlink(file_path, file_path)
        self.assert_raises_os_error(errno.ELOOP, self.open, file_path)

    def test_file_descriptors_for_different_files(self):
        first_path = self.make_path('some_file1')
        self.create_file(first_path, contents='contents here1')
        second_path = self.make_path('some_file2')
        self.create_file(second_path, contents='contents here2')
        third_path = self.make_path('some_file3')
        self.create_file(third_path, contents='contents here3')

        with self.open(first_path) as fake_file1:
            with self.open(second_path) as fake_file2:
                with self.open(third_path) as fake_file3:
                    fileno2 = fake_file2.fileno()
                    self.assertGreater(fileno2, fake_file1.fileno())
                    self.assertGreater(fake_file3.fileno(), fileno2)

    def test_file_descriptors_for_the_same_file_are_different(self):
        first_path = self.make_path('some_file1')
        self.create_file(first_path, contents='contents here1')
        second_path = self.make_path('some_file2')
        self.create_file(second_path, contents='contents here2')
        with self.open(first_path) as fake_file1:
            with self.open(second_path) as fake_file2:
                with self.open(first_path) as fake_file1a:
                    fileno2 = fake_file2.fileno()
                    self.assertGreater(fileno2, fake_file1.fileno())
                    self.assertGreater(fake_file1a.fileno(), fileno2)

    def test_reused_file_descriptors_do_not_affect_others(self):
        first_path = self.make_path('some_file1')
        self.create_file(first_path, contents='contents here1')
        second_path = self.make_path('some_file2')
        self.create_file(second_path, contents='contents here2')
        third_path = self.make_path('some_file3')
        self.create_file(third_path, contents='contents here3')

        with self.open(first_path, 'r') as fake_file1:
            with self.open(second_path, 'r') as fake_file2:
                fake_file3 = self.open(third_path, 'r')
                fake_file1a = self.open(first_path, 'r')
                fileno1 = fake_file1.fileno()
                fileno2 = fake_file2.fileno()
                fileno3 = fake_file3.fileno()
                fileno4 = fake_file1a.fileno()

        with self.open(second_path, 'r') as fake_file2:
            with self.open(first_path, 'r') as fake_file1b:
                self.assertEqual(fileno1, fake_file2.fileno())
                self.assertEqual(fileno2, fake_file1b.fileno())
                self.assertEqual(fileno3, fake_file3.fileno())
                self.assertEqual(fileno4, fake_file1a.fileno())
        fake_file3.close()
        fake_file1a.close()

    def test_intertwined_read_write(self):
        file_path = self.make_path('some_file')
        self.create_file(file_path)

        with self.open(file_path, 'a') as writer:
            with self.open(file_path, 'r') as reader:
                writes = ['hello', 'world\n', 'somewhere\nover', 'the\n',
                          'rainbow']
                reads = []
                # when writes are flushes, they are piped to the reader
                for write in writes:
                    writer.write(write)
                    writer.flush()
                    reads.append(reader.read())
                    reader.flush()
                self.assertEqual(writes, reads)
                writes = ['nothing', 'to\nsee', 'here']
                reads = []
                # when writes are not flushed, the reader doesn't read
                # anything new
                for write in writes:
                    writer.write(write)
                    reads.append(reader.read())
                self.assertEqual(['' for _ in writes], reads)

    def test_intertwined_read_write_python3_str(self):
        file_path = self.make_path('some_file')
        self.create_file(file_path)

        with self.open(file_path, 'a', encoding='utf-8') as writer:
            with self.open(file_path, 'r', encoding='utf-8') as reader:
                writes = ['привет', 'мир\n', 'где-то\nза', 'радугой']
                reads = []
                # when writes are flushes, they are piped to the reader
                for write in writes:
                    writer.write(write)
                    writer.flush()
                    reads.append(reader.read())
                    reader.flush()
                self.assertEqual(writes, reads)
                writes = ['ничего', 'не\nвидно']
                reads = []
                # when writes are not flushed, the reader doesn't
                # read anything new
                for write in writes:
                    writer.write(write)
                    reads.append(reader.read())
                self.assertEqual(['' for _ in writes], reads)

    def test_open_io_errors(self):
        file_path = self.make_path('some_file')
        self.create_file(file_path)

        with self.open(file_path, 'a') as fh:
            with self.assertRaises(OSError):
                fh.read()
            with self.assertRaises(OSError):
                fh.readlines()
        with self.open(file_path, 'w') as fh:
            with self.assertRaises(OSError):
                fh.read()
            with self.assertRaises(OSError):
                fh.readlines()
        with self.open(file_path, 'r') as fh:
            with self.assertRaises(OSError):
                fh.truncate()
            with self.assertRaises(OSError):
                fh.write('contents')
            with self.assertRaises(OSError):
                fh.writelines(['con', 'tents'])

        def _iterator_open(mode):
            with self.open(file_path, mode) as f:
                for _ in f:
                    pass

        with self.assertRaises(OSError):
            _iterator_open('w')
        with self.assertRaises(OSError):
            _iterator_open('a')

    def test_open_raises_io_error_if_parent_is_file_posix(self):
        self.check_posix_only()
        file_path = self.make_path('bar')
        self.create_file(file_path)
        file_path = self.os.path.join(file_path, 'baz')
        self.assert_raises_os_error(errno.ENOTDIR, self.open, file_path, 'w')

    def test_open_raises_io_error_if_parent_is_file_windows(self):
        self.check_windows_only()
        file_path = self.make_path('bar')
        self.create_file(file_path)
        file_path = self.os.path.join(file_path, 'baz')
        self.assert_raises_os_error(errno.ENOENT, self.open, file_path, 'w')

    def check_open_with_trailing_sep(self, error_nr):
        # regression test for #362
        path = self.make_path('foo') + self.os.path.sep
        self.assert_raises_os_error(error_nr, self.open, path, 'w')

    def test_open_with_trailing_sep_linux(self):
        self.check_linux_only()
        self.check_open_with_trailing_sep(errno.EISDIR)

    def test_open_with_trailing_sep_macos(self):
        self.check_macos_only()
        self.check_open_with_trailing_sep(errno.ENOENT)

    def test_open_with_trailing_sep_windows(self):
        self.check_windows_only()
        self.check_open_with_trailing_sep(errno.EINVAL)

    def test_can_read_from_block_device(self):
        self.skip_real_fs()
        device_path = 'device'
        self.filesystem.create_file(device_path, stat.S_IFBLK
                                    | fake_filesystem.PERM_ALL)
        with self.open(device_path, 'r') as fh:
            self.assertEqual('', fh.read())

    def test_truncate_flushes_contents(self):
        # Regression test for #285
        file_path = self.make_path('baz')
        self.create_file(file_path)
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            f0.truncate()
            self.assertEqual(4, self.os.path.getsize(file_path))

    def test_update_other_instances_of_same_file_on_flush(self):
        # Regression test for #302
        file_path = self.make_path('baz')
        with self.open(file_path, 'w') as f0:
            with self.open(file_path, 'w') as f1:
                f0.write('test')
                f0.truncate()
                f1.flush()
                self.assertEqual(4, self.os.path.getsize(file_path))

    def test_getsize_after_truncate(self):
        # Regression test for #412
        file_path = self.make_path('foo')
        with self.open(file_path, 'a') as f:
            f.write('a')
            f.seek(0)
            f.truncate()
            f.write('b')
            f.truncate()
            self.assertEqual(1, self.os.path.getsize(file_path))
            self.assertEqual(1, self.os.stat(file_path).st_size)

    def test_st_size_after_truncate(self):
        # Regression test for #412
        file_path = self.make_path('foo')
        with self.open(file_path, 'a') as f:
            f.write('a')
            f.truncate()
            f.write('b')
            f.truncate()
            self.assertEqual(2, self.os.stat(file_path).st_size)

    def test_that_read_over_end_does_not_reset_position(self):
        # Regression test for #286
        file_path = self.make_path('baz')
        self.create_file(file_path)
        with self.open(file_path) as f0:
            f0.seek(2)
            f0.read()
            self.assertEqual(2, f0.tell())

    def test_accessing_closed_file_raises(self):
        # Regression test for #275, #280
        if self.is_pypy:
            raise unittest.SkipTest('Different exceptions with PyPy')
        file_path = self.make_path('foo')
        self.create_file(file_path, contents=b'test')
        fake_file = self.open(file_path, 'r')
        fake_file.close()
        with self.assertRaises(ValueError):
            fake_file.read(1)
        with self.assertRaises(ValueError):
            fake_file.write('a')
        with self.assertRaises(ValueError):
            fake_file.readline()
        with self.assertRaises(ValueError):
            fake_file.truncate()
        with self.assertRaises(ValueError):
            fake_file.tell()
        with self.assertRaises(ValueError):
            fake_file.seek(1)
        with self.assertRaises(ValueError):
            fake_file.flush()

    def test_accessing_open_file_with_another_handle_raises(self):
        # Regression test for #282
        if self.is_pypy:
            raise unittest.SkipTest('Different exceptions with PyPy')
        file_path = self.make_path('foo')
        f0 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fake_file = self.open(file_path, 'r')
        fake_file.close()
        with self.assertRaises(ValueError):
            fake_file.read(1)
        with self.assertRaises(ValueError):
            fake_file.write('a')
        self.os.close(f0)

    def test_tell_flushes_under_mac_os(self):
        # Regression test for #288
        self.check_macos_only()
        file_path = self.make_path('foo')
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            self.assertEqual(4, f0.tell())
            self.assertEqual(4, self.os.path.getsize(file_path))

    def test_tell_flushes_in_python3(self):
        # Regression test for #288
        self.check_linux_and_windows()
        file_path = self.make_path('foo')
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            self.assertEqual(4, f0.tell())
            self.assertEqual(4, self.os.path.getsize(file_path))

    def test_read_flushes_under_posix(self):
        # Regression test for #278
        self.check_posix_only()
        file_path = self.make_path('foo')
        with self.open(file_path, 'a+') as f0:
            f0.write('test')
            self.assertEqual('', f0.read())
            self.assertEqual(4, self.os.path.getsize(file_path))

    def test_read_flushes_under_windows_in_python3(self):
        # Regression test for #278
        self.check_windows_only()
        file_path = self.make_path('foo')
        with self.open(file_path, 'w+') as f0:
            f0.write('test')
            f0.read()
            self.assertEqual(4, self.os.path.getsize(file_path))

    def test_seek_flushes(self):
        # Regression test for #290
        file_path = self.make_path('foo')
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            self.assertEqual(0, self.os.path.getsize(file_path))
            f0.seek(3)
            self.assertEqual(4, self.os.path.getsize(file_path))

    def test_truncate_flushes(self):
        # Regression test for #291
        file_path = self.make_path('foo')
        with self.open(file_path, 'a') as f0:
            f0.write('test')
            self.assertEqual(0, self.os.path.getsize(file_path))
            f0.truncate()
            self.assertEqual(4, self.os.path.getsize(file_path))

    def check_seek_outside_and_truncate_sets_size(self, mode):
        # Regression test for #294 and #296
        file_path = self.make_path('baz')
        with self.open(file_path, mode) as f0:
            f0.seek(1)
            f0.truncate()
            self.assertEqual(1, f0.tell())
            self.assertEqual(1, self.os.path.getsize(file_path))
            f0.seek(1)
            self.assertEqual(1, self.os.path.getsize(file_path))
        self.assertEqual(1, self.os.path.getsize(file_path))

    def test_seek_outside_and_truncate_sets_size_in_write_mode(self):
        # Regression test for #294
        self.check_seek_outside_and_truncate_sets_size('w')

    def test_seek_outside_and_truncate_sets_size_in_append_mode(self):
        # Regression test for #295
        self.check_seek_outside_and_truncate_sets_size('a')

    def test_closed(self):
        file_path = self.make_path('foo')
        f = self.open(file_path, 'w')
        self.assertFalse(f.closed)
        f.close()
        self.assertTrue(f.closed)
        f = self.open(file_path)
        self.assertFalse(f.closed)
        f.close()
        self.assertTrue(f.closed)

    def test_closing_closed_file_does_nothing(self):
        # Regression test for #299
        file_path = self.make_path('baz')
        f0 = self.open(file_path, 'w')
        f0.close()
        with self.open(file_path) as f1:
            # would close f1 if not handled
            f0.close()
            self.assertEqual('', f1.read())

    def test_closing_file_with_different_close_mode(self):
        self.skip_real_fs()
        filename = self.make_path('test.txt')
        fd = self.os.open(filename, os.O_CREAT | os.O_RDWR)
        file_obj = self.filesystem.get_object(filename)
        with self.open(fd, 'wb', closefd=False) as fp:
            fp.write(b'test')
        self.assertTrue(self.filesystem.has_open_file(file_obj))
        self.os.close(fd)
        self.assertFalse(self.filesystem.has_open_file(file_obj))

    def test_truncate_flushes_zeros(self):
        # Regression test for #301
        file_path = self.make_path('baz')
        with self.open(file_path, 'w') as f0:
            with self.open(file_path) as f1:
                f0.seek(1)
                f0.truncate()
                self.assertEqual('\0', f1.read())

    def test_byte_filename(self):
        file_path = self.make_path(b'test')
        with self.open(file_path, 'wb') as f:
            f.write(b'test')
        with self.open(file_path, 'rb') as f:
            self.assertEqual(b'test', f.read())

    def test_unicode_filename(self):
        file_path = self.make_path('тест')
        with self.open(file_path, 'wb') as f:
            f.write(b'test')
        with self.open(file_path, 'rb') as f:
            self.assertEqual(b'test', f.read())

    def test_write_devnull(self):
        for mode in ('r+', 'w', 'w+', 'a', 'a+'):
            with self.open(self.os.devnull, mode) as f:
                f.write('test')
            with self.open(self.os.devnull) as f:
                self.assertEqual('', f.read())

    def test_utf16_text(self):
        # regression test for #574
        file_path = self.make_path('foo')
        with self.open(file_path, "w", encoding='utf-16') as f:
            assert f.write("1") == 1

        with self.open(file_path, "a", encoding='utf-16') as f:
            assert f.write("2") == 1

        with self.open(file_path, "r", encoding='utf-16') as f:
            text = f.read()
            assert text == "12"


class RealFileOpenTest(FakeFileOpenTest):
    def use_real_fs(self):
        return True


class FakeFileOpenWithOpenerTest(FakeFileOpenTestBase):
    def opener(self, path, flags):
        return self.os.open(path, flags)

    def test_use_opener_with_read(self):
        file_path = self.make_path('foo')
        self.create_file(file_path, contents='test')
        with self.open(file_path, opener=self.opener) as f:
            assert f.read() == 'test'
            with self.assertRaises(OSError):
                f.write('foo')

    def test_use_opener_with_read_plus(self):
        file_path = self.make_path('foo')
        self.create_file(file_path, contents='test')
        with self.open(file_path, 'r+', opener=self.opener) as f:
            assert f.read() == 'test'
            assert f.write('bar') == 3
        with self.open(file_path) as f:
            assert f.read() == 'testbar'

    def test_use_opener_with_write(self):
        file_path = self.make_path('foo')
        self.create_file(file_path, contents='foo')
        with self.open(file_path, 'w', opener=self.opener) as f:
            with self.assertRaises(OSError):
                f.read()
            assert f.write('bar') == 3
        with self.open(file_path) as f:
            assert f.read() == 'bar'

    def test_use_opener_with_write_plus(self):
        file_path = self.make_path('foo')
        self.create_file(file_path, contents='test')
        with self.open(file_path, 'w+', opener=self.opener) as f:
            assert f.read() == ''
            assert f.write('bar') == 3
        with self.open(file_path) as f:
            assert f.read() == 'bar'

    def test_use_opener_with_append(self):
        file_path = self.make_path('foo')
        self.create_file(file_path, contents='foo')
        with self.open(file_path, 'a', opener=self.opener) as f:
            assert f.write('bar') == 3
            with self.assertRaises(OSError):
                f.read()
        with self.open(file_path) as f:
            assert f.read() == 'foobar'

    def test_use_opener_with_append_plus(self):
        file_path = self.make_path('foo')
        self.create_file(file_path, contents='foo')
        with self.open(file_path, 'a+', opener=self.opener) as f:
            assert f.read() == ''
            assert f.write('bar') == 3
        with self.open(file_path) as f:
            assert f.read() == 'foobar'

    def test_use_opener_with_exclusive_write(self):
        file_path = self.make_path('foo')
        self.create_file(file_path, contents='test')
        with self.assertRaises(OSError):
            self.open(file_path, 'x', opener=self.opener)

        file_path = self.make_path('bar')
        with self.open(file_path, 'x', opener=self.opener) as f:
            assert f.write('bar') == 3
            with self.assertRaises(OSError):
                f.read()
        with self.open(file_path) as f:
            assert f.read() == 'bar'

    def test_use_opener_with_exclusive_plus(self):
        file_path = self.make_path('foo')
        self.create_file(file_path, contents='test')
        with self.assertRaises(OSError):
            self.open(file_path, 'x+', opener=self.opener)

        file_path = self.make_path('bar')
        with self.open(file_path, 'x+', opener=self.opener) as f:
            assert f.write('bar') == 3
            assert f.read() == ''
        with self.open(file_path) as f:
            assert f.read() == 'bar'


class RealFileOpenWithOpenerTest(FakeFileOpenWithOpenerTest):
    def use_real_fs(self):
        return True


@unittest.skipIf(sys.version_info < (3, 8),
                 'open_code only present since Python 3.8')
class FakeFilePatchedOpenCodeTest(FakeFileOpenTestBase):

    def setUp(self):
        super(FakeFilePatchedOpenCodeTest, self).setUp()
        if self.use_real_fs():
            self.open_code = io.open_code
        else:
            self.filesystem.patch_open_code = PatchMode.ON
            self.open_code = self.fake_io_module.open_code

    def tearDown(self):
        if not self.use_real_fs():
            self.filesystem.patch_open_code = False
        super(FakeFilePatchedOpenCodeTest, self).tearDown()

    def test_invalid_path(self):
        with self.assertRaises(TypeError):
            self.open_code(4)

    def test_byte_contents_open_code(self):
        byte_fractions = b'\xe2\x85\x93 \xe2\x85\x94 \xe2\x85\x95 \xe2\x85\x96'
        file_path = self.make_path('foo')
        self.create_file(file_path, contents=byte_fractions)
        with self.open_code(file_path) as f:
            contents = f.read()
        self.assertEqual(contents, byte_fractions)

    def test_open_code_in_real_fs(self):
        self.skip_real_fs()
        file_path = __file__
        with self.assertRaises(OSError):
            self.open_code(file_path)


class RealPatchedFileOpenCodeTest(FakeFilePatchedOpenCodeTest):
    def use_real_fs(self):
        return True


@unittest.skipIf(sys.version_info < (3, 8),
                 'open_code only present since Python 3.8')
class FakeFileUnpatchedOpenCodeTest(FakeFileOpenTestBase):

    def setUp(self):
        super(FakeFileUnpatchedOpenCodeTest, self).setUp()
        if self.use_real_fs():
            self.open_code = io.open_code
        else:
            self.open_code = self.fake_io_module.open_code

    def test_invalid_path(self):
        with self.assertRaises(TypeError):
            self.open_code(4)

    def test_open_code_in_real_fs(self):
        file_path = __file__

        with self.open_code(file_path) as f:
            contents = f.read()
        self.assertTrue(len(contents) > 100)


class RealUnpatchedFileOpenCodeTest(FakeFileUnpatchedOpenCodeTest):
    def use_real_fs(self):
        return True

    def test_byte_contents_open_code(self):
        byte_fractions = b'\xe2\x85\x93 \xe2\x85\x94 \xe2\x85\x95 \xe2\x85\x96'
        file_path = self.make_path('foo')
        self.create_file(file_path, contents=byte_fractions)
        with self.open_code(file_path) as f:
            contents = f.read()
        self.assertEqual(contents, byte_fractions)


class BufferingModeTest(FakeFileOpenTestBase):
    def test_no_buffering(self):
        file_path = self.make_path("buffertest.bin")
        with self.open(file_path, 'wb', buffering=0) as f:
            f.write(b'a' * 128)
            with self.open(file_path, "rb") as r:
                x = r.read()
                self.assertEqual(b'a' * 128, x)

    def test_no_buffering_not_allowed_in_textmode(self):
        file_path = self.make_path("buffertest.txt")
        with self.assertRaises(ValueError):
            self.open(file_path, 'w', buffering=0)

    def test_default_buffering_no_flush(self):
        file_path = self.make_path("buffertest.bin")
        with self.open(file_path, 'wb') as f:
            f.write(b'a' * 2048)
            with self.open(file_path, "rb") as r:
                x = r.read()
                self.assertEqual(b'', x)
        with self.open(file_path, "rb") as r:
            x = r.read()
            self.assertEqual(b'a' * 2048, x)

    def test_default_buffering_flush(self):
        file_path = self.make_path("buffertest.bin")
        with self.open(file_path, 'wb') as f:
            f.write(b'a' * 2048)
            f.flush()
            with self.open(file_path, "rb") as r:
                x = r.read()
                self.assertEqual(b'a' * 2048, x)

    def test_writing_with_specific_buffer(self):
        file_path = self.make_path("buffertest.bin")
        with self.open(file_path, 'wb', buffering=512) as f:
            f.write(b'a' * 500)
            with self.open(file_path, "rb") as r:
                x = r.read()
                # buffer not filled - not written
                self.assertEqual(0, len(x))
            f.write(b'a' * 400)
            with self.open(file_path, "rb") as r:
                x = r.read()
                # buffer exceeded, but new buffer (400) not - previous written
                self.assertEqual(500, len(x))
            f.write(b'a' * 100)
            with self.open(file_path, "rb") as r:
                x = r.read()
                # buffer not full (500) not written
                self.assertEqual(500, len(x))
            f.write(b'a' * 100)
            with self.open(file_path, "rb") as r:
                x = r.read()
                # buffer exceeded (600) -> write previous
                # new buffer not full (100) - not written
                self.assertEqual(1000, len(x))
            f.write(b'a' * 600)
            with self.open(file_path, "rb") as r:
                x = r.read()
                # new buffer exceeded (600) -> all written
                self.assertEqual(1700, len(x))

    def test_writing_text_with_line_buffer(self):
        file_path = self.make_path("buffertest.bin")
        with self.open(file_path, 'w', buffering=1) as f:
            f.write('test' * 100)
            with self.open(file_path, "r") as r:
                x = r.read()
                # no new line - not written
                self.assertEqual(0, len(x))
            f.write('\ntest')
            with self.open(file_path, "r") as r:
                x = r.read()
                # new line - buffer written
                self.assertEqual(405, len(x))
            f.write('test' * 10)
            with self.open(file_path, "r") as r:
                x = r.read()
                # buffer not filled - not written
                self.assertEqual(405, len(x))
            f.write('\ntest')
            with self.open(file_path, "r") as r:
                x = r.read()
                # new line - buffer written
                self.assertEqual(450, len(x))

    def test_writing_large_text_with_line_buffer(self):
        file_path = self.make_path("buffertest.bin")
        with self.open(file_path, 'w', buffering=1) as f:
            f.write('test' * 4000)
            with self.open(file_path, "r") as r:
                x = r.read()
                # buffer larger than default - written
                self.assertEqual(16000, len(x))
            f.write('test')
            with self.open(file_path, "r") as r:
                x = r.read()
                # buffer not filled - not written
                self.assertEqual(16000, len(x))
            f.write('\ntest')
            with self.open(file_path, "r") as r:
                x = r.read()
                # new line - buffer written
                self.assertEqual(16009, len(x))
            f.write('\ntest')
            with self.open(file_path, "r") as r:
                x = r.read()
                # another new line - buffer written
                self.assertEqual(16014, len(x))

    def test_writing_text_with_default_buffer(self):
        file_path = self.make_path("buffertest.txt")
        with self.open(file_path, 'w') as f:
            f.write('test' * 5)
            with self.open(file_path, "r") as r:
                x = r.read()
                # buffer not filled - not written
                self.assertEqual(0, len(x))
            f.write('\ntest')
            with self.open(file_path, "r") as r:
                x = r.read()
                # buffer exceeded, but new buffer (400) not - previous written
                self.assertEqual(0, len(x))
            f.write('test' * 10)
            with self.open(file_path, "r") as r:
                x = r.read()
                # buffer not filled - not written
                self.assertEqual(0, len(x))
            f.write('\ntest')
            with self.open(file_path, "r") as r:
                x = r.read()
                self.assertEqual(0, len(x))

    def test_writing_text_with_specific_buffer(self):
        file_path = self.make_path("buffertest.txt")
        with self.open(file_path, 'w', buffering=2) as f:
            f.write('a' * 8000)
            with self.open(file_path, "r") as r:
                x = r.read()
                # buffer not filled - not written
                self.assertEqual(0, len(x))
            f.write('test')
            with self.open(file_path, "r") as r:
                x = r.read()
                # buffer exceeded, but new buffer (400) not - previous written
                self.assertEqual(0, len(x))
            f.write('test')
            with self.open(file_path, "r") as r:
                x = r.read()
                # buffer not filled - not written
                self.assertEqual(0, len(x))
            f.write('test')
            with self.open(file_path, "r") as r:
                x = r.read()
                self.assertEqual(0, len(x))
        # with self.open(file_path, "r") as r:
        #     x = r.read()
        #     self.assertEqual(35, len(x))

    def test_append_with_specific_buffer(self):
        file_path = self.make_path("buffertest.bin")
        with self.open(file_path, 'wb', buffering=512) as f:
            f.write(b'a' * 500)
        with self.open(file_path, 'ab', buffering=512) as f:
            f.write(b'a' * 500)
            with self.open(file_path, "rb") as r:
                x = r.read()
                # buffer not filled - not written
                self.assertEqual(500, len(x))
            f.write(b'a' * 400)
            with self.open(file_path, "rb") as r:
                x = r.read()
                # buffer exceeded, but new buffer (400) not - previous written
                self.assertEqual(1000, len(x))
            f.write(b'a' * 100)
            with self.open(file_path, "rb") as r:
                x = r.read()
                # buffer not full (500) not written
                self.assertEqual(1000, len(x))
            f.write(b'a' * 100)
            with self.open(file_path, "rb") as r:
                x = r.read()
                # buffer exceeded (600) -> write previous
                # new buffer not full (100) - not written
                self.assertEqual(1500, len(x))
            f.write(b'a' * 600)
            with self.open(file_path, "rb") as r:
                x = r.read()
                # new buffer exceeded (600) -> all written
                self.assertEqual(2200, len(x))

    def test_failed_flush_does_not_truncate_file(self):
        # regression test for #548
        self.skip_real_fs()  # cannot set fs size in real fs
        self.filesystem.set_disk_usage(100)
        self.os.makedirs("foo")
        file_path = self.os.path.join('foo', 'bar.txt')
        with self.open(file_path, 'wb') as f:
            f.write(b'a' * 50)
            f.flush()
            with self.open(file_path, "rb") as r:
                x = r.read()
                self.assertTrue(x.startswith(b'a' * 50))
            with self.assertRaises(OSError):
                f.write(b'b' * 200)
                f.flush()
            with self.open(file_path, "rb") as r:
                x = r.read()
                self.assertTrue(x.startswith(b'a' * 50))
            f.truncate(50)

    def test_failed_write_does_not_truncate_file(self):
        # test the same with no buffering and no flush
        self.skip_real_fs()  # cannot set fs size in real fs
        self.filesystem.set_disk_usage(100)
        self.os.makedirs("foo")
        file_path = self.os.path.join('foo', 'bar.txt')
        with self.open(file_path, 'wb', buffering=0) as f:
            f.write(b'a' * 50)
            with self.open(file_path, "rb") as r:
                x = r.read()
                self.assertEqual(b'a' * 50, x)
            with self.assertRaises(OSError):
                f.write(b'b' * 200)
            with self.open(file_path, "rb") as r:
                x = r.read()
                self.assertEqual(b'a' * 50, x)


class RealBufferingTest(BufferingModeTest):
    def use_real_fs(self):
        return True


class OpenFileWithEncodingTest(FakeFileOpenTestBase):
    """Tests that are similar to some open file tests above but using
    an explicit text encoding."""

    def setUp(self):
        super(OpenFileWithEncodingTest, self).setUp()
        self.file_path = self.make_path('foo')

    def test_write_str_read_bytes(self):
        str_contents = u'علي بابا'
        with self.open(self.file_path, 'w', encoding='arabic') as f:
            f.write(str_contents)
        with self.open(self.file_path, 'rb') as f:
            contents = f.read()
        self.assertEqual(str_contents, contents.decode('arabic'))

    def test_write_str_error_modes(self):
        str_contents = u'علي بابا'
        with self.open(self.file_path, 'w', encoding='cyrillic') as f:
            with self.assertRaises(UnicodeEncodeError):
                f.write(str_contents)

        with self.open(self.file_path, 'w', encoding='ascii',
                       errors='xmlcharrefreplace') as f:
            f.write(str_contents)
        with self.open(self.file_path, 'r', encoding='ascii') as f:
            contents = f.read()
        self.assertEqual('&#1593;&#1604;&#1610; &#1576;&#1575;&#1576;&#1575;',
                         contents)

        with self.open(self.file_path, 'w', encoding='ascii',
                       errors='namereplace') as f:
            f.write(str_contents)
        with self.open(self.file_path, 'r', encoding='ascii') as f:
            contents = f.read()
        self.assertEqual(
            r'\N{ARABIC LETTER AIN}\N{ARABIC LETTER LAM}\N'
            r'{ARABIC LETTER YEH} \N{ARABIC LETTER BEH}\N'
            r'{ARABIC LETTER ALEF}\N{ARABIC LETTER BEH}'
            r'\N{ARABIC LETTER ALEF}', contents)

    def test_read_str_error_modes(self):
        str_contents = u'علي بابا'
        with self.open(self.file_path, 'w', encoding='arabic') as f:
            f.write(str_contents)

        # default strict encoding
        with self.open(self.file_path, encoding='ascii') as f:
            with self.assertRaises(UnicodeDecodeError):
                f.read()
        with self.open(self.file_path, encoding='ascii',
                       errors='replace') as f:
            contents = f.read()
        self.assertNotEqual(str_contents, contents)

        with self.open(self.file_path, encoding='ascii',
                       errors='backslashreplace') as f:
            contents = f.read()
        self.assertEqual(r'\xd9\xe4\xea \xc8\xc7\xc8\xc7', contents)

    def test_write_and_read_str(self):
        str_contents = u'علي بابا'
        with self.open(self.file_path, 'w', encoding='arabic') as f:
            f.write(str_contents)
        with self.open(self.file_path, 'r', encoding='arabic') as f:
            contents = f.read()
        self.assertEqual(str_contents, contents)

    def test_create_file_with_append(self):
        contents = [
            u'Allons enfants de la Patrie,'
            u'Le jour de gloire est arrivé!',
            u'Contre nous de la tyrannie,',
            u'L’étendard sanglant est levé.',
        ]
        with self.open(self.file_path, 'a', encoding='utf-8') as fake_file:
            for line in contents:
                fake_file.write(line + '\n')
        with self.open(self.file_path, encoding='utf-8') as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def test_append_existing_file(self):
        contents = [
            u'Оригинальное содержание'
            u'Дополнительное содержание',
        ]
        self.create_file(self.file_path, contents=contents[0],
                         encoding='cyrillic')
        with self.open(self.file_path, 'a', encoding='cyrillic') as fake_file:
            for line in contents[1:]:
                fake_file.write(line + '\n')
        with self.open(self.file_path, encoding='cyrillic') as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def test_open_with_wplus(self):
        self.create_file(self.file_path,
                         contents=u'старое содержание',
                         encoding='cyrillic')
        with self.open(self.file_path, 'r', encoding='cyrillic') as fake_file:
            self.assertEqual(u'старое содержание', fake_file.read())

        with self.open(self.file_path, 'w+', encoding='cyrillic') as fake_file:
            fake_file.write(u'новое содержание')
            fake_file.seek(0)
            self.assertTrue(u'новое содержание', fake_file.read())

    def test_open_with_append_flag(self):
        contents = [
            u'Калинка,\n',
            u'калинка,\n',
            u'калинка моя,\n'
        ]
        additional_contents = [
            u'В саду ягода-малинка,\n',
            u'малинка моя.\n'
        ]
        self.create_file(self.file_path, contents=''.join(contents),
                         encoding='cyrillic')
        with self.open(self.file_path, 'a', encoding='cyrillic') as fake_file:
            with self.assertRaises(io.UnsupportedOperation):
                fake_file.read(0)
            with self.assertRaises(io.UnsupportedOperation):
                fake_file.readline()
            self.assertEqual(len(''.join(contents)), fake_file.tell())
            fake_file.seek(0)
            self.assertEqual(0, fake_file.tell())
            fake_file.writelines(additional_contents)
        with self.open(self.file_path, encoding='cyrillic') as fake_file:
            self.assertEqual(contents + additional_contents,
                             fake_file.readlines())

    def test_append_with_aplus(self):
        self.create_file(self.file_path,
                         contents=u'старое содержание',
                         encoding='cyrillic')
        fake_file = self.open(self.file_path, 'r', encoding='cyrillic')
        fake_file.close()

        with self.open(self.file_path, 'a+', encoding='cyrillic') as fake_file:
            self.assertEqual(17, fake_file.tell())
            fake_file.write(u'новое содержание')
            self.assertEqual(33, fake_file.tell())
            fake_file.seek(0)
            self.assertEqual(u'старое содержаниеновое содержание',
                             fake_file.read())

    def test_read_with_rplus(self):
        self.create_file(self.file_path,
                         contents=u'старое содержание здесь',
                         encoding='cyrillic')
        fake_file = self.open(self.file_path, 'r', encoding='cyrillic')
        fake_file.close()

        with self.open(self.file_path, 'r+', encoding='cyrillic') as fake_file:
            self.assertEqual(u'старое содержание здесь', fake_file.read())
            fake_file.seek(0)
            fake_file.write(u'новое  содержание')
            fake_file.seek(0)
            self.assertEqual(u'новое  содержание здесь', fake_file.read())


class OpenRealFileWithEncodingTest(OpenFileWithEncodingTest):
    def use_real_fs(self):
        return True


class FakeFileOpenLineEndingTest(FakeFileOpenTestBase):
    def setUp(self):
        super(FakeFileOpenLineEndingTest, self).setUp()

    def test_read_default_newline_mode(self):
        file_path = self.make_path('some_file')
        for contents in (b'1\n2', b'1\r\n2', b'1\r2'):
            self.create_file(file_path, contents=contents)
            with self.open(file_path, mode='r') as f:
                self.assertEqual(['1\n', '2'], f.readlines())
            with self.open(file_path, mode='r') as f:
                self.assertEqual('1\n2', f.read())
            with self.open(file_path, mode='rb') as f:
                self.assertEqual(contents, f.read())

    def test_write_universal_newline_mode(self):
        file_path = self.make_path('some_file')
        with self.open(file_path, 'w') as f:
            f.write('1\n2')
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(b'1' + self.os.linesep.encode() + b'2',
                             f.read())

        with self.open(file_path, 'w') as f:
            f.write('1\r\n2')
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(b'1\r' + self.os.linesep.encode() + b'2',
                             f.read())

    def test_read_with_newline_arg(self):
        file_path = self.make_path('some_file')
        file_contents = b'1\r\n2\n3\r4'
        self.create_file(file_path, contents=file_contents)
        with self.open(file_path, mode='r', newline='') as f:
            self.assertEqual('1\r\n2\n3\r4', f.read())
        with self.open(file_path, mode='r', newline='\r') as f:
            self.assertEqual('1\r\n2\n3\r4', f.read())
        with self.open(file_path, mode='r', newline='\n') as f:
            self.assertEqual('1\r\n2\n3\r4', f.read())
        with self.open(file_path, mode='r', newline='\r\n') as f:
            self.assertEqual('1\r\n2\n3\r4', f.read())

    def test_readlines_with_newline_arg(self):
        file_path = self.make_path('some_file')
        file_contents = b'1\r\n2\n3\r4'
        self.create_file(file_path, contents=file_contents)
        with self.open(file_path, mode='r', newline='') as f:
            self.assertEqual(['1\r\n', '2\n', '3\r', '4'],
                             f.readlines())
        with self.open(file_path, mode='r', newline='\r') as f:
            self.assertEqual(['1\r', '\n2\n3\r', '4'], f.readlines())
        with self.open(file_path, mode='r', newline='\n') as f:
            self.assertEqual(['1\r\n', '2\n', '3\r4'], f.readlines())
        with self.open(file_path, mode='r', newline='\r\n') as f:
            self.assertEqual(['1\r\n', '2\n3\r4'], f.readlines())

    @unittest.skipIf(sys.version_info >= (3, 10), "U flag no longer supported")
    def test_read_with_ignored_universal_newlines_flag(self):
        file_path = self.make_path('some_file')
        file_contents = b'1\r\n2\n3\r4'
        self.create_file(file_path, contents=file_contents)
        with self.open(file_path, mode='r', newline='\r') as f:
            self.assertEqual('1\r\n2\n3\r4', f.read())
        with self.open(file_path, mode='r', newline='\r') as f:
            self.assertEqual('1\r\n2\n3\r4', f.read())
        with self.open(file_path, mode='U', newline='\r') as f:
            self.assertEqual('1\r\n2\n3\r4', f.read())

    @unittest.skipIf(sys.version_info < (3, 11), "U flag still supported")
    def test_universal_newlines_flag_not_supported(self):
        file_path = self.make_path('some_file')
        file_contents = b'1\r\n2\n3\r4'
        self.create_file(file_path, contents=file_contents)
        with self.assertRaises(ValueError):
            self.open(file_path, mode='U', newline='\r')

    def test_write_with_newline_arg(self):
        file_path = self.make_path('some_file')
        with self.open(file_path, 'w', newline='') as f:
            f.write('1\r\n2\n3\r4')
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(b'1\r\n2\n3\r4', f.read())

        with self.open(file_path, 'w', newline='\n') as f:
            f.write('1\r\n2\n3\r4')
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(b'1\r\n2\n3\r4', f.read())

        with self.open(file_path, 'w', newline='\r\n') as f:
            f.write('1\r\n2\n3\r4')
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(b'1\r\r\n2\r\n3\r4', f.read())

        with self.open(file_path, 'w', newline='\r') as f:
            f.write('1\r\n2\n3\r4')
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(b'1\r\r2\r3\r4', f.read())

    def test_binary_readline(self):
        file_path = self.make_path('some_file')
        file_contents = b'\x80\n\x80\r\x80\r\n\x80'

        def chunk_line():
            px = 0
            while px < len(file_contents):
                ix = file_contents.find(b'\n', px)
                if ix == -1:
                    yield file_contents[px:]
                    return
                yield file_contents[px:ix + 1]
                px = ix + 1

        chunked_contents = list(chunk_line())
        self.create_file(file_path, contents=file_contents)
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(chunked_contents, list(f))


class RealFileOpenLineEndingTest(FakeFileOpenLineEndingTest):
    def use_real_fs(self):
        return True


class FakeFileOpenLineEndingWithEncodingTest(FakeFileOpenTestBase):
    def setUp(self):
        super(FakeFileOpenLineEndingWithEncodingTest, self).setUp()

    def test_read_standard_newline_mode(self):
        file_path = self.make_path('some_file')
        for contents in (u'раз\nдва', u'раз\r\nдва', u'раз\rдва'):
            self.create_file(file_path, contents=contents, encoding='cyrillic')
            with self.open(file_path, mode='r',
                           encoding='cyrillic') as fake_file:
                self.assertEqual([u'раз\n', u'два'], fake_file.readlines())
            with self.open(file_path, mode='r',
                           encoding='cyrillic') as fake_file:
                self.assertEqual(u'раз\nдва', fake_file.read())

    def test_write_universal_newline_mode(self):
        file_path = self.make_path('some_file')
        with self.open(file_path, 'w', encoding='cyrillic') as f:
            f.write(u'раз\nдва')
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(u'раз'.encode('cyrillic') +
                             self.os.linesep.encode()
                             + u'два'.encode('cyrillic'), f.read())

        with self.open(file_path, 'w', encoding='cyrillic') as f:
            f.write(u'раз\r\nдва')
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(u'раз\r'.encode('cyrillic') +
                             self.os.linesep.encode() +
                             u'два'.encode('cyrillic'), f.read())

    def test_read_with_newline_arg(self):
        file_path = self.make_path('some_file')
        file_contents = u'раз\r\nдва\nтри\rчетыре'
        self.create_file(file_path, contents=file_contents,
                         encoding='cyrillic')
        with self.open(file_path, mode='r', newline='',
                       encoding='cyrillic') as f:
            self.assertEqual(u'раз\r\nдва\nтри\rчетыре', f.read())
        with self.open(file_path, mode='r', newline='\r',
                       encoding='cyrillic') as f:
            self.assertEqual(u'раз\r\nдва\nтри\rчетыре', f.read())
        with self.open(file_path, mode='r', newline='\n',
                       encoding='cyrillic') as f:
            self.assertEqual(u'раз\r\nдва\nтри\rчетыре', f.read())
        with self.open(file_path, mode='r', newline='\r\n',
                       encoding='cyrillic') as f:
            self.assertEqual(u'раз\r\nдва\nтри\rчетыре', f.read())

    def test_readlines_with_newline_arg(self):
        file_path = self.make_path('some_file')
        file_contents = u'раз\r\nдва\nтри\rчетыре'
        self.create_file(file_path, contents=file_contents,
                         encoding='cyrillic')
        with self.open(file_path, mode='r', newline='',
                       encoding='cyrillic') as f:
            self.assertEqual([u'раз\r\n', u'два\n', u'три\r', u'четыре'],
                             f.readlines())
        with self.open(file_path, mode='r', newline='\r',
                       encoding='cyrillic') as f:
            self.assertEqual([u'раз\r', u'\nдва\nтри\r', u'четыре'],
                             f.readlines())
        with self.open(file_path, mode='r', newline='\n',
                       encoding='cyrillic') as f:
            self.assertEqual([u'раз\r\n', u'два\n', u'три\rчетыре'],
                             f.readlines())
        with self.open(file_path, mode='r', newline='\r\n',
                       encoding='cyrillic') as f:
            self.assertEqual([u'раз\r\n', u'два\nтри\rчетыре'],
                             f.readlines())

    def test_write_with_newline_arg(self):
        file_path = self.make_path('some_file')
        with self.open(file_path, 'w', newline='',
                       encoding='cyrillic') as f:
            f.write(u'раз\r\nдва\nтри\rчетыре')
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(u'раз\r\nдва\nтри\rчетыре'.encode('cyrillic'),
                             f.read())

        with self.open(file_path, 'w', newline='\n',
                       encoding='cyrillic') as f:
            f.write('раз\r\nдва\nтри\rчетыре')
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(u'раз\r\nдва\nтри\rчетыре'.encode('cyrillic'),
                             f.read())

        with self.open(file_path, 'w', newline='\r\n',
                       encoding='cyrillic') as f:
            f.write('раз\r\nдва\nтри\rчетыре')
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(u'раз\r\r\nдва\r\nтри\rчетыре'.encode('cyrillic'),
                             f.read())

        with self.open(file_path, 'w', newline='\r',
                       encoding='cyrillic') as f:
            f.write('раз\r\nдва\nтри\rчетыре')
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(u'раз\r\rдва\rтри\rчетыре'.encode('cyrillic'),
                             f.read())


class RealFileOpenLineEndingWithEncodingTest(
        FakeFileOpenLineEndingWithEncodingTest):
    def use_real_fs(self):
        return True


class OpenWithFileDescriptorTest(FakeFileOpenTestBase):
    def test_open_with_file_descriptor(self):
        file_path = self.make_path('this', 'file')
        self.create_file(file_path)
        fd = self.os.open(file_path, os.O_CREAT)
        self.assertEqual(fd, self.open(fd, 'r').fileno())

    def test_closefd_with_file_descriptor(self):
        file_path = self.make_path('this', 'file')
        self.create_file(file_path)
        fd = self.os.open(file_path, os.O_CREAT)
        fh = self.open(fd, 'r', closefd=False)
        fh.close()
        self.assertIsNotNone(self.filesystem.open_files[fd])
        fh = self.open(fd, 'r', closefd=True)
        fh.close()
        self.assertIsNone(self.filesystem.open_files[fd])


class OpenWithRealFileDescriptorTest(FakeFileOpenTestBase):
    def use_real_fs(self):
        return True


class OpenWithFlagsTestBase(FakeFileOpenTestBase):
    def setUp(self):
        super(OpenWithFlagsTestBase, self).setUp()
        self.file_path = self.make_path('some_file')
        self.file_contents = None

    def open_file(self, mode):
        return self.open(self.file_path, mode=mode)

    def open_file_and_seek(self, mode):
        fake_file = self.open(self.file_path, mode=mode)
        fake_file.seek(0, 2)
        return fake_file

    def write_and_reopen_file(self, fake_file, mode='r', encoding=None):
        fake_file.write(self.file_contents)
        fake_file.close()
        args = {'mode': mode}
        if encoding:
            args['encoding'] = encoding
        return self.open(self.file_path, **args)


class OpenWithBinaryFlagsTest(OpenWithFlagsTestBase):
    def setUp(self):
        super(OpenWithBinaryFlagsTest, self).setUp()
        self.file_contents = b'real binary contents: \x1f\x8b'
        self.create_file(self.file_path, contents=self.file_contents)

    def test_read_binary(self):
        with self.open_file('rb') as fake_file:
            self.assertEqual(self.file_contents, fake_file.read())

    def test_write_binary(self):
        with self.open_file_and_seek('wb') as f:
            self.assertEqual(0, f.tell())
            with self.write_and_reopen_file(f, mode='rb') as f1:
                self.assertEqual(self.file_contents, f1.read())
                # Attempt to reopen the file in text mode
                with self.open_file('wb') as f2:
                    with self.write_and_reopen_file(f2, mode='r',
                                                    encoding='ascii') as f3:
                        with self.assertRaises(UnicodeDecodeError):
                            f3.read()

    def test_write_and_read_binary(self):
        with self.open_file_and_seek('w+b') as f:
            self.assertEqual(0, f.tell())
            with self.write_and_reopen_file(f, mode='rb') as f1:
                self.assertEqual(self.file_contents, f1.read())


class RealOpenWithBinaryFlagsTest(OpenWithBinaryFlagsTest):
    def use_real_fs(self):
        return True


class OpenWithTextModeFlagsTest(OpenWithFlagsTestBase):
    def setUp(self):
        super(OpenWithTextModeFlagsTest, self).setUp()
        self.setUpFileSystem()

    def setUpFileSystem(self):
        self.file_path = self.make_path('some_file')
        self.file_contents = b'two\r\nlines'
        self.original_contents = 'two\r\nlines'
        self.converted_contents = 'two\nlines'
        self.create_file(self.file_path, contents=self.file_contents)

    def test_read_text(self):
        """Test that text mode flag is ignored"""
        self.check_windows_only()
        with self.open_file('r') as f:
            self.assertEqual(self.converted_contents, f.read())
        with self.open_file('rt') as f:
            self.assertEqual(self.converted_contents, f.read())

    def test_mixed_text_and_binary_flags(self):
        with self.assertRaises(ValueError):
            self.open_file_and_seek('w+bt')


class RealOpenWithTextModeFlagsTest(OpenWithTextModeFlagsTest):
    def use_real_fs(self):
        return True


class OpenWithInvalidFlagsTest(FakeFileOpenTestBase):
    def test_capital_r(self):
        with self.assertRaises(ValueError):
            self.open('some_file', 'R')

    def test_capital_w(self):
        with self.assertRaises(ValueError):
            self.open('some_file', 'W')

    def test_capital_a(self):
        with self.assertRaises(ValueError):
            self.open('some_file', 'A')

    def test_lower_u(self):
        with self.assertRaises(ValueError):
            self.open('some_file', 'u')

    def test_lower_rw(self):
        with self.assertRaises(ValueError):
            self.open('some_file', 'rw')


class OpenWithInvalidFlagsRealFsTest(OpenWithInvalidFlagsTest):
    def use_real_fs(self):
        return True


class ResolvePathTest(FakeFileOpenTestBase):
    def write_to_file(self, file_name):
        with self.open(file_name, 'w') as fh:
            fh.write('x')

    def test_none_filepath_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.open(None, 'w')

    def test_empty_filepath_raises_io_error(self):
        with self.assertRaises(OSError):
            self.open('', 'w')

    def test_normal_path(self):
        file_path = self.make_path('foo')
        self.write_to_file(file_path)
        self.assertTrue(self.os.path.exists(file_path))

    def test_link_within_same_directory(self):
        self.skip_if_symlink_not_supported()
        final_target = self.make_path('foo', 'baz')
        link_path = self.make_path('foo', 'bar')
        self.create_symlink(link_path, 'baz')
        self.write_to_file(link_path)
        self.assertTrue(self.os.path.exists(final_target))
        self.assertEqual(1, self.os.stat(final_target)[stat.ST_SIZE])

    def test_link_to_sub_directory(self):
        self.skip_if_symlink_not_supported()
        final_target = self.make_path('foo', 'baz', 'bip')
        dir_path = self.make_path('foo', 'baz')
        self.create_dir(dir_path)
        link_path = self.make_path('foo', 'bar')
        target_path = self.os.path.join('baz', 'bip')
        self.create_symlink(link_path, target_path)
        self.write_to_file(link_path)
        self.assertTrue(self.os.path.exists(final_target))
        self.assertEqual(1, self.os.stat(final_target)[stat.ST_SIZE])
        self.assertTrue(self.os.path.exists(dir_path))
        # Make sure that intermediate directory got created.
        self.assertTrue(self.os.stat(dir_path)[stat.ST_MODE] & stat.S_IFDIR)

    def test_link_to_parent_directory(self):
        self.skip_if_symlink_not_supported()
        final_target = self.make_path('baz', 'bip')
        self.create_dir(self.make_path('foo'))
        self.create_dir(self.make_path('baz'))
        link_path = self.make_path('foo', 'bar')
        self.create_symlink(link_path, self.os.path.join('..', 'baz'))
        self.write_to_file(self.make_path('foo', 'bar', 'bip'))
        self.assertTrue(self.os.path.exists(final_target))
        self.assertEqual(1, self.os.stat(final_target)[stat.ST_SIZE])
        self.assertTrue(self.os.path.exists(link_path))

    def test_link_to_absolute_path(self):
        self.skip_if_symlink_not_supported()
        final_target = self.make_path('foo', 'baz', 'bip')
        self.create_dir(self.make_path('foo', 'baz'))
        link_path = self.make_path('foo', 'bar')
        self.create_symlink(link_path, final_target)
        self.write_to_file(link_path)
        self.assertTrue(self.os.path.exists(final_target))

    def test_relative_links_work_after_chdir(self):
        self.skip_if_symlink_not_supported()
        final_target = self.make_path('foo', 'baz', 'bip')
        self.create_dir(self.make_path('foo', 'baz'))
        link_path = self.make_path('foo', 'bar')
        self.create_symlink(link_path, self.os.path.join('.', 'baz', 'bip'))
        if not self.is_windows:
            self.assert_equal_paths(
                final_target, self.os.path.realpath(link_path))

        self.assertTrue(self.os.path.islink(link_path))
        self.os.chdir(self.make_path('foo'))
        self.assert_equal_paths(self.make_path('foo'), self.os.getcwd())
        self.assertTrue(self.os.path.islink('bar'))
        if not self.is_windows:
            self.assert_equal_paths(final_target, self.os.path.realpath('bar'))

        self.write_to_file(link_path)
        self.assertTrue(self.os.path.exists(final_target))

    def test_absolute_links_work_after_chdir(self):
        self.skip_if_symlink_not_supported()
        final_target = self.make_path('foo', 'baz', 'bip')
        self.create_dir(self.make_path('foo', 'baz'))
        link_path = self.make_path('foo', 'bar')
        self.create_symlink(link_path, final_target)
        if not self.is_windows:
            self.assert_equal_paths(
                final_target, self.os.path.realpath(link_path))

        self.assertTrue(self.os.path.islink(link_path))
        self.os.chdir(self.make_path('foo'))
        self.assert_equal_paths(self.make_path('foo'), self.os.getcwd())
        self.assertTrue(self.os.path.islink('bar'))
        if not self.is_windows:
            self.assert_equal_paths(final_target, self.os.path.realpath('bar'))

        self.write_to_file(link_path)
        self.assertTrue(self.os.path.exists(final_target))

    def test_chdir_through_relative_link(self):
        self.check_posix_only()
        dir1_path = self.make_path('x', 'foo')
        dir2_path = self.make_path('x', 'bar')
        self.create_dir(dir1_path)
        self.create_dir(dir2_path)
        link_path = self.make_path('x', 'foo', 'bar')
        self.create_symlink(link_path,
                            self.os.path.join('..', 'bar'))
        self.assert_equal_paths(dir2_path, self.os.path.realpath(link_path))

        self.os.chdir(dir1_path)
        self.assert_equal_paths(dir1_path, self.os.getcwd())
        self.assert_equal_paths(dir2_path, self.os.path.realpath('bar'))

        self.os.chdir('bar')
        self.assert_equal_paths(dir2_path, self.os.getcwd())

    def test_chdir_uses_open_fd_as_path(self):
        self.check_posix_only()
        if self.is_pypy:
            # unclear behavior with PyPi
            self.skip_real_fs()
        self.assert_raises_os_error(
            [errno.ENOTDIR, errno.EBADF], self.os.chdir, 500)
        dir_path = self.make_path('foo', 'bar')
        self.create_dir(dir_path)

        path_des = self.os.open(dir_path, os.O_RDONLY)
        self.os.chdir(path_des)
        self.os.close(path_des)
        self.assert_equal_paths(dir_path, self.os.getcwd())

    def test_read_link_to_link(self):
        # Write into the final link target and read back from a file which will
        # point to that.
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('foo', 'bar')
        self.create_symlink(link_path, 'link')
        self.create_symlink(self.make_path('foo', 'link'), 'baz')
        self.write_to_file(self.make_path('foo', 'baz'))
        fh = self.open(link_path, 'r')
        self.assertEqual('x', fh.read())

    def test_write_link_to_link(self):
        self.skip_if_symlink_not_supported()
        final_target = self.make_path('foo', 'baz')
        link_path = self.make_path('foo', 'bar')
        self.create_symlink(link_path, 'link')
        self.create_symlink(self.make_path('foo', 'link'), 'baz')
        self.write_to_file(link_path)
        self.assertTrue(self.os.path.exists(final_target))

    def test_multiple_links(self):
        self.skip_if_symlink_not_supported()
        self.os.makedirs(self.make_path('a', 'link1', 'c', 'link2'))

        self.create_symlink(self.make_path('a', 'b'), 'link1')

        if not self.is_windows:
            self.assert_equal_paths(self.make_path('a', 'link1'),
                                    self.os.path.realpath(
                                        self.make_path('a', 'b')))
            self.assert_equal_paths(self.make_path('a', 'link1', 'c'),
                                    self.os.path.realpath(
                                        self.make_path('a', 'b', 'c')))

        link_path = self.make_path('a', 'link1', 'c', 'd')
        self.create_symlink(link_path, 'link2')
        self.assertTrue(self.os.path.exists(link_path))
        self.assertTrue(self.os.path.exists(
            self.make_path('a', 'b', 'c', 'd')))

        final_target = self.make_path('a', 'link1', 'c', 'link2', 'e')
        self.assertFalse(self.os.path.exists(final_target))
        self.write_to_file(self.make_path('a', 'b', 'c', 'd', 'e'))
        self.assertTrue(self.os.path.exists(final_target))

    def test_utime_link(self):
        """os.utime() and os.stat() via symbolic link (issue #49)"""
        self.skip_if_symlink_not_supported()
        self.create_dir(self.make_path('foo', 'baz'))
        target_path = self.make_path('foo', 'baz', 'bip')
        self.write_to_file(target_path)
        link_name = self.make_path('foo', 'bar')
        self.create_symlink(link_name, target_path)

        self.os.utime(link_name, (1, 2))
        st = self.os.stat(link_name)
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)
        self.os.utime(link_name, (3, 4))
        st = self.os.stat(link_name)
        self.assertEqual(3, st.st_atime)
        self.assertEqual(4, st.st_mtime)

    def test_too_many_links(self):
        self.check_posix_only()
        link_path = self.make_path('a', 'loop')
        self.create_symlink(link_path, 'loop')
        self.assertFalse(self.os.path.exists(link_path))

    def test_that_drive_letters_are_preserved(self):
        self.check_windows_only()
        self.skip_real_fs()
        self.assertEqual('C:!foo!bar',
                         self.filesystem.resolve_path('C:!foo!!bar'))

    def test_that_unc_paths_are_preserved(self):
        self.check_windows_only()
        self.skip_real_fs()
        self.assertEqual('!!foo!bar!baz',
                         self.filesystem.resolve_path('!!foo!bar!baz!!'))


class RealResolvePathTest(ResolvePathTest):
    def use_real_fs(self):
        return True


if __name__ == '__main__':
    unittest.main()
