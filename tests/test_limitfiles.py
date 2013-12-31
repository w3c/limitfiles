#!/usr/bin/env python3
#
# Copyright © 2013 World Wide Web Consortium, (Massachusetts Institute
# of Technology, European Research Consortium for Informatics and
# Mathematics, Keio University, Beihang). All Rights Reserved. This
# work is distributed under the W3C® Software License [1] in the hope
# that it will be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.
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

import limitfiles

class TestLimitFiles(unittest.TestCase):
    def setUp(self):
        self.next_name = 1
        self.workdir = tempfile.mkdtemp(prefix='limitfiles')
        self.limits = limitfiles.LimitManager()
        self.notifier = pyinotify.Notifier(self.limits, timeout=10)

    def tearDown(self):
        self.notifier.stop()
        shutil.rmtree(self.workdir, True)

    def watch(self, **kwargs):
        return self.limits.add_watch(self.workdir, **kwargs)

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

    # Call with one sequence, or arguments to temp_filenames
    def assertFilesLeft(self, arg1, *args):
        if not args:
            expected = arg1
        else:
            expected = list(self.temp_filenames(arg1, *args))
        while self.notifier.check_events():
            self.notifier.read_events()
            self.notifier.process_events()
        actual = sorted(os.listdir(self.workdir), key=int)
        self.assertSequenceEqual(actual, expected)

    def test_count_limit(self):
        self.watch(high=5, low=2)
        self.touch_files(6)
        self.assertFilesLeft(4, 7)

    def test_count_limit_after_files_exist(self):
        self.touch_files(3)
        self.watch(high=5, low=2)
        self.touch_files(3)
        self.assertFilesLeft(4, 7)

    def test_count_limit_on_existing_files(self):
        self.touch_files(6)
        self.watch(high=5, low=2)
        self.assertFilesLeft(4, 7)

    def test_limit_respects_mtime(self):
        self.watch(high=5, low=2)
        self.touch_files(4)
        os.utime(self.workpath(1), (10, 10))
        self.touch_files(2)
        self.assertFilesLeft(['1', '5', '6'])

    def test_limit_respects_deletes(self):
        self.watch(high=5, low=1)
        self.touch_files(4)
        for num in [1, 2]:
            os.unlink(self.workpath(num))
        self.touch_files(2)
        self.assertFilesLeft(3, 7)

    def test_match_limit(self):
        self.watch(high=2, low=1, match='[1-3]')
        self.touch_files(8)
        base_expected = list(self.temp_filenames(4, 9))
        self.assertFilesLeft(['3'] + base_expected)
        self.touch_files(3)
        self.assertFilesLeft(base_expected + ['9', '11'])
