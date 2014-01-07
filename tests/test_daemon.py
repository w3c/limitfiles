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

import atexit
import functools
import subprocess
import sys
import tempfile
import time

import limitfiles
import tests.limitfiles_common as lftests

DEV_NULL = open('/dev/null', 'w')
atexit.register(DEV_NULL.close)

class TestLimitFilesDaemon(lftests.LimitFilesTestCase):
    def setUp(self):
        super().setUp()
        self.command = [sys.executable, 'limitfiles.py']

    def tearDown(self):
        if hasattr(self, 'config'):
            self.config.close()
            del self.config
        if hasattr(self, 'daemon'):
            if self.daemon.poll() is None:
                self.daemon.kill()
            if self.daemon.stdout is not None:
                self.daemon.stdout.close()
            del self.daemon
        super().tearDown()

    def write_config(self, **kwargs):
        lines = ['[{}]'.format(kwargs.get('name', "Test Watch")),
                 'directory = {}'.format(kwargs.get('dir_name', self.workdir)),
                 'max = {}'.format(kwargs['high']),
                 'keep = {}'.format(kwargs['low'])]
        if 'match' in kwargs:
            lines.append('match = {}'.format(kwargs['match']))
        self.config = tempfile.NamedTemporaryFile(
            'w', prefix='limitfiles', suffix='.ini', encoding='utf-8')
        self.config.write('\n'.join(lines))
        self.config.flush()

    def run_daemon(self, conf_name=None, args=['-f']):
        if conf_name is None:
            conf_name = self.config.name
        self.daemon = subprocess.Popen(
            self.command + args + ['-c', self.config.name],
            stdin=subprocess.PIPE, stdout=DEV_NULL, stderr=subprocess.STDOUT)
        self.daemon.stdin.close()

    def watch(self, **kwargs):
        self.write_config(**kwargs)
        self.run_daemon()
        
    def wait_for_daemon(func):
        @functools.wraps(func)
        def daemon_waiter(*args, **kwargs):
            timeout = time.time() + 1
            while True:
                try:
                    func(*args, **kwargs)
                except AssertionError:
                    if time.time() > timeout:
                        raise
                    time.sleep(.1)
                else:
                    break
        return daemon_waiter
            
    assertFilesLeft = wait_for_daemon(
        lftests.LimitFilesTestCase.assertFilesLeft)

    @wait_for_daemon
    def assertNoDaemon(self):
        returncode = self.daemon.poll()
        self.assertIsNotNone(returncode)
        self.assertGreater(returncode, 0)

    def assertBadWatch(self, *args, **kwargs):
        self.watch(**kwargs)
        self.assertNoDaemon()
