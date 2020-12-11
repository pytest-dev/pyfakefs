---
name: Bug report
about: Create a report to help us improve
title: ''
labels: ''
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.
Please provide a stack trace if available.

**How To Reproduce**
Please provide a unit test or a minimal code snippet that reproduces the 
problem.

**Your environment**
Please run the following and paste the output.
```bash
python -c "import platform; print(platform.platform())"
python -c "import sys; print('Python', sys.version)"
python -c "from pyfakefs.fake_filesystem import __version__; print('pyfakefs', __version__)"
```
