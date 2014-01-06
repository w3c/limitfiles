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

import contextlib
import errno
import itertools
import os
import pyinotify
import re

from stat import S_ISREG

class LimitProcessor(pyinotify.ProcessEvent):
    def my_init(self, dir_name, high, low, match=None):
        self.dir_name = dir_name
        self.files = {}
        self.min = low
        self.delete_threshold = high - low
        if self.delete_threshold < 0:
            raise ValueError("high {} must be above low {}".format(high, low))
        elif match is None:
            self.match = lambda name: True
        else:
            try:
                self.match = re.compile(match).search
            except re.error as error:
                raise ValueError("bad match regexp {!r}: {}".
                                 format(match, error))
        for filename in os.listdir(dir_name):
            self._record_file(filename)
        self._clean_files()

    @contextlib.contextmanager
    def _skip_os_errors(self, errnos=frozenset({errno.ENOENT, errno.EPERM})):
        try:
            yield
        except OSError as error:
            if error.errno not in errnos:
                raise

    def _record_file(self, filename):
        if not self.match(filename):
            return
        path = os.path.join(self.dir_name, filename)
        with self._skip_os_errors():
            stats = os.stat(path)
            if S_ISREG(stats.st_mode):
                self.files[path] = stats.st_mtime

    def _clean_files(self):
        deletes_left = len(self.files) - self.min
        if deletes_left < self.delete_threshold:
            return
        sorted_names = sorted(self.files.keys(), key=self.files.get)
        for path in itertools.takewhile(lambda x: deletes_left > 0,
                                        sorted_names):
            del self.files[path]
            with self._skip_os_errors():
                os.unlink(path)
                deletes_left -= 1

    def process_IN_CREATE(self, event):
        self._record_file(event.name)
        self._clean_files()

    process_IN_ATTRIB = process_IN_CREATE
    process_IN_MODIFY = process_IN_CREATE
    process_IN_MOVED_TO = process_IN_CREATE

    def process_IN_DELETE(self, event):
        try:
            del self.files[event.pathname]
        except KeyError:
            pass

    process_IN_MOVED_FROM = process_IN_DELETE


class LimitManager(pyinotify.WatchManager):
    mask = pyinotify.IN_ONLYDIR
    for method in (name.split('_', 1)[1] for name in dir(LimitProcessor)
                   if name.startswith('process_')):
        mask |= pyinotify.EventsCodes.OP_FLAGS.get(method, 0)

    def add_watch(self, path, **kwargs):
        processor = LimitProcessor(dir_name=path, **kwargs)
        return super().add_watch(path, self.mask, processor)
