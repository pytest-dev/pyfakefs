# pyfakefs Release Notes
The released versions correspond to PyPI releases.

## [Version 5.0.0](https://pypi.python.org/pypi/pyfakefs/5.0.0) (2022-10-09)
New version after the transfer to `pytest-dev`.

### Changes
* the old-style API deprecated since version 3.4 has now been removed
* the method `copyRealFile` deprecated since version 3.2 has been removed - 
  use `add_real_file` instead

### Infrastructure
* transferred the repository to the `pytest-dev` organization
* renamed the `master` branch to `main`
* added automatic PyPI release workflow
* move documentation from GitHub Pages to Read the Docs 

### New Features
* added some support for `st_blocks` in stat result
  (see [#722](../../issues/722))

### Fixes
* fixed handling of `O_TMPFILE` in `os.open` (caused handling of 
  `O_DIRECTORY` as `O_TMPFILE`) (see [#723](../../issues/723))
* fixed handling of read permissions (see [#719](../../issues/719))

## [Version 4.7.0](https://pypi.python.org/pypi/pyfakefs/4.7.0) (2022-09-18)
Changed handling of nested fixtures and bug fixes.

### Changes
* `fs` fixtures cannot be nested; any nested `fs` fixture (for example 
  inside an `fs_session` or `fs_module` fixture) will just reference the outer
  fixture (the behavior had been unexpected before)

### Fixes
* reverted a performance optimization introduced in version 3.3.0 that
  caused hanging tests with installed torch (see [#693](../../issues/693))
* do not use the build-in opener in `pathlib` as it may cause problems
  (see [#697](../../issues/697))
* add support for path-like objects in `shutil.disk_usage`
  (see [#699](../../issues/699))
* do not advertise support for Python 3.6 in `setup.py`
  (see [#707](../../issues/707))
* return the expected type from `fcntl.ioctl` and `fcntl.fcntl` calls if `arg`
  is of type `byte`; the call itself does nothing as before 
* do not skip filesystem modules by name to allow using own modules with 
  the same name (see [#707](../../issues/707))
* add missing support for `os.renames` (see [#714](../../issues/714))

## [Version 4.6.3](https://pypi.python.org/pypi/pyfakefs/4.6.3) (2022-07-20)
Another patch release that fixes a regression in version 4.6.

### Changes
* automatically reset filesystem on changing `is_windows_fs` or `is_macos`
  (see [#692](../../issues/692)) - ensures better upwards compatibility in
  most cases

  :warning: Make sure you write to the filesystem _after_ you change  
  `is_windows_fs` or `is_macos`, otherwise the changes will be lost.

### Fixes
* fixed regression: `os.path.exists` returned `True` for any root drive path under Windows

## [Version 4.6.2](https://pypi.python.org/pypi/pyfakefs/4.6.2) (2022-07-14)
Patch release that fixes an error in the previous patch.

### Fixes
* fixed support for `opener` introduced in previous patch release 
  (see [#689](../../issues/689))

## [Version 4.6.1](https://pypi.python.org/pypi/pyfakefs/4.6.1) (2022-07-13)
Fixes incompatibility with Python 3.11 beta 4.

_Note_: Python 3.11 is only supported in the current beta 4 version, problems
with later beta or rc versions are still possible. We will try to fix such 
problems in short order should they appear.

### Fixes
* added support for `opener` argument in `open`, which is used in `tempfile`
  in Python 3.11 since beta 4 (see [#686](../../issues/686))

### Infrastructure
* make sure tests run without `pyfakefs` installed as a package
  (see [#687](../../issues/687))

## [Version 4.6.0](https://pypi.python.org/pypi/pyfakefs/4.6.0) (2022-07-12)
Adds support for Python 3.11, removes support for Python 3.6, changes root 
path behavior under Windows. 

### Changes
* Python 3.6 has reached its end of life on 2021/12/23 and is no
  longer officially supported by pyfakefs
  * `os.stat_float_times` has been removed in Python 3.7 and is therefore no 
     longer supported
* under Windows, the root path is now effectively `C:\` instead of `\`; a 
  path starting with `\` points to the current drive as in the real file 
  system (see [#673](../../issues/673))
* fake `pathlib.Path.owner()` and `pathlib.Path.group()` now behave like the 
  real methods - they look up the real user/group name for the user/group id
  that is associated with the fake file (see [#678](../../issues/678))

### New Features
* added some support for the upcoming Python version 3.11
  (see [#677](../../issues/677))
* added convenience fixtures for module- and session based `fs` fixtures
  (`fs_module` and `fs_session`)

### Fixes
* fixed an incompatibility of `tmpdir` (and probably other fixtures) with the 
  module-scoped version of `fs`; had been introduced in 
  pyfakefs 4.5.5 by the fix for [#666](../../issues/666)
  (see [#684](../../issues/684))

## [Version 4.5.6](https://pypi.python.org/pypi/pyfakefs/4.5.6) (2022-03-17)
Fixes a regression which broke tests with older pytest versions (< 3.9).

### Changes
* minimum supported pytest version is now 3.0 (older versions do not work 
  properly with current Python versions)

### Fixes
* only skip `_pytest.pathlib` in pytest versions where it is actually present
  (see [#669](../../issues/669))

### Infrastructure
* add tests with different pytest versions, starting with 3.0

## [Version 4.5.5](https://pypi.python.org/pypi/pyfakefs/4.5.5) (2022-02-14)
Bugfix release, needed for compatibility with pytest 7.0.

### Fixes
* correctly handle file system space for files opened in write mode
  (see [#660](../../issues/660))
* correctly handle reading/writing pipes via file
  (see [#661](../../issues/661))
* disallow `encoding` argument on binary `open()`
  (see [#664](../../issues/664))
* fixed compatibility issue with pytest 7.0.0
  (see [#666](../../issues/666))

## [Version 4.5.4](https://pypi.python.org/pypi/pyfakefs/4.5.4) (2022-01-12)
Minor bugfix release.

### Fixes
* added missing mocked functions for fake pipe (see [#650](../../issues/650))
* fixed some bytes warnings (see [#651](../../issues/651))

## [Version 4.5.3](https://pypi.python.org/pypi/pyfakefs/4.5.3) (2021-11-08)
Reverts a change in the previous release that could cause a regression.

### Changes
* `os.listdir`, `os.scandir` and `pathlib.Path.listdir` now return the
  directory list in a random order only if explicitly configured in the 
  file system (use `fs.shuffle_listdir_results = True` with `fs` being the 
  file system). In a future version, the default may be changed to better 
  reflect the real filesystem behavior (see [#647](../../issues/647))
  
## [Version 4.5.2](https://pypi.python.org/pypi/pyfakefs/4.5.2) (2021-11-07)
This is a bugfix release.

### Changes
* `os.listdir`, `os.scandir` and `pathlib.Path.listdir` now return the
  directory list in a random order (see [#638](../../issues/638))
* the `fcntl` module under Unix is now mocked, e.g. all functions have no 
  effect (this may be changed in the future if needed,
  see [#645](../../issues/645))  

### Fixes
* fixed handling of alternative path separator in `os.path.split`,
  `os.path.splitdrive` and `glob.glob`
  (see [#632](../../issues/632))
* fixed handling of failed rename due to permission error
  (see [#643](../../issues/643))

  
## [Version 4.5.1](https://pypi.python.org/pypi/pyfakefs/4.5.1) (2021-08-29)
This is a bugfix release.

### Fixes
* added handling of path-like where missing
* improved handling of `str`/`bytes` paths
* suppress all warnings while inspecting loaded modules
  (see [#614](../../issues/614))
* do not import pandas and related modules if it is not patched
  (see [#627](../../issues/627))
* handle `pathlib.Path.owner()` and `pathlib.Path.group` by returning 
  the current user/group name (see [#629](../../issues/629))
* fixed handling of `use_known_patches=False` (could cause an exception)  
* removed Python 3.5 from metadata to disable installation for that version
  (see [#615](../../issues/615))

### Infrastructure
* added test dependency check (see [#608](../../issues/608))
* skip tests failing with ASCII locale
  (see [#623](../../issues/623))

## [Version 4.5.0](https://pypi.python.org/pypi/pyfakefs/4.5.0) (2021-06-04)
Adds some support for Python 3.10 and basic type checking.

_Note_: This version has been yanked from PyPI as it erroneously allowed
installation under Python 3.5.

### New Features
  * added support for some Python 3.10 features:
    * new method `pathlib.Path.hardlink_to` 
    * new `newline` argument in `pathlib.Path.write_text`
    * new `follow_symlinks` argument in `pathlib.Path.stat` and
     `pathlib.Path.chmod`
    * new 'strict' argument in `os.path.realpath`  

### Changes
  * Python 3.5 has reached its end of life in September 2020 and is no longer 
    supported
  * `pathlib2` is still supported, but considered to have the same
    functionality as `pathlib` and is no longer tested separately;
    the previous behavior broke newer `pathlib` features if `pathlib2`
    was installed (see [#592](../../issues/592))
    
### Fixes
  * correctly handle byte paths in `os.path.exists`
    (see [#595](../../issues/595))
  * Update `fake_pathlib` to support changes coming in Python 3.10
    ([see](https://github.com/python/cpython/pull/19342)
  * correctly handle UNC paths in `os.path.split` and in directory path 
    evaluation (see [#606](../../issues/606))

### Infrastructure
  * added mypy checks in CI (see [#599](../../issues/599))

## [Version 4.4.0](https://pypi.python.org/pypi/pyfakefs/4.4.0) (2021-02-24)
Adds better support for Python 3.8 / 3.9.
  
### New Features
  * added support for `pathlib.Path.link_to` (new in Python 3.8) 
    (see [#580](../../issues/580))
  * added support for `pathlib.Path.readlink` (new in Python 3.9) 
    (see [#584](../../issues/584))
  * added `FakeFilesystem.create_link` convenience method which creates
    intermittent directories (see [#580](../../issues/580))
    
### Fixes
  * fixed handling of pipe descriptors in the fake filesystem 
    (see [#581](../../issues/581))
  * added non-functional argument `effective_ids` to `os.access`
    (see [#585](../../issues/585))
  * correctly handle `os.file` for unreadable files
    (see [#588](../../issues/588))

### Infrastructure
  * added automatic documentation build and check-in

## [Version 4.3.3](https://pypi.python.org/pypi/pyfakefs/4.3.3) (2020-12-20)

Another bugfix release.

### Fixes
* Reverted one Windows-specific optimization that can break tests under some
  conditions (see [#573](../../issues/573))
* Setting `os` did not reset `os.sep` and related variables,
  fixed null device name, added `os.pathsep` and missing `os.path` variables
  (see [#572](../../issues/572))

## [Version 4.3.2](https://pypi.python.org/pypi/pyfakefs/4.3.2) (2020-11-26)

This is a bugfix release that fixes a regression introduced in version 4.2.0.

### Fixes
* `open` calls had not been patched for modules with a name ending with "io"
  (see [#569](../../issues/569))

## [Version 4.3.1](https://pypi.python.org/pypi/pyfakefs/4.3.1) (2020-11-23)

This is an update to the performance release, with more setup caching and the
possibility to disable it. 

### Changes
* Added caching of patched modules to avoid lookup overhead  
* Added `use_cache` option and `clear_cache` method to be able
  to deal with unwanted side effects of the newly introduced caching

### Infrastructure
* Moved CI builds to GitHub Actions for performance reasons

## [Version 4.3.0](https://pypi.python.org/pypi/pyfakefs/4.3.0) (2020-11-19)

This is mostly a performance release. The performance of the pyfakefs setup has
been decreasing sufficiently, especially with the 4.x releases. This release
corrects that by making the most expansive feature optional, and by adding some
other performance improvements. This shall decrease the setup time by about a
factor of 20, and it shall now be comparable to the performance of the 3.4
release.

### Changes
  * The `patchfs` decorator now expects a positional argument instead of the
    keyword arguments `fs`. This avoids confusion with the pytest `fs`
    fixture and conforms to the behavior of `mock.patch`. You may have to
    adapt the argument order if you use the `patchfs` and `mock.patch`
    decorators together (see [#566](../../issues/566)) 
  * Default arguments that are file system functions are now _not_ patched by
    default to avoid a large performance impact. An additional parameter
    `patch_default_args` has been added that switches this behavior on
    (see [#567](../../issues/567)).
  * Added performance improvements in the test setup, including caching the
    the unpatched modules
    
## [Version 4.2.1](https://pypi.python.org/pypi/pyfakefs/4.2.1) (2020-11-02)

This is a bugfix release that fixes a regression issue.

### Fixes
  * remove dependency of pyfakefs on `pytest` (regression, 
    see [#565](../../issues/565)) 

## [Version 4.2.0](https://pydpi.python.org/pypi/pyfakefs/4.2.0) (2020-11-01)

#### New Features
  * add support for the `buffering` parameter in `open` 
    (see [#549](../../issues/549))
  * add possibility to patch `io.open_code` using the new argument 
    `patch_open_code` (since Python 3.8)
    (see [#554](../../issues/554))
  * add possibility to set file system OS via `FakeFilesystem.os` 
    
#### Fixes
  * fix check for link in `os.walk` (see [#559](../../issues/559))
  * fix handling of real files in combination with `home` if simulating
    Posix under Windows (see [#558](../../issues/558))
  * do not call fake `open` if called from skipped module  
    (see [#552](../../issues/552))
  * do not call fake `pathlib.Path` if called from skipped module  
    (see [#553](../../issues/553))
  * fixed handling of `additional_skip_names` with several module components
  * allow to open existing pipe file descriptor
    (see [#493](../../issues/493))
  * do not truncate file on failed flush
    (see [#548](../../issues/548))
  * suppress deprecation warnings while collecting modules
    (see [#542](../../issues/542))
  * add support for `os.truncate` and `os.ftruncate`
    (see [#545](../../issues/545))

#### Infrastructure
  * fixed another problem with CI test scripts not always propagating errors
  * make sure pytest will work without pyfakefs installed
   (see [#550](../../issues/550))

## [Version 4.1.0](https://pypi.python.org/pypi/pyfakefs/4.1.0) (2020-07-12)

#### New Features
  * Added some support for pandas (`read_csv`, `read_excel` and more), and
   for django file locks to work with the fake filesystem 
   (see [#531](../../issues/531))
  
#### Fixes
  * `os.expanduser` now works with a bytes path
  * Do not override global warnings setting in `Deprecator` 
    (see [#526](../../issues/526))
  * Make sure filesystem modules in `pathlib` are patched
    (see [#527](../../issues/527))
  * Make sure that alternative path separators are correctly handled under Windows
    (see [#530](../../issues/530))

#### Infrastructure
  * Make sure all temporary files from real fs tests are removed

## [Version 4.0.2](https://pypi.python.org/pypi/pyfakefs/4.0.2) (2020-03-04)

This as a patch release that only builds for Python 3. Note that 
versions 4.0.0 and 4.0.1 will be removed from PyPI to disable
installing them under Python 2. 

#### Fixes
  * Do not build for Python 2 (see [#524](../../issues/524))

## [Version 4.0.1](https://pypi.python.org/pypi/pyfakefs/4.0.1) (2020-03-03)

This as a bug fix release for a regression bug.

_Note_: This version has been yanked from PyPI as it erroneously allowed
installation under Python 2. This has been fixed in version 4.0.2.

#### Fixes
  * Avoid exception if using `flask-restx` (see [#523](../../issues/523))

## [Version 4.0.0](https://pypi.python.org/pypi/pyfakefs/4.0.0) (2020-03-03)
pyfakefs 4.0.0 drops support for Python 2.7. If you still need
Python 2.7, you can continue to use pyfakefs 3.7.x.

_Note_: This version has been yanked from PyPI as it erroneously allowed
installation under Python 2. This has been fixed in version 4.0.2.

#### Changes
  * Removed Python 2.7 and 3.4 support (see [#492](../../issues/492))
  
#### New Features
  * Added support for handling keyword-only arguments in some `os` functions
  * Added possibility to pass additional parameters to `fs` pytest fixture
  * Added automatic patching of default arguments that are file system
    functions
  * Added convenience decorator `patchfs` to patch single functions using
    the fake filesystem
  
#### Fixes
  * Added missing `st_ino` in `makedir` (see [#515](../../issues/515))
  * Fixed handling of relative paths in `lresolve` / `os.lstat`
    (see [#516](../../issues/516))
  * Fixed handling of byte string paths 
    (see [#517](../../issues/517))
  * Fixed `os.walk` if path ends with path separator
    (see [#512](../../issues/512))
  * Fixed handling of empty path in `os.makedirs`
    (see [#510](../../issues/510))
  * Fixed handling of `os.TMPFILE` flag under Linux
    (see [#509](../../issues/509) and [#511](../../issues/511))
  * Adapted fake `pathlib` to changes in Python 3.7.6/3.8.1   
    (see [#508](../../issues/508))
  * Fixed behavior of `os.makedirs` in write-protected directory 
    (see [#507](../../issues/507))

## [Version 3.7.2](https://pypi.python.org/pypi/pyfakefs/3.7.2) (2020-03-02)

This version backports some fixes from main.

#### Fixes
  * Fixed handling of relative paths in `lresolve` / `os.lstat`
    (see [#516](../../issues/516))
  * Fixed `os.walk` if path ends with path separator
    (see [#512](../../issues/512))
  * Fixed handling of empty path in `os.makedirs`
    (see [#510](../../issues/510))
  * Fixed handling of `os.TMPFILE` flag under Linux
    (see [#509](../../issues/509) and [#511](../../issues/511))
  * Fixed behavior of `os.makedirs` in write-protected directory 
    (see [#507](../../issues/507))

## [Version 3.7.1](https://pypi.python.org/pypi/pyfakefs/3.7.1) (2020-02-14)

This version adds support for Python 3.7.6 and 3.8.1.

#### Fixes
  * Adapted fake `pathlib` to changes in Python 3.7.6/3.8.1   
    (see [#508](../../issues/508)) (backported from main)
    
## [Version 3.7](https://pypi.python.org/pypi/pyfakefs/3.7) (2019-11-23)

This version adds support for Python 3.8.

_Note:_ This is the last pyfakefs version that will support Python 2.7 
and Python 3.4 (possible bug fix releases notwithstanding).

#### New Features
  * added support for Python 3.8 (see [#504](../../issues/504))
  * added preliminary support for Windows-specific `os.stat_result` attributes
    `tst_file_attributes` and `st_reparse_tag` (see [#504](../../issues/504))
  * added support for fake `os.sendfile` (Posix only, Python 3 only)
    (see [#504](../../issues/504))

#### Fixes
  * support `devnull` in Windows under Python 3.8
    (see [#504](../../issues/504)) 
  * fixed side effect of calling `DirEntry.stat()` under Windows (changed 
    st_nlink) (see [#502](../../issues/502))
  * fixed problem of fake modules still referenced after a test in modules 
    loaded during the test (see [#501](../../issues/501) and [#427](../../issues/427))
  * correctly handle missing read permission for parent directory
    (see [#496](../../issues/496))
  * raise for `os.scandir` with non-existing directory
    (see [#498](../../issues/498))
    
#### Infrastructure
  * fixed CI tests scripts to always propagate errors
    (see [#500](../../issues/500))

## [Version 3.6.1](https://pypi.python.org/pypi/pyfakefs/3.6.1) (2019-10-07)

#### Fixes
  * avoid rare side effect during module iteration in test setup
    (see [#338](../../issues/338))
  * make sure real OS tests are not executed by default 
    (see [#495](../../issues/495))
    
## [Version 3.6](https://pypi.python.org/pypi/pyfakefs/3.6) (2019-06-30)

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

## [Version 3.5.8](https://pypi.python.org/pypi/pyfakefs/3.5.8) (2019-06-21)

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

## [Version 3.5.7](https://pypi.python.org/pypi/pyfakefs/3.5.7) (2019-02-08)

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

## [Version 3.5.6](https://pypi.python.org/pypi/pyfakefs/3.5.6) (2019-01-13)

#### Changes
  * import external `pathlib2` and `scandir` packages first if present
    (see [#462](../../issues/462))

## [Version 3.5.5](https://pypi.python.org/pypi/pyfakefs/3.5.5) (2018-12-20)

#### Fixes
  * removed shebang from test files to avoid packaging warnings
   (see [#461](../../issues/461))

## [Version 3.5.4](https://pypi.python.org/pypi/pyfakefs/3.5.4) (2018-12-19)

#### New Features
  * added context manager class `Pause` for pause/resume
    (see [#448](../../issues/448))

#### Fixes
  * fixed `AttributeError` shown while displaying `fs` in a failing pytest
    in Python 2
  * fixed permission handling for root user
  * avoid `AttributeError` triggered by modules without `__module__` attribute
    (see [#460](../../issues/460))

## [Version 3.5.3](https://pypi.python.org/pypi/pyfakefs/3.5.3) (2018-11-22)

This is a minor release to have a version with passing tests for OpenSUSE
packaging.

#### New Features
  * automatically patch file system methods imported as another name like
    `from os.path import exists as my_exists`, including builtin `open`
    and `io.open`

#### Fixes
  * make tests for access time less strict to account for file systems that
    do not change it immediately ([#453](../../issues/453))

## [Version 3.5.2](https://pypi.python.org/pypi/pyfakefs/3.5.2) (2018-11-11)

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

## [Version 3.5](https://pypi.python.org/pypi/pyfakefs/3.5) (2018-10-22)

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

## [Version 3.4.3](https://pypi.python.org/pypi/pyfakefs/3.4.3) (2018-06-13)

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

## [Version 3.4.1](https://pypi.python.org/pypi/pyfakefs/3.4.1) (2018-03-18)

This is a bug fix only release.

#### Fixes
  * Missing cleanup after using dynamic patcher let to incorrect behavior of
   `tempfile` after test execution (regression, see [#356](../../issues/356))
  * `add_real_directory` does not work after `chdir` (see [#355](../../issues/355))

## [Version 3.4](https://pypi.python.org/pypi/pyfakefs/3.4) (2018-03-08)

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

## [Version 3.3](https://pypi.python.org/pypi/pyfakefs/3.3) (2017-11-12)

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

## [Version 3.2](https://pypi.python.org/pypi/pyfakefs/3.2) (2017-05-27)

#### New Features
  * The `errors` argument is supported for `io.open()` and `os.open()`
  * New methods `add_real_file()`, `add_real_directory()` and `add_real_paths()`
    make real files and directories appear within the fake file system.
    File contents are read from the real file system only as needed ([#170](../../issues/170)).
    See `example_test.py` for a usage example.
  * Deprecated `TestCase.copyRealFile()` in favor of `add_real_file()`.
    `copyRealFile()` remains only for backward compatibility.  Also, some
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

## [Version 3.1](https://pypi.python.org/pypi/pyfakefs/3.1) (2017-02-11)

#### New Features
 * Added helper method `TestCase.copyRealFile()` to copy a file from
   the real file system to the fake file system. This makes it easy to use
   template, data and configuration files in your tests.
 * A pytest plugin is now installed with pyfakefs that exports the
   fake filesystem as pytest fixture `fs`.

#### Fixes
 * Incorrect disk usage calculation if too large file created ([#155](../../issues/155))

## [Version 3.0](https://pypi.python.org/pypi/pyfakefs/3.0) (2017-01-18)

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
 * Added [auto-generated documentation](http://pytest-dev.github.io/pyfakefs/)

#### Fixes
 * `shutil.move` incorrectly moves directories ([#145](../../issues/145))
 * Missing support for 'x' mode in `open` (Python >= 3.3) ([#147](../../issues/147))
 * Incorrect exception type in Posix if path ancestor is a file ([#139](../../issues/139))
 * Exception handling when using `Patcher` with py.test ([#135](../../issues/135))
 * Fake `os.listdir` returned sorted instead of unsorted entries

## [Version 2.9](https://pypi.python.org/pypi/pyfakefs/2.9) (2016-10-02)

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
There are no release notes for releases 2.6 and below.  The following versions are still available on PyPI:
 * [1.1](https://pypi.python.org/pypi/pyfakefs/1.1), [1.2](https://pypi.python.org/pypi/pyfakefs/1.2), [2.0](https://pypi.python.org/pypi/pyfakefs/2.0), [2.1](https://pypi.python.org/pypi/pyfakefs/2.1), [2.2](https://pypi.python.org/pypi/pyfakefs/2.2), [2.3](https://pypi.python.org/pypi/pyfakefs/2.3) and [2.4](https://pypi.python.org/pypi/pyfakefs/2.4)
