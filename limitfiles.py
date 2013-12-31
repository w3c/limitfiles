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
    def my_init(self):
        self.limits = {}

    def register_limit(self, limiter):
        self.limits[limiter.dir_name] = limiter

    def deregister_limit(self, dir_name):
        del self.limits[dir_name]

    def process_IN_DELETE(self, event):
        self.limits[event.path].file_gone(event.pathname)

    process_IN_MOVED_FROM = process_IN_DELETE

    def process_IN_CREATE(self, event):
        self.limits[event.path].file_touched(event.pathname)

    process_IN_ATTRIB = process_IN_CREATE
    process_IN_MODIFY = process_IN_CREATE
    process_IN_MOVED_TO = process_IN_CREATE


class FileLimiter(object):
    # understands limit semantics and enforces the policy
    def __init__(self, dir_name, hi_count, lo_count):
        self.dir_name = dir_name
        self.files = {}
        self.max = hi_count
        self.min = lo_count

    def file_touched(self, path):
        try:
            stats = os.stat(path)
        except FileNotFoundError:
            return
        if not S_ISREG(stats.st_mode):
            return
        self.files[path] = stats.st_mtime
        if len(self.files) >= self.max:
            self.clean_files()

    def file_gone(self, path):
        try:
            del self.files[path]
        except KeyError:
            pass

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

    def __init__(self, *args, **kwargs):
        self.processor = LimitProcessor()
        super().__init__(*args, **kwargs)

    def add_watch(self, path, *args, **kwargs):
        self.processor.register_limit(FileLimiter(path, *args, **kwargs))
        return super().add_watch(path, self.mask, self.processor)

    def del_watch(self, wd):
        self.processor.deregister_limit(self.get_path(wd))
        return super().del_watch(wd)
