# pyfakefs Release Notes 
The release versions are PyPi releases.

## Version 3.2 (as yet unreleased)

#### New Features
  * `io.open`, `os.open`: support for `errors` argument
  * Added new methods to `fake_filesystem.FakeFilesystem` that make real files 
    and directories appear within the fake file system: 
    `add_real_file()`, `add_real_directory()` and `add_real_paths()`.
    File contents are read from the real file system only when needed ([#170](../../issues/170)).
  * Added the CHANGES.md release notes to the release manifest

#### Infrastructure
  * `mox3` is no longer required - the relevant part has been integrated into pyfakefs ([#182](../../issues/182))
  
#### Fixes
 * Corrected handling of byte/unicode paths in several functions ([#187](../../issues/187))
 * `FakeShutilModule.rmtree` failed for directory ending with path separator ([#177](../../issues/177))
 * Case incorrectly handled for added Windows drives 
 * `pathlib.glob()` incorrectly handled case under MacOS ([#167](../../issues/167))
 * tox support was broken ([#163](../../issues/163))
 * Rename that only changes case was not possible under Windows ([#160](../../issues/160))
 
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
 * support for path-like objects as arguments in fake `os`
   and `os.path` modules (Python >= 3.6)
 * some changes to make pyfakefs work with Python 3.6 
 * added fake `pathlib` module (Python >= 3.4) ([#29](../../issues/29))
 * support for `os.replace` (Python >= 3.3)
 * `os.access`, `os.chmod`, `os.chown`, `os.stat`, `os.utime`:
   support for `follow_symlinks` argument (Python >= 3.3)
 * support for `os.scandir` (Python >= 3.5) ([#119](../../issues/119))
 * option to not fake modules named `path` ([#53](../../issues/53))
 * `glob.glob`, `glob.iglob`: support for `recursive` argument (Python >= 3.5) ([#116](../../issues/116))
 * support for `glob.iglob` ([#59](../../issues/59))
 
#### Infrastructure
 * added [auto-generated documentation](http://jmcgeheeiv.github.io/pyfakefs/)

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
 * support for fake `io.open()` ([#70](../../issues/70))
 * support for mount points ([#25](../../issues/25))
 * support for hard links ([#75](../../issues/75))
 * support for float times (mtime, ctime)
 * Windows support:
     * support for alternative path separator
     * support for case-insensitive filesystems ([#69](../../issues/69))
     * support for drive letters and UNC paths
 * support for filesystem size ([#86](../../issues/86))
 * `shutil.rmtree`: support for `ignore_errors` and `onerror` arguments ([#72](../../issues/72))
 * support for `os.fsync()` and `os.fdatasync()` ([#73](../../issues/73))
 * `os.walk`: Support for `followlinks` argument
 
#### Fixes
 * `shutil` functions like `make_archive` do not work with pyfakefs ([#104](../../issues/104))
 * file permissions on deletion not correctly handled ([#27](../../issues/27))
 * `shutil.copy` error with bytes contents ([#105](../../issues/105))
 * mtime and ctime not updated on content changes

## [Version 2.7](https://pypi.python.org/pypi/pyfakefs/2.7)

#### Infrastructure
 * moved repository from GoogleCode to GitHub, merging 3 projects
 * added continuous integration testing with Travis CI
 * added usage documentation in project wiki
 * better support for pypi releases
 
#### New Features
 * added direct unit test support in `fake_filesystem_unittest` 
   (transparently patches all calls to faked implementations)
 * added support for doctests
 * added support for cygwin
 * better support for Python 3

#### Fixes
 * `os.utime` fails to traverse symlinks ([#49](../../issues/49))
 * `chown` incorrectly accepts non-integer uid/gid arguments ([#30](../../issues/30))
 * Reading from fake block devices doesn't work ([#24](../../issues/24))
 * `fake_tempfile` is using `AddOpenFile` incorrectly ([#23](../../issues/23))
 * incorrect behavior of `relpath`, `abspath` and `normpath` on Windows.
 * cygwin wasn't treated as Windows ([#37](../../issues/37))
 * Python 3 `open` in binary mode not working ([#32](../../issues/32))
 * `os.remove` doesn't work with relative paths ([#31](../../issues/31))
 * `mkstemp` returns no valid file descriptor ([#19](../../issues/19))
 * `open` methods lack `IOError` for prohibited operations ([#18](../../issues/18))
 * incorrectly resolved relative path ([#3](../../issues/3))
 * `FakeFileOpen` keyword args do not match the `__builtin__` equivalents ([#5](../../issues/5))
 * relative paths not supported ([#16](../../issues/16), [#17](../../issues/17)))

## Older Versions
As there have been three different projects that have been merged together 
for release 2.7, no older release notes are given.
The following versions are still available in PyPi:
 * [1.1](https://pypi.python.org/pypi/pyfakefs/1.1), [1.2](https://pypi.python.org/pypi/pyfakefs/1.2), [2.0](https://pypi.python.org/pypi/pyfakefs/2.0), [2.1](https://pypi.python.org/pypi/pyfakefs/2.1), [2.2](https://pypi.python.org/pypi/pyfakefs/2.2), [2.3](https://pypi.python.org/pypi/pyfakefs/2.3) and [2.4](https://pypi.python.org/pypi/pyfakefs/2.4)
