
# Contributing to pyfakefs

We welcome any contributions that help to improve pyfakefs for the community.
Contributions may include bug reports, bug fixes, new features, infrastructure enhancements, or
documentation updates.

## How to contribute

### Reporting Bugs

If you think you found a bug in pyfakefs, you can [create an issue](https://help.github.com/articles/creating-an-issue/).
Before filing the bug, please check, if it still exists in the [main branch](https://github.com/pytest-dev/pyfakefs).
If you can reproduce the problem, please provide enough information so that it can be reproduced by other developers.
This includes:
  * The Operating System
  * The Python version
  * A minimal example to reproduce the problem (preferably in the form of a failing test)
  * The stack trace in case of an unexpected exception.
For better readability, you may use [markdown code formatting](https://help.github.com/articles/creating-and-highlighting-code-blocks/) for any included code.

### Proposing Enhancements

If you need a specific feature that is not implemented, or have an idea for the next
exciting gimmick in pyfakefs, you can also create a respective issue.
Of course - implementing it yourself is the best chance to get it done!
The next item has some information on doing this.

### Contributing Code

The preferred workflow for contributing code is to
[fork](https://help.github.com/articles/fork-a-repo/) the [repository](https://github.com/pytest-dev/pyfakefs) on GitHub, clone it,
develop on a feature branch, and [create a pull request](https://help.github.com/articles/creating-a-pull-request-from-a-fork) when done.
There are a few things to consider for contributing code:
  * We ensure the [PEP-8 coding style](https://www.python.org/dev/peps/pep-0008/)
    by using [black](https://pypi.org/project/black/) auto-format in a
    pre-commit hook; you can locally install
    [pre-commit](https://pypi.org/project/pre-commit/) to run the linter
    tests on check-in or on demand (`pre-commit run --all-files`)
  * Use the [Google documentation style](https://google.github.io/styleguide/pyguide.html) to document new public classes or methods
  * Provide unit tests for bug fixes or new functionality - check the existing tests for examples
  * Provide meaningful commit messages - it is ok to amend the commits to improve the comments
  * Check that the automatic GitHub Action CI tests all pass for your pull request
  * Be ready to adapt your changes after a code review

### Contributing Documentation

If you want to improve the existing documentation, you can do this also using a pull request.
You can contribute to:
  * the source code documentation using [Google documentation style](https://google.github.io/styleguide/pyguide.html)
  * the [README](https://github.com/pytest-dev/pyfakefs/blob/main/README.md) using [markdown syntax](https://help.github.com/articles/basic-writing-and-formatting-syntax/)
  * the documentation published on [Read the Docs](https://pytest-pyfakefs.readthedocs.io/en/latest/),
    located in the `docs` directory (call `make html` from that directory).
    For building the documentation, you will need [sphinx](http://sphinx.pocoo.org/).
  * [this file](https://github.com/pytest-dev/pyfakefs/blob/main/CONTRIBUTING.md)
  if you want to enhance the contributing guide itself

Thanks for taking the time to contribute to pyfakefs!
