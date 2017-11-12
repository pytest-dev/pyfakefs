# pyfakefs Release Notes
The release versions are PyPi releases.

## [Version 3.3](https://pypi.python.org/pypi/pyfakefs/3.3)

This is the last release that supports Python 2.6.

#### New Features
  * Added possibility to reload modules and switch on dynamic loading of modules
    after setup (experimental, see [#248](../../issues/248))
  * Added possibility to patch modules that import file system modules under
    another name, for example `import os as '_os` ([#231](../../issues/231))
  * Added support for `dir_fd` argument in several `os` functions
    ([#206](../../issues/206))
  * Added support for open file descriptor as path argument in `os.utime`,
    `os.chmod`, `os.chdir`, `os.chown`, `os.listdir`, `os.stat` and `os.lstat`
    (Python >= 3.3) ([#205](../../issues/205))
  * Added support for basic modes in fake `os.open()` ([#204](../../issues/204))
  * Added fake `os.path.samefile` implementation ([#193](../../issues/193))
  * Added support for `ns` argument in `os.utime()` (Python >= 3.3)
    ([#192](../../issues/192))
  * Added nanosecond time members in `os.stat_result` (Python >= 3.3)
    ([#196](../../issues/196))

#### Infrastructure
  * Added Travis CI tests for MacOSX (Python 2.7 and 3.6)
  * Added Appveyor CI tests for Windows (Python 2.7, 3.3 and 3.6)
  * Added auto-generated documentation for development version on GitHub Pages
  * Removed most of `fake_filesystem_shutil` implementation, relying on the
    patched `os` module instead ([#194](../../issues/194))
  * Removed `fake_tempfile` and `fake_filesystem_glob`, relying on the patched
    `os` module instead ([#189](../../issues/189), [#191](../../issues/191))

#### Fixes
  * Multiple fixes of bugs found using TSTL by @agroce (see about 100 issues
    with the `TSTL` label)
    * several problems with buffer handling in high-level IO functions
    * several problems with multiple handles on the same file
    * several problems with low-level IO functions
    * incorrect exception (`IOError` vs `OSError`) raised in several cases
    * Fake `rename` did not behave like `os.rename` in many cases
    * Symlinks have not been considered or incorrectly handled in several
      functions
    * A nonexistent file that has the same name as the content of the parent
      object was seen as existing
    * Incorrect error handling during directory creation
    * many fixes for OS-specific behavior
  * Also patch modules that are loaded between `__init__()` and `setUp()`
    ([#199](../../issues/199))
  * Creating files in read-only directory was possible ([#203](../../issues/203))

## [Version 3.2](https://pypi.python.org/pypi/pyfakefs/3.2)

#### New Features
  * The `errors` argument is supported for `io.open()` and `os.open()`
  * New methods `add_real_file()`, `add_real_directory()` and `add_real_paths()`
    make real files and directories appear within the fake file system.
    File contents are read from the real file system only as needed ([#170](../../issues/170)).
    See `example_test.py` for a usage example.
  * Deprecated `TestCase.copyRealFile()` in favor of `add_real_file()`.
    `copyRealFile()` remains only for backward compatability.  Also, some
    less-popular argument combinations have been disallowed.
  * Added this file you are reading, `CHANGES.md`, to the release manifest

#### Infrastructure
  * The `mox3` package is no longer a prerequisite--the portion required by pyfakefs
    has been integrated into pyfakefs ([#182](../../issues/182))

#### Fixes
 * Corrected the handling of byte/unicode paths in several functions ([#187](../../issues/187))
 * `FakeShutilModule.rmtree()` failed for directories ending with path separator ([#177](../../issues/177))
 * Case was incorrectly handled for added Windows drives
 * `pathlib.glob()` incorrectly handled case under MacOS ([#167](../../issues/167))
 * tox support was broken ([#163](../../issues/163))
 * On Windows it was not possible to rename a file when only the case of the file
   name changed ([#160](../../issues/160))

## [Version 3.1](https://pypi.python.org/pypi/pyfakefs/3.1)

#### New Features
 * Added helper method `TestCase.copyRealFile()` to copy a file from
   the real file system to the fake file system. This makes it easy to use
   template, data and configuration files in your tests.
 * A pytest plugin is now installed with pyfakefs that exports the
   fake filesystem as pytest fixture `fs`.

#### Fixes
 * Incorrect disk usage calculation if too large file created ([#155](../../issues/155))

## [Version 3.0](https://pypi.python.org/pypi/pyfakefs/3.0)

#### New Features
 * Support for path-like objects as arguments in fake `os`
   and `os.path` modules (Python >= 3.6)
 * Some changes to make pyfakefs work with Python 3.6
 * Added fake `pathlib` module (Python >= 3.4) ([#29](../../issues/29))
 * Support for `os.replace` (Python >= 3.3)
 * `os.access`, `os.chmod`, `os.chown`, `os.stat`, `os.utime`:
   support for `follow_symlinks` argument (Python >= 3.3)
 * Support for `os.scandir` (Python >= 3.5) ([#119](../../issues/119))
 * Option to not fake modules named `path` ([#53](../../issues/53))
 * `glob.glob`, `glob.iglob`: support for `recursive` argument (Python >= 3.5) ([#116](../../issues/116))
 * Support for `glob.iglob` ([#59](../../issues/59))

#### Infrastructure
 * Added [auto-generated documentation](http://jmcgeheeiv.github.io/pyfakefs/)

#### Fixes
 * `shutil.move` incorrectly moves directories ([#145](../../issues/145))
 * Missing support for 'x' mode in `open` (Python >= 3.3) ([#147](../../issues/147))
 * Incorrect exception type in Posix if path ancestor is a file ([#139](../../issues/139))
 * Exception handling when using `Patcher` with py.test ([#135](../../issues/135))
 * Fake `os.listdir` returned sorted instead of unsorted entries

## [Version 2.9](https://pypi.python.org/pypi/pyfakefs/2.9)

#### New Features
 * `io.open`, `os.open`: support for `encoding` argument ([#120](../../issues/120))
 * `os.makedirs`: support for `exist_ok` argument (Python >= 3.2) ([#98](../../issues/98))
 * Support for fake `io.open()` ([#70](../../issues/70))
 * Support for mount points ([#25](../../issues/25))
 * Support for hard links ([#75](../../issues/75))
 * Support for float times (mtime, ctime)
 * Windows support:
     * support for alternative path separator
     * support for case-insensitive filesystems ([#69](../../issues/69))
     * support for drive letters and UNC paths
 * Support for filesystem size ([#86](../../issues/86))
 * `shutil.rmtree`: support for `ignore_errors` and `onerror` arguments ([#72](../../issues/72))
 * Support for `os.fsync()` and `os.fdatasync()` ([#73](../../issues/73))
 * `os.walk`: Support for `followlinks` argument

#### Fixes
 * `shutil` functions like `make_archive` do not work with pyfakefs ([#104](../../issues/104))
 * File permissions on deletion not correctly handled ([#27](../../issues/27))
 * `shutil.copy` error with bytes contents ([#105](../../issues/105))
 * mtime and ctime not updated on content changes

## [Version 2.7](https://pypi.python.org/pypi/pyfakefs/2.7)

#### Infrastructure
 * Moved repository from GoogleCode to GitHub, merging 3 projects
 * Added continuous integration testing with Travis CI
 * Added usage documentation in project wiki
 * Better support for pypi releases

#### New Features
 * Added direct unit test support in `fake_filesystem_unittest`
   (transparently patches all calls to faked implementations)
 * Added support for doctests
 * Added support for cygwin
 * Better support for Python 3

#### Fixes
 * `os.utime` fails to traverse symlinks ([#49](../../issues/49))
 * `chown` incorrectly accepts non-integer uid/gid arguments ([#30](../../issues/30))
 * Reading from fake block devices doesn't work ([#24](../../issues/24))
 * `fake_tempfile` is using `AddOpenFile` incorrectly ([#23](../../issues/23))
 * Incorrect behavior of `relpath`, `abspath` and `normpath` on Windows.
 * Cygwin wasn't treated as Windows ([#37](../../issues/37))
 * Python 3 `open` in binary mode not working ([#32](../../issues/32))
 * `os.remove` doesn't work with relative paths ([#31](../../issues/31))
 * `mkstemp` returns no valid file descriptor ([#19](../../issues/19))
 * `open` methods lack `IOError` for prohibited operations ([#18](../../issues/18))
 * Incorrectly resolved relative path ([#3](../../issues/3))
 * `FakeFileOpen` keyword args do not match the `__builtin__` equivalents ([#5](../../issues/5))
 * Relative paths not supported ([#16](../../issues/16), [#17](../../issues/17)))

## Older Versions
There are no release notes for releases 2.6 and below.  The following versions are still available on PyPi:
 * [1.1](https://pypi.python.org/pypi/pyfakefs/1.1), [1.2](https://pypi.python.org/pypi/pyfakefs/1.2), [2.0](https://pypi.python.org/pypi/pyfakefs/2.0), [2.1](https://pypi.python.org/pypi/pyfakefs/2.1), [2.2](https://pypi.python.org/pypi/pyfakefs/2.2), [2.3](https://pypi.python.org/pypi/pyfakefs/2.3) and [2.4](https://pypi.python.org/pypi/pyfakefs/2.4)
