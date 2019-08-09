# pyfakefs Release Notes
The released versions correspond to PyPi releases.

## Preview of future Version 4.0

_Note:_ pyfakefs 4.0 is planned for release at the end of 2019 or the beginning
of 2020. As pyfakefs 4.0 is a major release, we are giving you advance notice of
the proposed changes so you can be ready.

  * pyfakefs 4.0 drops support for Python 2.7. If you still need
    Python 2.7, you can still use the latest pyfakefs 3.x version. 

## Version 3.7 (as yet unreleased)

### Fixes
  * avoid rare side effect during module iteration in test setup
    (see [#338](../../issues/338))
    
    
## [Version 3.6](https://pypi.python.org/pypi/pyfakefs/3.6)

#### Changes
  * removed unneeded parameter `use_dynamic_patch`

#### New Features
  * support for `src_dir_fd` and `dst_dir_fd` arguments in `os.rename`,
    `os.replace` and `os.link`
  * added possibility to use modules instead of module names for the
    `additional_skip_names` argument (see [#482](../../issues/482))
  * added argument `allow_root_user` to `Patcher` and `UnitTest` to allow
    forcing non-root access (see [#474](../../issues/474))
  * added basic support for `os.pipe` (see [#473](../../issues/473))
  * added support for symlinks in `add_real_directory`
  * added new public method `add_real_symlink`
  
#### Infrastructure
  * added check for correctly installed Python 3 version in Travis.CI
    (see [#487](../../issues/487))

#### Fixes
  * fixed incorrect argument names for some `os` functions
  * fake `DirEntry` now implements `os.PathLike` in Python >= 3.6
    (see [#483](../../issues/483))
  * fixed incorrect argument name for `os.makedirs`
    (see [#481](../../issues/481))
  * avoid pytest warning under Python 2.7 (see [#466](../../issues/466))
  * add __next__ to FakeFileWrapper (see [#485](../../issues/485))

## [Version 3.5.8](https://pypi.python.org/pypi/pyfakefs/3.5.8)

Another bug-fix release that mainly fixes a regression wih Python 2 that has
been introduced in version 3.5.3.

#### Fixes
  * regression: patching build-in `open` under Python 2 broke unit tests
    (see [#469](../../issues/469))
  * fixed writing to file added with `add_real_file`
    (see [#470](../../issues/470))
  * fixed argument name of `FakeIOModule.open` (see [#471](../../pull/471))

#### Infrastructure
  * more changes to run tests using `python setup.py test` under Python 2
    regardless of `pathlib2` presence

## [Version 3.5.7](https://pypi.python.org/pypi/pyfakefs/3.5.7)

This is mostly a bug-fix release.

#### Fixes
  * regression: `pathlib` did not get patched in the presence of `pathlib2`
    (see [#467](../../issues/467))
  * fixed errors if running the PyCharm debugger under Python 2
    (see [#464](../../issues/464))

#### Infrastructure
  * do not run real file system tests by default (fixes deployment problem,
    see [#465](../../issues/465))
  * make tests run if running `python setup.py test` under Python 2

## [Version 3.5.6](https://pypi.python.org/pypi/pyfakefs/3.5.6)

#### Changes
  * import external `pathlib2` and `scandir` packages first if present
    (see [#462](../../issues/462))

## [Version 3.5.5](https://pypi.python.org/pypi/pyfakefs/3.5.5)

#### Fixes
  * removed shebang from test files to avoid packaging warnings
   (see [#461](../../issues/461))

## [Version 3.5.4](https://pypi.python.org/pypi/pyfakefs/3.5.4)

#### New Features
  * added context manager class `Pause` for pause/resume
    (see [#448](../../issues/448))

#### Fixes
  * fixed `AttributeError` shown while displaying `fs` in a failing pytest
    in Python 2
  * fixed permission handling for root user
  * avoid `AttributeError` triggered by modules without `__module__` attribute
    (see [#460](../../issues/460))

## [Version 3.5.3](https://pypi.python.org/pypi/pyfakefs/3.5.3)

This is a minor release to have a version with passing tests for OpenSUSE
packaging.

#### New Features
  * automatically patch file system methods imported as another name like
    `from os.path import exists as my_exists`, including builtin `open`
    and `io.open`

#### Fixes
  * make tests for access time less strict to account for file systems that
    do not change it immediately ([#453](../../issues/453))

## [Version 3.5.2](https://pypi.python.org/pypi/pyfakefs/3.5.2)

This is mostly a bug-fix release.

#### New Features
  * added support for pause/resume of patching the file system modules
    ([#448](../../issues/448))
  * allow to set current group ID, set current user ID and group ID as
    `st_uid` and `st_gid` in new files ([#449](../../issues/449))

#### Fixes
  * fixed using `modules_to_patch` (regression, see [#450](../../issues/450))
  * fixed recursion error on unpickling the fake file system
    ([#445](../../issues/445))
  * allow trailing path in `add_real_directory` ([#446](../../issues/446))

## [Version 3.5](https://pypi.python.org/pypi/pyfakefs/3.5)

#### Changes
  * This version of pyfakefs does not support Python 3.3. Python 3.3 users
    must keep using pyfakefs 3.4.3, or upgrade to a newer Python version.
  * The deprecation warnings for the old API are now switched on by default.
    To switch them off for legacy code, use:
    ```python
    from pyfakefs.deprecator import Deprecator
    Deprecator.show_warnings = False
    ```

#### New Features
  * Improved automatic patching:
    * automatically patch methods of a patched file system module imported like
      `from os.path import exists` ([#443](../../pull/443))
    * a module imported as another name (`import os as _os`) is now correctly
      patched without the need of additional parameters
      ([#434](../../pull/434))
    * automatically patch `Path` if imported like `from pathlib import Path`
      ([#440](../../issues/440))
    * parameter `patch_path` has been removed from `UnitTest` and `Patcher`,
      the correct patching of `path` imports is now done automatically
      ([#429](../../pull/429))
    * `UnitTest` /`Patcher` arguments can now also be set in `setUpPyfakefs()`
      ([#430](../../pull/430))
  * added possibility to set user ID ([#431](../../issues/431))
  * added side_effect option to fake files ([#433](../../pull/433))
  * added some support for extended filesystem attributes under Linux
    ([#423](../../issues/423))
  * handle `contents=None` in `create_file()` as empty contents if size not
    set ([#424](../../issues/424))
  * added `pathlib2` support ([#408](../../issues/408)) ([#422](../../issues/422))
  * added support for null device ([#418](../../issues/418))
  * improved error message for "Bad file descriptor in fake filesystem"
    ([#419](../../issues/419))

#### Fixes
  * fixed pytest when both pyfakefs and future are installed
    ([#441](../../issues/441))
  * file timestamps are now updated more according to the real behavior
    ([#435](../../issues/435))
  * fixed a problem related to patching `shutil` functions using `zipfile`
    ([#427](../../issues/427))

## [Version 3.4.3](https://pypi.python.org/pypi/pyfakefs/3.4.3)

This is mostly a bug fix release, mainly for bugs found by
[@agroce](https://github.com/agroce) using [tstl](https://github.com/agroce/tstl).

#### New Features
  * added support for path-like objects as arguments in `create_file()`,
  `create_dir()`, `create_symlink()`, `add_real_file()` and
  `add_real_directory()` (Python >= 3.6, see [#409](../../issues/409))

#### Infrastructure
  * moved tests into package
  * use README.md in pypi ([#358](../../issues/358))

#### Fixes
  * `tell` after `seek` gave incorrect result in append mode
  ([#363](../../issues/363))
  * a failing pytest did not display the test function correctly
  ([#381](../../issues/381))
  * flushing file contents after truncate was incorrect under some conditions
  ([#412](../../issues/412))
  * `readline()` did not work correctly in binary mode
  ([#411](../../issues/411))
  *  `pathlib.Path.resolve()` behaved incorrectly if the path does not exist
  ([#401](../../issues/401))
  * `closed` attribute was not implemented in fake file ([#380](../../issues/380))
  * `add_real_directory` did not behave correctly for nested paths
  * the following functions did not behave correctly for paths ending with a
  path separator (found by @agroce using [tstl](https://github.com/agroce/tstl)):
    * `os.rename` ([#400](../../issues/400))
    * `os.link` ([#399](../../issues/399), [#407](../../issues/407))
    * `os.rmdir` ([#398](../../issues/398))
    * `os.mkdir`, `os.makedirs` ([#396](../../issues/396))
    * `os.rename` ([#391](../../issues/391), [#395](../../issues/395),
    [#396](../../issues/396), [#389](../../issues/389),
    [#406](../../issues/406))
    * `os.symlink` ([#371](../../issues/371), [#390](../../issues/390))
    * `os.path.isdir` ([#387](../../issues/387))
    * `open` ([#362](../../issues/362), [#369](../../issues/369),
    [#397](../../issues/397))
    * `os.path.lexists`, `os.path.islink` ([#365](../../issues/365),
    [#373](../../issues/373), [#396](../../issues/396))
    * `os.remove` ([#360](../../issues/360), [#377](../../issues/377),
    [#396](../../issues/396))
    * `os.stat` ([#376](../../issues/376))
    * `os.path.isfile` ([#374](../../issues/374))
    * `os.path.getsize` ([#368](../../issues/368))
    * `os.lstat` ([#366](../../issues/366))
    * `os.path.exists` ([#364](../../issues/364))
    * `os.readlink` ([#359](../../issues/359), [#372](../../issues/372),
    [#392](../../issues/392))

## [Version 3.4.1](https://pypi.python.org/pypi/pyfakefs/3.4.1)

This is a bug fix only release.

#### Fixes
  * Missing cleanup after using dynamic patcher let to incorrect behavior of
   `tempfile` after test execution (regression, see [#356](../../issues/356))
  * `add_real_directory` does not work after `chdir` (see [#355](../../issues/355))

## [Version 3.4](https://pypi.python.org/pypi/pyfakefs/3.4)

This version of pyfakefs does not support Python 2.6.  Python 2.6 users
must use pyfakefs 3.3 or earlier.

#### New Features
  * Added possibility to map real files or directories to another path in
  the fake file system (see [#347](../../issues/347))
  * Configuration of `Patcher` and `TestCase`:
    * Possibility to reload modules is now also available in `Patcher`
    * Added possibility to add own fake modules via `modules_to_patch`
    argument (see [#345](../../issues/345))
    * Dynamic loading of modules after setup is now on by default and no more
    considered experimental (see [#340](../../issues/340))
  * Added support for file descriptor path parameter in `os.scandir`
   (Python >= 3.7, Posix only) (see [#346](../../issues/346))
  * Added support to fake out backported `scandir` module ([#332](../../issues/332))
  * `IOError`/`OSError` exception messages in the fake file system now always
  start with the message issued in the real file system in Unix systems (see [#202](../../issues/202))

#### Infrastructure
  * Changed API to be PEP-8 conform ([#186](../../issues/186)). Note: The old
    API is still available.
  * Removed Python 2.6 support ([#293](../../issues/293))
  * Added usage documentation to GitHub Pages
  * Added contributing guide
  * Added flake8 tests to Travis CI

#### Fixes
  * Links in base path in `os.scandir` shall not be resolved ([#350](../../issues/350))
  * Fixed unit tests when run on a computer not having umask set to 0022
  * Correctly handle newline parameter in `open()` for Python 3, added support for universal newline mode in Python 2 ([#339](../../issues/339))
  * Fixed handling of case-changing rename with symlink under MacOS ([#322](../../issues/322))
  * Creating a file with a path ending with path separator did not raise ([#320](../../issues/320))
  * Fixed more problems related to `flush` ([#302](../../issues/302), [#300](../../issues/300))
  * Correctly handle opening files more than once ([#343](../../issues/343))
  * Fake `os.lstat()` crashed with several trailing path separators ([#342](../../issues/342))
  * Fixed handling of path components starting with a drive letter([#337](../../issues/337))
  * Symlinks to absolute paths were incorrectly resolved under Windows ([#341](../../issues/341))
  * Unittest mock didn't work after setUpPyfakefs ([#334](../../issues/334))
  * `os.path.split()` and `os.path.dirname()` gave incorrect results under Windows ([#335](../../issues/335))

## [Version 3.3](https://pypi.python.org/pypi/pyfakefs/3.3)

This is the last release that supports Python 2.6.

#### New Features
  * The OS specific temp directory is now automatically created in `setUp()` (related to [#191](../../issues/191)).
    Note that this may break test code that assumes that the fake file system is completely empty at test start.
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
