# Licensed under the Apache License: http://www.apache.org/licenses/LICENSE-2.0
# For details: https://github.com/nedbat/coveragepy/blob/master/NOTICE.txt

"""
Test class mixins

Some of these are transitional while working toward pure-pytest style.
"""

import os
import os.path
import shutil
import sys

import pytest

from coverage.backward import importlib

from tests.helpers import change_dir, make_file, remove_files


class PytestBase(object):
    """A base class to connect to pytest in a test class hierarchy."""

    @pytest.fixture(autouse=True)
    def connect_to_pytest(self, request, monkeypatch):
        """Captures pytest facilities for use by other test helpers."""
        # pylint: disable=attribute-defined-outside-init
        self._pytest_request = request
        self._monkeypatch = monkeypatch
        self.setup_test()

    # Can't call this setUp or setup because pytest sniffs out unittest and
    # nosetest special names, and does things with them.
    # https://github.com/pytest-dev/pytest/issues/8424
    def setup_test(self):
        """Per-test initialization. Override this as you wish."""
        pass

    def addCleanup(self, fn, *args):
        """Like unittest's addCleanup: code to call when the test is done."""
        self._pytest_request.addfinalizer(lambda: fn(*args))

    def set_environ(self, name, value):
        """Set an environment variable `name` to be `value`."""
        self._monkeypatch.setenv(name, value)

    def del_environ(self, name):
        """Delete an environment variable, unless we set it."""
        self._monkeypatch.delenv(name, raising=False)


class TempDirMixin(object):
    """Provides temp dir and data file helpers for tests."""

    # Our own setting: most of these tests run in their own temp directory.
    # Set this to False in your subclass if you don't want a temp directory
    # created.
    run_in_temp_dir = True

    @pytest.fixture(autouse=True)
    def _temp_dir(self, tmpdir_factory):
        """Create a temp dir for the tests, if they want it."""
        if self.run_in_temp_dir:
            tmpdir = tmpdir_factory.mktemp("")
            self.temp_dir = str(tmpdir)
            with change_dir(self.temp_dir):
                # Modules should be importable from this temp directory.  We don't
                # use '' because we make lots of different temp directories and
                # nose's caching importer can get confused.  The full path prevents
                # problems.
                sys.path.insert(0, os.getcwd())

                yield None
        else:
            yield None

    def make_file(self, filename, text="", bytes=b"", newline=None):
        """Make a file. See `tests.helpers.make_file`"""
        # pylint: disable=redefined-builtin     # bytes
        assert self.run_in_temp_dir, "Only use make_file when running in a temp dir"
        return make_file(filename, text, bytes, newline)


class SysPathModulesMixin:
    """Auto-restore sys.path and the imported modules at the end of each test."""

    @pytest.fixture(autouse=True)
    def _save_sys_path(self):
        """Restore sys.path at the end of each test."""
        old_syspath = sys.path[:]
        try:
            yield
        finally:
            sys.path = old_syspath

    @pytest.fixture(autouse=True)
    def _module_saving(self):
        """Remove modules we imported during the test."""
        self._old_modules = list(sys.modules)
        try:
            yield
        finally:
            self._cleanup_modules()

    def _cleanup_modules(self):
        """Remove any new modules imported since our construction.

        This lets us import the same source files for more than one test, or
        if called explicitly, within one test.

        """
        for m in [m for m in sys.modules if m not in self._old_modules]:
            del sys.modules[m]

    def clean_local_file_imports(self):
        """Clean up the results of calls to `import_local_file`.

        Use this if you need to `import_local_file` the same file twice in
        one test.

        """
        # So that we can re-import files, clean them out first.
        self._cleanup_modules()

        # Also have to clean out the .pyc file, since the timestamp
        # resolution is only one second, a changed file might not be
        # picked up.
        remove_files("*.pyc", "*$py.class")
        if os.path.exists("__pycache__"):
            shutil.rmtree("__pycache__")

        if importlib and hasattr(importlib, "invalidate_caches"):
            importlib.invalidate_caches()


class StdStreamCapturingMixin:
    """
    Adapter from the pytest capsys fixture to more convenient methods.

    This doesn't also output to the real stdout, so we probably want to move
    to "real" capsys when we can use fixtures in test methods.

    Once you've used one of these methods, the capturing is reset, so another
    invocation will only return the delta.

    """
    @pytest.fixture(autouse=True)
    def _capcapsys(self, capsys):
        """Grab the fixture so our methods can use it."""
        self.capsys = capsys

    def stdouterr(self):
        """Returns (out, err), two strings for stdout and stderr."""
        return self.capsys.readouterr()

    def stdout(self):
        """Returns a string, the captured stdout."""
        return self.capsys.readouterr().out

    def stderr(self):
        """Returns a string, the captured stderr."""
        return self.capsys.readouterr().err
