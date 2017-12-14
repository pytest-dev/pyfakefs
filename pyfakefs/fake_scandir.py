import sys


class DirEntry(object):
    """Emulates os.DirEntry. Note that we did not enforce keyword only arguments."""

    def __init__(self, filesystem):
        """Initialize the dir entry with unset values.

        Args:
            filesystem: the fake filesystem used for implementation.
        """
        self._filesystem = filesystem
        self.name = ''
        self.path = ''
        self._inode = None
        self._islink = False
        self._isdir = False
        self._statresult = None
        self._statresult_symlink = None

    def inode(self):
        """Return the inode number of the entry."""
        if self._inode is None:
            self.stat(follow_symlinks=False)
        return self._inode

    def is_dir(self, follow_symlinks=True):
        """Return True if this entry is a directory entry.

        Args:
            follow_symlinks: If True, also return True if this entry is a symlink
                            pointing to a directory.

        Returns:
            True if this entry is an existing directory entry, or if
            follow_symlinks is set, and this entry points to an existing directory entry.
        """
        return self._isdir and (follow_symlinks or not self._islink)

    def is_file(self, follow_symlinks=True):
        """Return True if this entry is a regular file entry.

        Args:
            follow_symlinks: If True, also return True if this entry is a symlink
                            pointing to a regular file.

        Returns:
            True if this entry is an existing file entry, or if
            follow_symlinks is set, and this entry points to an existing file entry.
        """
        return not self._isdir and (follow_symlinks or not self._islink)

    def is_symlink(self):
        """Return True if this entry is a symbolic link (even if broken)."""
        return self._islink

    def stat(self, follow_symlinks=True):
        """Return a stat_result object for this entry.

        Args:
            follow_symlinks: If False and the entry is a symlink, return the
                result for the symlink, otherwise for the object it points to.
        """
        if follow_symlinks:
            if self._statresult_symlink is None:
                file_object = self._filesystem.ResolveObject(self.path)
                if self._filesystem.is_windows_fs:
                    file_object.st_nlink = 0
                self._statresult_symlink = file_object.stat_result.copy()
            return self._statresult_symlink

        if self._statresult is None:
            file_object = self._filesystem.LResolveObject(self.path)
            self._inode = file_object.st_ino
            if self._filesystem.is_windows_fs:
                file_object.st_nlink = 0
            self._statresult = file_object.stat_result.copy()
        return self._statresult


class ScanDirIter:
    """Iterator for DirEntry objects returned from `scandir()`
    function."""

    def __init__(self, filesystem, path):
        self.filesystem = filesystem
        self.path = self.filesystem.ResolvePath(path)
        contents = {}
        try:
            contents = self.filesystem.ConfirmDir(path).contents
        except OSError:
            pass
        self.contents_iter = iter(contents)

    def __iter__(self):
        return self

    def __next__(self):
        try:
            entry = self.contents_iter.next()
        except AttributeError:
            entry = self.contents_iter.__next__()
        dir_entry = DirEntry(self.filesystem)
        dir_entry.name = entry
        dir_entry.path = self.filesystem.JoinPaths(self.path, dir_entry.name)
        dir_entry._isdir = self.filesystem.IsDir(dir_entry.path)
        dir_entry._islink = self.filesystem.IsLink(dir_entry.path)
        return dir_entry

    # satisfy both Python 2 and 3
    next = __next__

    if sys.version_info >= (3, 6):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()

        def close(self):
            pass


def scandir(filesystem, path=''):
    """Return an iterator of DirEntry objects corresponding to the entries
    in the directory given by path.

    Args:
        filesystem: The fake filesystem used for implementation
        path: Path to the target directory within the fake filesystem.

    Returns:
        an iterator to an unsorted list of os.DirEntry objects for
        each entry in path.

    Raises:
        OSError: if the target is not a directory.
    """
    return ScanDirIter(filesystem, path)


def _classify_directory_contents(filesystem, root):
    """Classify contents of a directory as files/directories.

    Args:
        filesystem: The fake filesystem used for implementation
        root: (str) Directory to examine.

    Returns:
        (tuple) A tuple consisting of three values: the directory examined,
        a list containing all of the directory entries, and a list
        containing all of the non-directory entries.
        (This is the same format as returned by the `os.walk` generator.)

    Raises:
        Nothing on its own, but be ready to catch exceptions generated by
        underlying mechanisms like `os.listdir`.
    """
    dirs = []
    files = []
    for entry in filesystem.ListDir(root):
        if filesystem.IsDir(filesystem.JoinPaths(root, entry)):
            dirs.append(entry)
        else:
            files.append(entry)
    return root, dirs, files


def walk(filesystem, top, topdown=True, onerror=None, followlinks=False):
    """Perform an os.walk operation over the fake filesystem.

    Args:
        filesystem: The fake filesystem used for implementation
        top: The root directory from which to begin walk.
        topdown: Determines whether to return the tuples with the root as
            the first entry (`True`) or as the last, after all the child
            directory tuples (`False`).
      onerror: If not `None`, function which will be called to handle the
            `os.error` instance provided when `os.listdir()` fails.
      followlinks: If `True`, symbolic links are followed.

    Yields:
        (path, directories, nondirectories) for top and each of its
        subdirectories.  See the documentation for the builtin os module
        for further details.
    """

    def do_walk(top_dir, top_most=False):
        top_dir = filesystem.CollapsePath(top_dir)
        if not top_most and not followlinks and filesystem.IsLink(top_dir):
            return
        try:
            top_contents = _classify_directory_contents(filesystem, top_dir)
        except OSError as exc:
            top_contents = None
            if onerror is not None:
                onerror(exc)

        if top_contents is not None:
            if topdown:
                yield top_contents

            for directory in top_contents[1]:
                if not followlinks and filesystem.IsLink(directory):
                    continue
                for contents in do_walk(filesystem.JoinPaths(top_dir, directory)):
                    yield contents

            if not topdown:
                yield top_contents

    return do_walk(top, top_most=True)


class FakeScanDirModule(object):
    def __init__(self, filesystem):
        self.filesystem = filesystem

    def scandir(self, path='.'):
        return scandir(self.filesystem, path)

    def walk(self, top, topdown=True, onerror=None, followlinks=False):
        return walk(self.filesystem, top, topdown, onerror, followlinks)
