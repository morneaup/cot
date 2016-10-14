#!/usr/bin/env python
#
# helper.py - Abstract provider of a non-Python helper program.
#
# February 2015, Glenn F. Matthews
# Copyright (c) 2015-2016 the COT project developers.
# See the COPYRIGHT.txt file at the top-level directory of this distribution
# and at https://github.com/glennmatthews/cot/blob/master/COPYRIGHT.txt.
#
# This file is part of the Common OVF Tool (COT) project.
# It is subject to the license terms in the LICENSE.txt file found in the
# top-level directory of this distribution and at
# https://github.com/glennmatthews/cot/blob/master/LICENSE.txt. No part
# of COT, including this file, may be copied, modified, propagated, or
# distributed except according to the terms contained in the LICENSE.txt file.

"""Common interface for providers of non-Python helper programs.

Provides the ability to install the program if not already present,
and the ability to run the program as well.

**Classes**

.. autosummary::
  :nosignatures:

  HelperNotFoundError
  HelperError
  Helper
  PackageManager

**Attributes**

.. autosummary::
  :nosignatures:

  helpers
  package_managers

**Functions**

.. autosummary::
  :nosignatures:

  check_call
  check_output
"""

import logging

import os
import os.path
import contextlib
import errno
import re
import shutil
import subprocess

try:
    from subprocess import check_output as _check_output
except ImportError:
    # Python 2.6 doesn't have subprocess.check_output.
    # Implement it ourselves:
    def _check_output(args, **kwargs):
        process = subprocess.Popen(args,
                                   stdout=subprocess.PIPE,
                                   **kwargs)
        stdout, _ = process.communicate()
        retcode = process.poll()
        if retcode:
            e = subprocess.CalledProcessError(retcode, " ".join(args))
            e.output = stdout
            raise e
        return stdout

import tarfile
import distutils.spawn
from distutils.version import StrictVersion
import requests

from verboselogs import VerboseLogger

logging.setLoggerClass(VerboseLogger)
logger = logging.getLogger(__name__)

try:
    # Python 3.x
    from tempfile import TemporaryDirectory
except ImportError:
    # Python 2.x
    import tempfile

    @contextlib.contextmanager
    def TemporaryDirectory(suffix='',   # noqa: N802
                           prefix='tmp',
                           dirpath=None):
        """Create a temporary directory and make sure it's deleted later.

        Reimplementation of Python 3's ``tempfile.TemporaryDirectory``.
        """
        tempdir = tempfile.mkdtemp(suffix, prefix, dirpath)
        try:
            yield tempdir
        finally:
            shutil.rmtree(tempdir)


class HelperNotFoundError(OSError):
    """A helper program cannot be located."""


class HelperError(EnvironmentError):
    """A helper program exited with non-zero return code."""


class HelperDict(dict):
    """Dictionary of Helper objects by name.

    Similar to :class:`collections.defaultdict` but takes the key
    as a parameter to the factory.
    """

    def __init__(self, factory, *args, **kwargs):
        """Create the given dictionary with the given factory class/method."""
        super(HelperDict, self).__init__(*args, **kwargs)
        self.factory = factory

    def __missing__(self, key):
        """Method called when accessing a non-existent key.

        Automatically populate the given key with an instance of the factory.
        """
        self[key] = self.factory(key)
        return self[key]


class Helper(object):
    """A provider of a non-Python helper program.

    **Static Methods**

    .. autosummary::
      :nosignatures:

      cp
      download_and_expand_tgz
      mkdir

    **Instance Properties**

    .. autosummary::
      name
      info_uri
      installable
      installed
      path
      version

    **Instance Methods**

    .. autosummary::
      :nosignatures:

      call
      install
    """

    def __init__(self, name,
                 info_uri=None,
                 version_args=None,
                 version_regexp="([0-9.]+)"):
        """Initializer.

        :param name: Name of helper executable
        :param list version_args: Args to pass to the helper to
          get its version. Defaults to ``['--version']`` if unset.
        :param version_regexp: Regexp to get the version number from
          the output of the command.
        """
        self._name = name
        self._info_uri = info_uri
        self._path = None
        self._installed = None
        self._version = None
        if not version_args:
            version_args = ['--version']
        self._version_args = version_args
        self._version_regexp = version_regexp

    def __bool__(self):
        """A helper is True if installed and False if not installed."""
        return self.installed

    # For Python 2.x compatibility:
    __nonzero__ = __bool__

    _provider_packages = {}

    UI = None
    """User interface (if any) available to helpers."""

    @property
    def name(self):
        """Name of the helper program."""
        return self._name

    @property
    def info_uri(self):
        """URI for more information about this helper."""
        return self._info_uri

    @property
    def path(self):
        """Discovered path to the helper."""
        if not self._path:
            logger.verbose("Checking for helper executable %s", self.name)
            self._path = distutils.spawn.find_executable(self.name)
            if self._path:
                logger.verbose("%s is at %s", self.name, self.path)
                self._installed = True
            else:
                logger.verbose("No path to %s found", self.name)
        return self._path

    @property
    def installed(self):
        """Whether this helper program is installed and available to run."""
        if self._installed is None:
            self._installed = (self.path is not None)
        return self._installed

    @property
    def installable(self):
        """Whether COT is capable of installing this program on this system."""
        for pm_name in self._provider_packages:
            if package_managers[pm_name]:
                return True
        return False

    @property
    def version(self):
        """Release version of the associated helper program."""
        if self.installed and not self._version:
            output = self.call(self._version_args, require_success=False)
            match = re.search(self._version_regexp, output)
            if not match:
                raise RuntimeError("Unable to find version number in output:"
                                   "\n{0}".format(output))
            self._version = StrictVersion(match.group(1))
        return self._version

    def call(self, args,
             capture_output=True, **kwargs):
        """Call the helper program with the given arguments.

        :param list args: List of arguments to the helper program.
        :param boolean capture_output: If ``True``, stdout/stderr will be
          redirected to a buffer and returned, instead of being displayed
          to the user.
        :param boolean require_success: if ``True``, an exception will be
          raised if the helper exits with a non-zero status code.
        :param boolean retry_with_sudo: if ``True``, if the helper fails,
          will prepend ``sudo`` and retry one more time before giving up.
        :return: Captured stdout/stderr (if :attr:`capture_output`),
          else ``None``.
        """
        if not self.path:
            if self.UI and not self.UI.confirm(
                    "{0} does not appear to be installed.\nTry to install it?"
                    .format(self.name)):
                raise HelperNotFoundError(
                    1,
                    "Unable to proceed without helper program '{0}'. "
                    "Please install it and/or check your $PATH."
                    .format(self.name))
            self.install()
        args.insert(0, self.name)
        if capture_output:
            return check_output(args, **kwargs)
        else:
            check_call(args, **kwargs)
            return None

    def install(self):
        """Install the helper program.

        :raise: :exc:`NotImplementedError` if not ``installable``
        :raise: :exc:`HelperError` if installation is attempted but fails.

        Subclasses should not override this method but instead should provide
        an appropriate implementation of the :meth:`_install` method.
        """
        if self.installed:
            return
        if not self.installable:
            msg = "Unsure how to install {0}.".format(self.name)
            if self.info_uri:
                msg += "\nRefer to {0} for information".format(self.info_uri)
            raise NotImplementedError(msg)
        logger.info("Installing '%s'...", self.name)
        # Call the subclass implementation
        self._install()
        # Make sure it actually performed as promised
        assert self.path, "after installing, path is {0}".format(self.path)

        logger.info("Successfully installed '%s'", self.name)

    def _install(self):
        """Subclass-specific implementation of installation logic."""
        # Default implementation
        for pm_name, packages in self._provider_packages.items():
            if not package_managers[pm_name]:
                continue
            if isinstance(packages, str):
                packages = [packages]
            for pkg in packages:
                package_managers[pm_name].install_package(pkg)

    @staticmethod
    @contextlib.contextmanager
    def download_and_expand_tgz(url):
        """Context manager for downloading and expanding a .tar.gz file.

        Creates a temporary directory, downloads the specified URL into
        the directory, unzips and untars the file into this directory,
        then yields to the given block. When the block exits, the temporary
        directory and its contents are deleted.

        ::

          with download_and_expand_tgz("http://example.com/foo.tgz") as d:
              # archive contents have been extracted to 'd'
              ...
          # d is automatically cleaned up.

        :param str url: URL of a .tgz or .tar.gz file to download.
        """
        with TemporaryDirectory(prefix="cot_helper") as d:
            logger.debug("Temporary directory is %s", d)
            logger.verbose("Downloading and extracting %s", url)
            response = requests.get(url, stream=True)
            tgz = os.path.join(d, 'helper.tgz')
            with open(tgz, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            del response
            logger.debug("Extracting %s", tgz)
            # the "with tarfile.open()..." construct isn't supported in 2.6
            tarf = tarfile.open(tgz, "r:gz")
            try:
                tarf.extractall(path=d)
            finally:
                tarf.close()
            try:
                yield d
            finally:
                logger.debug("Cleaning up temporary directory %s", d)

    @staticmethod
    def mkdir(directory, permissions=493):    # 493 == 0o755
        """Check whether the given target directory exists, and create if not.

        :param str directory: Directory to check/create.
        :param permissions: Permission mask to set when creating a directory.
           Default is ``0o755``.
        """
        if os.path.isdir(directory):
            # TODO: permissions check, update permissions if needed
            return True
        elif os.path.exists(directory):
            raise RuntimeError("Path {0} exists but is not a directory!"
                               .format(directory))
        try:
            logger.verbose("Creating directory " + directory)
            os.makedirs(directory, permissions)
            return True
        except OSError as e:
            logger.verbose("Directory %s creation failed, trying sudo",
                           directory)
            try:
                check_call(['sudo', 'mkdir', '-p',
                            '--mode=%o' % permissions,
                            directory])
            except HelperError:
                # That failed too - re-raise the original exception
                raise e
            return True

    @staticmethod
    def cp(src, dest):
        """Copy the given src to the given dest, using sudo if needed.

        :param str src: Source path.
        :param str dest: Destination path.
        :return: True
        """
        logger.verbose("Copying %s to %s", src, dest)
        try:
            shutil.copy(src, dest)
        except (OSError, IOError) as e:
            logger.verbose('Installation error, trying sudo.')
            try:
                check_call(['sudo', 'cp', src, dest])
            except HelperError:
                # That failed too - re-raise the original exception
                raise e
        return True


helpers = HelperDict(Helper)
"""Dictionary of concrete Helper subclasses to be populated at load time."""


class PackageManager(Helper):
    """Helper program with additional API method install_package()."""

    def install_package(self, package):
        """Install the requested package if needed.

        :param str package: Name of the package to install.
        """
        raise NotImplementedError("install_package not implemented!")


package_managers = HelperDict(PackageManager)
"""Dictionary of concrete PackageManager subclasses, populated at load time."""


def check_call(args, require_success=True, retry_with_sudo=False, **kwargs):
    """Wrapper for :func:`subprocess.check_call`.

    Unlike :meth:`check_output` below, this does not redirect stdout
    or stderr; all output from the subprocess will be sent to the system
    stdout/stderr as normal.

    :param list args: Command to invoke and its associated args
    :param boolean require_success: If ``False``, do not raise an error
      when the command exits with a return code other than 0
    :param boolean retry_with_sudo: If ``True``, if the command gets
      an exception, prepend ``sudo`` to the command and try again.

    :raise HelperNotFoundError: if the command doesn't exist
      (instead of a :class:`OSError`)
    :raise HelperError: if :attr:`require_success` is not ``False`` and
      the command returns a value other than 0 (instead of a
      :class:`CalledProcessError`).
    :raise OSError: as :func:`subprocess.check_call`.
    """
    cmd = args[0]
    logger.info("Calling '%s'...", " ".join(args))
    try:
        subprocess.check_call(args, **kwargs)
    except OSError as e:
        if retry_with_sudo and (e.errno == errno.EPERM or
                                e.errno == errno.EACCES):
            check_call(['sudo'] + args,
                       require_success=require_success,
                       retry_with_sudo=False,
                       **kwargs)
            return
        if e.errno != errno.ENOENT:
            raise
        raise HelperNotFoundError(e.errno,
                                  "Unable to locate helper program '{0}'. "
                                  "Please check your $PATH.".format(cmd))
    except subprocess.CalledProcessError as e:
        if require_success:
            if retry_with_sudo:
                check_call(['sudo'] + args,
                           require_success=require_success,
                           retry_with_sudo=False,
                           **kwargs)
                return
            raise HelperError(e.returncode,
                              "Helper program '{0}' exited with error {1}"
                              .format(cmd, e.returncode))
    logger.info("...done")
    logger.debug("%s exited successfully", cmd)


def check_output(args, require_success=True, retry_with_sudo=False, **kwargs):
    """Wrapper for :func:`subprocess.check_output`.

    Automatically redirects stderr to stdout, captures both to a buffer,
    and generates a debug message with the stdout contents.

    :param list args: Command to invoke and its associated args
    :param boolean require_success: If ``False``, do not raise an error
      when the command exits with a return code other than 0
    :param boolean retry_with_sudo: If ``True``, if the command gets
      an exception, prepend ``sudo`` to the command and try again.

    :return: Captured stdout/stderr from the command

    :raise HelperNotFoundError: if the command doesn't exist
      (instead of a :class:`OSError`)
    :raise HelperError: if :attr:`require_success` is not ``False`` and
      the command returns a value other than 0 (instead of a
      :class:`CalledProcessError`).
    :raise OSError: as :func:`subprocess.check_call`.
    """
    cmd = args[0]
    logger.info("Calling '%s' and capturing its output...", " ".join(args))
    try:
        stdout = _check_output(args,
                               stderr=subprocess.STDOUT,
                               **kwargs).decode('ascii', 'ignore')
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise
        raise HelperNotFoundError(e.errno,
                                  "Unable to locate helper program '{0}'. "
                                  "Please check your $PATH.".format(cmd))
    except subprocess.CalledProcessError as e:
        stdout = e.output.decode()
        if require_success:
            if retry_with_sudo:
                return check_output(['sudo'] + args,
                                    require_success=require_success,
                                    retry_with_sudo=False,
                                    **kwargs)
            raise HelperError(e.returncode,
                              "Helper program '{0}' exited with error {1}:"
                              "\n> {2}\n{3}".format(cmd, e.returncode,
                                                    " ".join(args),
                                                    stdout))
    logger.info("...done")
    logger.verbose("%s output:\n%s", cmd, stdout)
    return stdout
