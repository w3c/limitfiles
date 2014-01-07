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

import pyinotify
import tempfile

import limitfiles
import tests.limitfiles_common as lftests

class TestLimitFiles(lftests.LimitFilesTestCase):
    def setUp(self):
        super().setUp()
        self.limits = limitfiles.LimitManager()
        self.notifier = pyinotify.Notifier(self.limits, timeout=10)

    def tearDown(self):
        self.notifier.stop()
        super().tearDown()

    def assertFilesLeft(self, *args):
        while self.notifier.check_events():
            self.notifier.read_events()
            self.notifier.process_events()
        super().assertFilesLeft(*args)

    def assertBadWatch(self, *args, **kwargs):
        self.assertRaises(ValueError, self.watch, *args, **kwargs)

    def watch(self, **kwargs):
        dir_name = kwargs.pop('dir_name', self.workdir)
        return self.limits.add_watch(dir_name, **kwargs)
