#!/usr/bin/env python3
"""limitfiles - Automatic file cleanup using inotify

==========
limitfiles
==========

------------------------------------
Automatic file cleanup using inotify
------------------------------------

limitfiles uses `pyinotify`_ to watch files in a directory, optionally
with names that match a regular expression.  When the number of files
reaches a configured limit, limitfiles deletes the oldest ones (by
mtime) to bring the count down to a configured floor.

.. _pyinotify: https://github.com/seb-m/pyinotify

You can start limitfiles as a script, and it will run as a daemon to
enforce limits defined in a configuration file.  You can also import
limitfiles as a module and work with individual components.

COMMAND-LINE OPTIONS
====================

    -h, --help            Show a brief usage message
    -c CONF_NAME, --config=CONF_NAME
                          Read limit configurations from the named file
                          (default ``/etc/limitfiles.ini``)
    -f, --foreground      Do not daemonize; run in the foreground.
                          limitfiles will not write a pidfile when you
                          use this option.
    -p PIDFILE, --pidfile=PIDFILE
                          Write the daemon's process ID to the named file.
                          This file must not exist when the daemon starts.

COPYRIGHT AND LICENSE
=====================

:Copyright:

  Copyright © 2013-2014 World Wide Web Consortium, (Massachusetts
  Institute of Technology, European Research Consortium for
  Informatics and Mathematics, Keio University, Beihang). All Rights
  Reserved. This work is distributed under the `W3C® Software License`_
  in the hope that it will be useful, but WITHOUT ANY WARRANTY;
  without even the implied warranty of MERCHANTABILITY or FITNESS FOR
  A PARTICULAR PURPOSE.

  .. _W3C® Software License: http://www.w3.org/Consortium/Legal/2002/copyright-software-20021231

:Version: 1.1
:Author: Brett Smith <brett@w3.org>
:Date: 2014-01-16
"""

__version__ = '1.1'

import contextlib
import errno
import itertools
import os
import pyinotify
import re

from stat import S_ISREG

class LimitProcessor(pyinotify.ProcessEvent):
    """Limit the number of files in one directory

    This is a subclass of pyinotify.ProcessEvent that enforces one file
    limit.  It keeps track of file mtimes as they change, and deletes the
    oldest files when too many appear.

    Required keyword arguments:

    `dir_name`
      The directory being watched.

    `high`, `low`
      When the number of matching files reaches the count in `high`, the
      processor deletes files until the number remaining is equal to `low`.

    Optional keyword arguments:

    `match`
      If this is a Python regular expression string, the processor will only
      count and limit files whose names match the regular expression.
    """
    _common_errnos = frozenset({errno.ENOENT, errno.EPERM, errno.EACCES})
    _changed_under_errnos = _common_errnos | {errno.ENOTDIR}

    def my_init(self, dir_name, high, low, match=None):
        self.dir_name = dir_name
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
            self.process_IN_Q_OVERFLOW(skip_errors=self._common_errnos)
        except OSError as error:
            raise ValueError(error)

    def process_IN_Q_OVERFLOW(self, event=None,
                              skip_errors=_changed_under_errnos):
        # Scan the whole directory for matching files and record their mtimes.
        self.files = {}
        listing = []
        with self._skip_os_errors(skip_errors):
            listing = os.listdir(self.dir_name)
        for filename in listing:
            self._record_file(filename)
        self._clean_files()

    @contextlib.contextmanager
    def _skip_os_errors(self, errnos=_common_errnos):
        # If the block raises an OSError, execution will continue if the
        # exception's errno is included in errnos.
        try:
            yield
        except OSError as error:
            if error.errno not in errnos:
                raise

    def _record_file(self, filename):
        # Find and save one file's mtime.
        if not self.match(filename):
            return
        path = os.path.join(self.dir_name, filename)
        with self._skip_os_errors():
            stats = os.stat(path)
            if S_ISREG(stats.st_mode):
                self.files[path] = stats.st_mtime

    def _clean_files(self):
        # Check if the number of files is above the maximum.  If so,
        # delete the oldest until we reach the floor.
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
    """WatchManager to conveniently limit directories

    This is a subclass of pyinotify.WatchManager with a new add_watch method
    that creates a LimitProcessor and installs it with the right event mask.
    """
    mask = pyinotify.IN_ONLYDIR | pyinotify.IN_Q_OVERFLOW
    for method in (name.split('_', 1)[1] for name in dir(LimitProcessor)
                   if name.startswith('process_')):
        mask |= pyinotify.EventsCodes.OP_FLAGS.get(method, 0)

    def add_watch(self, path, **kwargs):
        """Watch one directory with a LimitProcessor

        This method creates a new LimitProcessor with the given arguments,
        and a new inotify watch that uses that LimitProcessor as the event
        handler.

        Pass the name of the directory to watch as the first argument.  Refer
        to the LimitProcessor documentation for other keyword arguments you
        can specify.  Returns the result of WatchManager.add_watch().
        """
        processor = LimitProcessor(dir_name=path, **kwargs)
        return super().add_watch(path, self.mask, processor)


def _parse_options(args):
    # Parse the arguments with an OptionParser and return the result.
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
    print("limitfiles configuration error:", message, file=sys.stderr)
    sys.exit(3)

def _config_warning(sec_name, message):
    print("limitfiles warning: can't watch {}: {}".format(sec_name, message),
          file=sys.stderr)

def _iter_config(config):
    # For each limit in the configuration file, yield the name of the
    # directory and a dictionary of keyword arguments for LimitProcessor.
    for sec_name in config.sections():
        watch_args = {}
        try:
            dir_name = config.get(sec_name, 'directory')
            watch_args['high'] = config.getint(sec_name, 'max')
            watch_args['low'] = config.getint(sec_name, 'keep')
        except configparser.Error as error:
            _config_warning(sec_name, error)
            continue
        try:
            watch_args['match'] = config.get(sec_name, 'match')
        except configparser.NoOptionError:
            pass
        if not os.path.isdir(dir_name):
            _config_warning(sec_name, "{} is not a directory".format(dir_name))
        else:
            yield dir_name, watch_args

def _build_watch_manager(filename):
    # Read the named configuration file, install an inotify watch for each
    # limit in it, and return the new watch manager.
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
    """Run the limitfiles daemon

    This function reads file limit configurations from a file, and runs a
    daemon to enforce them.

    Arguments:

    `args`
      A list of argument strings, like ``sys.argv``.  These can customize
      the daemon's behavior.  Refer to the module documentation for valid
      options.
    """
    global configparser, optparse, sys
    import configparser, optparse, sys
    options, args = _parse_options(args)
    watches = _build_watch_manager(options.conf_name)
    notifier = pyinotify.Notifier(watches)
    notifier.loop(daemonize=options.daemonize, pid_file=options.pidfile)


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
