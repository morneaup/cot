#!/usr/bin/env python
#
# setup.py - installer script for COT package
#
# April 2014, Glenn F. Matthews
#
# See the COPYRIGHT.txt file at the top-level directory of this distribution
# and at https://github.com/glennmatthews/cot/blob/master/COPYRIGHT.txt.
#
# This file is part of the Common OVF Tool (COT) project.
# It is subject to the license terms in the LICENSE.txt file found in the
# top-level directory of this distribution and at
# https://github.com/glennmatthews/cot/blob/master/LICENSE.txt. No part
# of COT, including this file, may be copied, modified, propagated, or
# distributed except according to the terms contained in the LICENSE.txt file.

from setuptools import setup
import versioneer

versioneer.VCS = 'git'
versioneer.versionfile_source = 'COT/_version.py'
versioneer.versionfile_build = versioneer.versionfile_source # TODO
versioneer.tag_prefix = 'v'
versioneer.parentdir_prefix = 'cot-'

import os.path

README_FILE = os.path.join(os.path.dirname(__file__), 'README.md')

setup(
    name='common-ovf-tool',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    author='Glenn Matthews',
    author_email='glenn@e-dad.net',
    packages=['COT'],
    entry_points = {
        'console_scripts': [
            'cot = COT.cli:main',
        ],
    },
    url='https://github.com/glennmatthews/cot',
    license=open('LICENSE.txt').read(),
    description='Common OVF Tool',
    long_description=open(README_FILE).read(),
    test_suite='COT.tests',
)
