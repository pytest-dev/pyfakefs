---
name: Bug report
about: Create a report to help us improve
title: ''
labels: ''
assignees: ''

---

**Describe the bug**
Describe the observed behavior, and what you expect to happen instead.
In case of a crash, please provide the complete stack trace.

**How To Reproduce**
Please provide a unit test or a minimal reproducible example that shows
the problem.

**Your environment**
Please run the following in the environment where the problem happened and
paste the output.
```bash
python -c "import platform; print(platform.platform())"
python -c "import sys; print('Python', sys.version)"
python -c "from pyfakefs import __version__; print('pyfakefs', __version__)"
python -c "import pytest; print('pytest', pytest.__version__)"
```
