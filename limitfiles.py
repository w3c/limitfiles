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

import itertools
import os
import pyinotify

from stat import S_ISREG

class LimitProcessor(pyinotify.ProcessEvent):
    def my_init(self, high, low):
        self.files = {}
        self.max = high
        self.min = low

    def process_IN_CREATE(self, event):
        try:
            stats = os.stat(event.pathname)
        except FileNotFoundError:
            return
        if not S_ISREG(stats.st_mode):
            return
        self.files[event.pathname] = stats.st_mtime
        if len(self.files) >= self.max:
            self.clean_files()

    process_IN_ATTRIB = process_IN_CREATE
    process_IN_MODIFY = process_IN_CREATE
    process_IN_MOVED_TO = process_IN_CREATE

    def process_IN_DELETE(self, event):
        try:
            del self.files[event.pathname]
        except KeyError:
            pass

    process_IN_MOVED_FROM = process_IN_DELETE

    def clean_files(self):
        sorted_names = sorted(self.files.keys(), key=self.files.get)
        for path in itertools.islice(sorted_names, self.max - self.min):
            os.unlink(path)
            del self.files[path]


class LimitManager(pyinotify.WatchManager):
    mask = pyinotify.IN_ONLYDIR
    for method in (name.split('_', 1)[1] for name in dir(LimitProcessor)
                   if name.startswith('process_')):
        mask |= pyinotify.EventsCodes.OP_FLAGS.get(method, 0)

    def add_watch(self, path, **kwargs):
        return super().add_watch(path, self.mask, LimitProcessor(**kwargs))
