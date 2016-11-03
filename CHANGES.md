# Release Notes

## Unreleased

#### New Features
 * support for `os.scandir` (Python >= 3.5)
 * option to not fake modules named `path`
 * `glob.glob`, `glob.iglob`: support for `recursive` argument
 * support for `glob.iglob`

## Version 2.9

#### New Features
 * `io.open`, `os.open`: support for `encoding` argument
 * `os.makedirs`: support for `exist_ok` argument
 * support for fake `io.open()`
 * support for mount points
 * support for hard links
 * support for float times (mtime, ctime)
 * Windows support:
     * support for alternative path separator (Windows)
     * support for case-insensitive filesystems
     * supprt for drive letters and UNC paths
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
