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

VERSION="1.0"

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
        if low < 0:
            raise ValueError("low {} must be >= 0".format(low))
        elif high < 0:
            raise ValueError("high {} must be >= 0".format(high))
        elif self.delete_threshold < 0:
            raise ValueError("high {} must be above low {}".format(high, low))
        elif match is None:
            self.match = lambda name: True
        else:
            try:
                self.match = re.compile(match).search
            except re.error as error:
                raise ValueError("bad match regexp {!r}: {}".
                                 format(match, error))
        try:
            with self._skip_os_errors():
                listing = os.listdir(dir_name)
        except OSError as error:
            raise ValueError(error)
        for filename in listing:
            self._record_file(filename)
        self._clean_files()

    @contextlib.contextmanager
    def _skip_os_errors(self, errnos=frozenset({errno.ENOENT, errno.EPERM,
                                                errno.EACCES})):
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
            with self._skip_os_errors():
                os.unlink(path)
                del self.files[path]
                deletes_left -= 1
        # Check how many files are left.  If there are still enough to trigger
        # cleaning, that means the OS won't let us enforce the limit.  Modify
        # the limit to compensate.
        deletes_left = len(self.files) - self.min
        if deletes_left >= self.delete_threshold:
            self.delete_threshold = deletes_left + 1

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


def _parse_options(args):
    import optparse
    parser = optparse.OptionParser(usage="%prog [options]")
    parser.add_option('-c', '--config',
                      dest='conf_name', default='/etc/limitfiles.ini',
                      help="use this configuration file")
    parser.add_option('-f', '--foreground',
                      dest='daemonize', action='store_false', default=True,
                      help="run in the foreground")
    parser.add_option('-p', '--pidfile',
                      dest='pidfile', default=False,
                      help="write PID to this file")
    return parser.parse_args(args)

def _config_error(message):
    print("Configuration error:", message, file=sys.stderr)
    sys.exit(3)

def _config_warning(sec_name, message):
    print("Warning: can't watch {}: {}".format(sec_name, message),
          file=sys.stderr)

def _iter_config(config):
    for sec_name in config.sections():
        watch_args = {}
        try:
            dir_name = config.get(sec_name, 'directory')
            watch_args['high'] = config.getint(sec_name, 'max')
            watch_args['low'] = config.getint(sec_name, 'keep')
        except configparser.Error as error:
            _config_warning(sec_name, error)
            continue
        watch_args['match'] = config[sec_name].get('match')
        if not os.path.isdir(dir_name):
            _config_warning(sec_name, "{} is not a directory".format(dir_name))
        else:
            yield dir_name, watch_args

def _build_watch_manager(filename):
    import configparser
    config = configparser.SafeConfigParser()
    if not config.read(filename):
        _config_error("Could not parse {}".format(filename))
    watch_manager = LimitManager()
    success = False
    for dir_name, watch_args in _iter_config(config):
        try:
            success = watch_manager.add_watch(dir_name, **watch_args) or success
        except ValueError as error:
            _config_warning(dir_name, error)
    if not success:
        _config_error("No valid sections")
    return watch_manager

def main(args):
    options, args = _parse_options(args)
    watches = _build_watch_manager(options.conf_name)
    notifier = pyinotify.Notifier(watches)
    notifier.loop(daemonize=options.daemonize, pid_file=options.pidfile)


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
