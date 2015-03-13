#!/usr/bin/env python
#
# setup.py - installer script for COT package
#
# April 2014, Glenn F. Matthews
# Copyright (c) 2014-2015 the COT project developers.
# See the COPYRIGHT.txt file at the top-level directory of this distribution
# and at https://github.com/glennmatthews/cot/blob/master/COPYRIGHT.txt.
#
# This file is part of the Common OVF Tool (COT) project.
# It is subject to the license terms in the LICENSE.txt file found in the
# top-level directory of this distribution and at
# https://github.com/glennmatthews/cot/blob/master/LICENSE.txt. No part
# of COT, including this file, may be copied, modified, propagated, or
# distributed except according to the terms contained in the LICENSE.txt file.

# Install setuptools automatically if not already present
try:
    from setuptools import setup
except ImportError:
    import ez_setup
    ez_setup.use_setuptools()
    from setuptools import setup

import os.path
import re
import shutil
import sys
from setuptools import Command

import versioneer

versioneer.VCS = 'git'
versioneer.versionfile_source = 'COT/_version.py'
versioneer.versionfile_build = versioneer.versionfile_source    # TODO
versioneer.tag_prefix = 'v'
versioneer.parentdir_prefix = 'cot-'

README_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'README.rst')

install_requires = [
    'argparse',
    'colorlog>=2.5.0',
    'requests>=2.5.1',
    'verboselogs>=1.0',
]
# shutil.get_terminal_size is standard in 3.3 and later only.
if sys.version_info < (3, 3):
    install_requires.append('backports.shutil_get_terminal_size')

setup_requires = ['sphinx>1.2.3']
tests_require = install_requires + ['unittest2']

cmd_class = versioneer.get_cmdclass()


def regenerate_usage_contents():
    """Get CLI usage strings for all submodules and write them to file."""
    from COT.cli import CLI
    cli = CLI()
    print("Getting top-level help for 'cot'...")
    help = cli.parser.format_help()
    help_text_to_rst(help, "cot")

    for subcommand in ["add-disk",
                       "add-file",
                       "deploy",
                       "edit-hardware",
                       "edit-product",
                       "edit-properties",
                       "info",
                       "inject-config",
                       "install-helpers"]:
        print("Getting help for 'cot {0}'...".format(subcommand))
        help = cli.subparser_lookup[subcommand].format_help()
        assert help, "help is empty!"

        print("Converting help string to reStructuredText...")
        help_text_to_rst(help, subcommand)

    print("Done updating help rst files")


def help_text_to_rst(help, label):
    """Convert CLI usage string from plaintext to RST and write to file."""
    dirpath = os.path.join(os.path.dirname(__file__),
                           "docs", "_autogenerated", label)
    if os.path.exists(dirpath):
        shutil.rmtree(dirpath)
    os.makedirs(dirpath)

    synopsis_lines = []
    description_lines = []
    options_lines = []
    examples_lines = []
    in_synopsis = False
    in_description = False
    in_options = False
    in_examples = False

    for line in help.splitlines():
        if re.match("^usage:", line):
            synopsis_lines.append("Synopsis")
            synopsis_lines.append("--------")
            synopsis_lines.append("::")
            synopsis_lines.append("")
            in_synopsis = True
            continue
        elif in_synopsis and not re.match("^  ", line):
            description_lines.append("Description")
            description_lines.append("-----------")
            in_synopsis = False
            in_description = True
        elif in_description and re.match("^Copyright", line):
            # Special case for top-level 'cot' CLI
            description_lines.append("")
            continue
        elif in_description and re.match("^\S.*:$", line):
            options_lines.append("Options")
            options_lines.append("-------")
            options_lines.append("")
            if not re.match("(optional|positional) arguments", line):
                # Options subsection - strip trailing ':'
                section = line.rstrip()[:-1].capitalize()
                options_lines.append(section)
                options_lines.append("*" * len(section))
            in_description = False
            in_options = True
            continue
        elif in_options and re.match("^Example", line):
            # Entering the (optional) examples epilog
            examples_lines.append("Examples")
            examples_lines.append("--------")
            examples_lines.append("")
            in_options = False
            in_examples = True
            continue
        elif in_options and re.match("^\S", line):
            if not re.match("(optional|positional) arguments", line):
                # Options subsection - strip trailing ':'
                section = line.rstrip()[:-1].capitalize()
                options_lines.append(section)
                options_lines.append("*" * len(section))
            continue
        elif in_options and re.match("^  <command>", line):
            # Special case for top-level 'cot' CLI
            continue
        elif in_options and re.match("^   ? ?\S", line):
            # New argument
            # Do we have any trailing text?
            match = re.match("^   ? ?(.*\S)  +(\S.*)", line)
            if match:
                line = match.group(1).strip()
                desc_line = "  " + (match.group(2).strip())
            else:
                line = line.strip()
                desc_line = None

            # RST is picky about what an option's values look like,
            # so we have to do some cleanup of the argparse presentation:

            # RST dislikes multi-char args with one dash like '-ds' or '-vv'.
            # All of the ones COT has are synonyms for 'proper' args, so we'll
            # just omit these synonyms from the docs.
            line = re.sub(r" -[a-z][a-z]+( \S+)?,?", "", line)

            # --type {e1000,virtio}   ---->   --type <e1000,virtio>
            line = re.sub(r"(-+\S+) {([^}]+)}", r"\1 <\2>", line)

            # --names NAME1 [NAME2 ...] ---->  --names <NAME1...>
            line = re.sub(r"(-+\S+) ([^,]+) \[[^,]+\]",
                          r"\1 <\2...>", line)
            if desc_line:
                options_lines.append(line)
                line = desc_line
        elif in_options and re.match("^        ", line):
            # Description of an option - keep it under the option_list
            line = "  " + line.strip()
        elif in_examples and re.match("^    ", line):
            # Beginning of an example - mark as a literal
            if not re.match("^    ", examples_lines[-1]):
                examples_lines.append("::")
                examples_lines.append("")
        elif in_examples and re.match("^  \S", line):
            # Description of an example - exit any literal block
            if re.match("^    ", examples_lines[-1]):
                examples_lines.append("")
            line = line.strip()
        else:
            pass

        if line.rstrip():
            line = line.rstrip()
        if in_synopsis:
            synopsis_lines.append(line)
        elif in_description:
            description_lines.append(line)
        elif in_options:
            options_lines.append(line)
        elif in_examples:
            examples_lines.append(line)
        else:
            raise RuntimeError("Not sure what to do with line:\n{0}"
                               .format(line))

    output = {
        'synopsis': "\n".join(synopsis_lines),
        'description': "\n".join(description_lines),
        'options': "\n".join(options_lines),
        'examples': "\n".join(examples_lines)
    }

    for key, value in output.items():
        filepath = os.path.join(dirpath, "{0}.txt".format(key))
        print("Writing to {0}".format(filepath))
        with open(filepath, 'w') as f:
            f.write(value)


class custom_build_docs_autogen(Command):

    description = "Build autogenerated documentation for COT"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        regenerate_usage_contents()


class custom_install_man(Command):
    description = "Install man pages for COT"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        src = os.path.join(os.path.dirname(__file__), 'build', 'sphinx', 'man')
        if not os.path.exists(src):
            raise RuntimeError("need to run 'setup.py build_sphinx -b man'")
        dest = "/usr/share/man/man8"
        for f in os.listdir(src):
            # Which man section does this belong in?
            section = os.path.splitext(f)[1][1:]
            dest = "/usr/share/man/man{0}/".format(section)
            if not os.path.exists(dest):
                os.makedirs(dest)
            print("Copying {0} to {1}".format(f, dest))
            shutil.copy(os.path.join(src, f), dest)

cmd_class['build_docs_autogen'] = custom_build_docs_autogen
cmd_class['install_man'] = custom_install_man

setup(
    name='cot',
    version=versioneer.get_version(),
    cmdclass=cmd_class,
    author='Glenn Matthews',
    author_email='glenn@e-dad.net',
    packages=['COT', 'COT.helpers'],
    entry_points={
        'console_scripts': [
            'cot = COT.cli:main',
        ],
    },
    url='https://github.com/glennmatthews/cot',
    license='MIT',
    description='Common OVF Tool',
    long_description=open(README_FILE).read(),
    setup_requires=setup_requires,
    test_suite='unittest2.collector',
    tests_require=tests_require,
    install_requires=install_requires,
    classifiers=[
        # Project status
        'Development Status :: 5 - Production/Stable',
        # Target audience
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Emulators',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Software Distribution',
        'Topic :: System :: Systems Administration',
        # Licensing
        'License :: OSI Approved :: MIT License',
        # Environment
        'Environment :: Console',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX :: Linux',
        # Supported versions
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    keywords='virtualization ovf ova esxi vmware vcenter',
)
