#!/usr/bin/env python3
#
# Copyright © 2013-2014 World Wide Web Consortium, (Massachusetts
# Institute of Technology, European Research Consortium for
# Informatics and Mathematics, Keio University, Beihang). All Rights
# Reserved. This work is distributed under the W3C® Software License
# [1] in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.
#
# [1] http://www.w3.org/Consortium/Legal/2002/copyright-software-20021231
#
# Written December 2013 by Brett Smith <brett@w3.org>
# This module depends on the third-party pyinotify module.

import os
import pyinotify
import tempfile
import shutil
import unittest

class LimitFilesTestCase(unittest.TestCase):
    def setUp(self):
        self.next_name = 1
        self.workdir = tempfile.mkdtemp(prefix='limitfiles')

    def tearDown(self):
        shutil.rmtree(self.workdir, True)

    def watch(self, name="Test Watch", dir_name=None, high=None, low=None,
              match=None):
        raise NotImplementedError("LimitFilesTestCase.watch is abstract")

    def temp_filenames(self, *args):
        for num in range(*args):
            yield str(num)

    def workpath(self, filename):
        return os.path.join(self.workdir, str(filename))

    def touch_files(self, count):
        stop = self.next_name + count
        for name in self.temp_filenames(self.next_name, stop):
            path = self.workpath(name)
            stamp = int(name)
            open(path, 'w').close()
            os.utime(path, (stamp, stamp))
        self.next_name = stop

    def filename_set(self, seq):
        return frozenset(str(item) for item in seq)

    def assertFilesLeft(self, must_have, may_have=()):
        must_have = self.filename_set(must_have)
        may_have = self.filename_set(may_have) | must_have
        actual = self.filename_set(os.listdir(self.workdir))
        self.assertSetEqual(must_have, actual & must_have)
        self.assertSetEqual(actual, actual & may_have)

    def assertBadWatch(self, name="Test Watch", dir_name=None, high=None,
                       low=None, match=None):
        raise NotImplementedError(
            "LimitFilesTestCase.assertBadWatch is abstract")

    def test_count_limit(self):
        self.watch(high=5, low=2)
        self.touch_files(6)
        self.assertFilesLeft([5, 6], [4])

    def test_count_limit_after_files_exist(self):
        self.touch_files(3)
        self.watch(high=5, low=2)
        self.touch_files(3)
        self.assertFilesLeft([5, 6], [4])

    def test_count_limit_on_existing_files(self):
        self.touch_files(6)
        self.watch(high=5, low=2)
        self.assertFilesLeft([5, 6])

    def test_existing_files_way_over_limit(self):
        self.touch_files(9)
        self.watch(high=2, low=1)
        self.assertFilesLeft([9], [8])

    def test_limit_respects_mtime(self):
        self.watch(high=5, low=2)
        self.touch_files(4)
        os.utime(self.workpath(1), (10, 10))
        self.touch_files(1)
        self.assertFilesLeft([1, 5])

    def test_limit_respects_deletes(self):
        self.watch(high=5, low=1)
        self.touch_files(4)
        for num in [1, 2]:
            os.unlink(self.workpath(num))
        self.touch_files(2)
        self.assertFilesLeft(range(3, 7))

    def test_match_limit(self):
        self.watch(high=2, low=1, match='[1-3]')
        self.touch_files(8)
        base_expected = list(range(4, 9))
        self.assertFilesLeft([3] + base_expected)
        self.touch_files(3)
        self.assertFilesLeft(base_expected + [9, 11])

    def test_unwritable_files(self):
        self.touch_files(4)
        os.chmod(self.workdir, 0o500)
        self.watch(high=4, low=2)
        self.assertFilesLeft(range(1, 5))
        os.chmod(self.workdir, 0o700)
        self.assertFilesLeft([3, 4], [1, 2])
        self.touch_files(1)
        self.assertFilesLeft([4, 5], [2, 3])

    def test_nonfile_handling(self):
        self.watch(high=4, low=2)
        os.mkdir(self.workpath('d1'))
        os.mkdir(self.workpath('d2'))
        os.mkfifo(self.workpath('f'))
        os.symlink('d1', self.workpath('l'))
        non_files = {'d1', 'd2', 'f', 'l'}
        self.assertFilesLeft(non_files)
        self.touch_files(4)
        self.assertFilesLeft(non_files | {3, 4})

    def test_upsidedown_count_fails(self):
        self.assertBadWatch(high=2, low=4)

    def test_bad_regexp_fails(self):
        self.assertBadWatch(low=1, high=2, match='[')

    def test_nondir_watch_fails(self):
        with tempfile.NamedTemporaryFile(prefix='limitfiles') as tmpfile:
            self.assertBadWatch(dir_name=tmpfile.name, high=2, low=1)

    def test_negative_low_fails(self):
        self.assertBadWatch(low=-2, high=2)

    def test_negative_high_fails(self):
        self.assertBadWatch(low=-2, high=-1)
