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
# Written January 2014 by Brett Smith <brett@w3.org>
# This module depends on the third-party pyinotify module.

from distutils.core import setup

from limitfiles import __version__
URL = "http://www.github.com/w3c/limitfiles"

import os
min_umask = 0o022
old_umask = os.umask(min_umask)
os.umask(old_umask & min_umask)

setup(name="limitfiles",
      version=__version__,
      description="Use inotify to automatically clean files",
      author="Brett Smith",
      author_email="brett@w3.org",
      url=URL,
      download_url=URL,
      py_modules=['limitfiles'],
      data_files=[('/etc/init.d', ['limitfiles'])],
      license="W3C Software Notice and License"
      )
