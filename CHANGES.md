# Release Notes 
The release versions are PyPi releases.

## Version 3.0

#### New Features
 * support for path-like objects as arguments in fake `os`
   and `os.path` modules (Python >= 3.6)
 * support for `pathlib` module (Python >= 3.4)
 * support for `os.replace` (Python >= 3.3)
 * `os.access`, `os.chmod`, `os.chown`, `os.stat`, `os.utime`:
   support for `follow_symlinks` argument (Python >= 3.3)
 * support for `os.scandir` (Python >= 3.5)
 * option to not fake modules named `path`
 * `glob.glob`, `glob.iglob`: support for `recursive` argument (Python >= 3.5)
 * support for `glob.iglob`

#### Fixes
 * shutil.move incorrectly moves directories (#145)
 * Missing support for 'x' mode in `open` (Python >= 3.3) (#147)
 * Incorrect exception type in Posix if path ancestor is a file (#139)
 * Exception handling when using `Patcher` with py.test (#135)
 
## Version 2.9

#### New Features
 * `io.open`, `os.open`: support for `encoding` argument
 * `os.makedirs`: support for `exist_ok` argument (Python >= 3.2)
 * support for fake `io.open()`
 * support for mount points
 * support for hard links
 * support for float times (mtime, ctime)
 * Windows support:
     * support for alternative path separator
     * support for case-insensitive filesystems
     * support for drive letters and UNC paths
 * support for filesystem size
 * `shutil.rmtree`: support for `ignore_errors` and `onerror` arguments
 * support for `os.fsync()` and `os.fdatasync()`
 * `os.walk`: Support for `followlinks` argument
 
#### Fixes
 * `shutil` functions like `make_archive` do not work with pyfakefs (#104)
 * file permissions on deletion not correctly handled (#27)
 * `shutil.copy` error with bytes contents (#105)
 * mtime and ctime not updated on content changes
 * Reading from fake block devices doesn't work (#24)

## Version 2.7

#### Infrastructure
 * moved repository from GoogleCode to GitHub, merging 3 projects
 * added continous integration testing with Travis CI
 * added usage documentation in project wiki
 * better support for pypi releases
 
#### New Features
 * added direct unit test support in `fake_filesystem_unittest` 
   (transparently patches all calls to faked implementations)
 * added support for doctests
 * added support for cygwin
 * better support for Python 3

#### Fixes
 * `chown` incorrectly accepts non-integer uid/gid arguments
 * incorrect behavior of `relpath`, `abspath` and `normpath` on Windows.
 * Python 3 `open` in binary mode not working (#32)
 * `mkstemp` returns no valid file descriptor (#19)
 * `open` methods lack `IOError` for prohibited operations (#18)
 * incorrectly resolved relative path (#3)
 * `FakeFileOpen` keyword args do not match the `__builtin__` equivalents (#5)
 * relative paths not supported (#16, #17)

## Older Versions
As there have been three different projects that have been merged together 
for release 2.7, no older release notes are given.
The following versions are still available in PyPi:
 * 1.1, 1.2, 2.0, 2.1, 2.2, 2.3 and 2.4
