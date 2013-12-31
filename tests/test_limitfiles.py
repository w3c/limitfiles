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

    def watch(self, *args, **kwargs):
        return self.limits.add_watch(self.workdir, *args, **kwargs)

    def temp_filenames(self, *args):
        for num in range(*args):
            yield str(num)

    def touch_files(self, count):
        stop = self.next_name + count
        for name in self.temp_filenames(self.next_name, stop):
            path = os.path.join(self.workdir, name)
            stamp = int(name)
            open(path, 'w').close()
            os.utime(path, (stamp, stamp))
        self.next_name = stop

    def assertFilesLeft(self, first, last):
        while self.notifier.check_events():
            self.notifier.read_events()
            self.notifier.process_events()
        actual = sorted(os.listdir(self.workdir))
        expected = list(self.temp_filenames(first, last + 1))
        self.assertSequenceEqual(actual, expected)

    def test_count_limit(self):
        self.watch(5, 2)
        self.touch_files(6)
        self.assertFilesLeft(4, 6)
