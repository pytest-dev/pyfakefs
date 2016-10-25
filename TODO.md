## To-do list/ideas for pyfakefs
### Python 3
#### Add support for new arguments
 * dir_fd (os.access, os.chmod, os.chown, os.link, os.lstat, os.mkdir, os.mknod, 
           os.open, os.readlink, os.remove, os.rename, os.rmdir, os.stat, os.symlink, os.utime)
 * follow_symlinks (os.link)
 * effective_ids (os.access)
 * open file descriptor as path (os.access, os.chmod)
 * ns (os.utime)

#### Add support for new/unsupported commands
 * os.getcwbd
 * os.sync
 * os.fchmod, os.fchown, os.ftruncate, ...
 * os.lseek
 * ...
 
#### Miscellaneous
 * correctly support keyword-only arguments
 * add 3.6 to travis
 * add support for path-like objects (3.6)
 
### Coding style
 * fix pep-8 and pylint issues
 * setup pylint check (by landscape or similar)
 
### Documentation
 * cleanup/unify documentation
 * auto-publish documentation on readthedocs.com
 * add release notes
 