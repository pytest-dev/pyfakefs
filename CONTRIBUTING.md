
# Contributing to pyfakefs

We welcome any contributions that help to improve pyfakefs for the community.
This may include bug reports, bug fixes, new features, infrastructure enhancements, or 
documentation updates.

## How to contribute

### Reporting Bugs

If you think you found a bug in pyfakefs, you can [create an issue](https://help.github.com/articles/creating-an-issue/).
Before filing the bug, please check, if it still exists in the [master branch](https://github.com/jmcgeheeiv/pyfakefs). 
If you can reproduce the problem, please provide enough information to reproduce the problem.
This includes:
  * The Operating System
  * The Python version
  * A minimal example to reproduce the problem (preferably in the form of a failing test, if possible)
  * The stack trace in case of an unexpected excpetion
For better readabilty, you may use [markdown code formatting](https://help.github.com/articles/creating-and-highlighting-code-blocks/) for any included code.

### Proposing Enhancements

If you need a specific feature that is not implemented, or have an idea for the next 
exciting enhancement in pyfakefs, you can also create a respective issue. The best chances 
to get it are of course if you implement it yourself, as described in the next item.

### Contributing Code

The preferred workflow for contributing code is to [fork](https://help.github.com/articles/fork-a-repo/) the
[repository](https://github.com/jmcgeheeiv/pyfakefs) on GitHub, clone, 
develop on a feature branch, and [create a pull requests](https://help.github.com/articles/creating-a-pull-request-from-a-fork).
There are a few things to consider for contributing code:
  * Please use the standard [PEP-8 coding style](https://www.python.org/dev/peps/pep-0008/) 
  (your IDE or tools like [pep8](https://pypi.python.org/pypi/pep8) or [pylint](https://pypi.python.org/pypi/pylint) will help you)
  * Use the [Google documentation style](https://google.github.io/styleguide/pyguide.html) to document new public classes or methods
  * Provide unit tests for bug fixes or new functionality - check the existing tests for examples
  * Provide meaningful commit messages
  
### Contributing Documentation

If you want to improve the existing documentation, you can just create a pull request with the changes.
You can contribute to:
  * the source code documentation using [Google documentation style](https://google.github.io/styleguide/pyguide.html) 
  * the [README](https://github.com/jmcgeheeiv/pyfakefs/blob/master/README.md)
  * the documentation published on [GitHub Pages](http://jmcgeheeiv.github.io/pyfakefs/), located in the 'docs' directory. 
  For building the documentation, you will need [sphinx](http://sphinx.pocoo.org/).
  * [this file](https://github.com/jmcgeheeiv/pyfakefs/blob/master/CONTRIBUTING.md) if you want to enhance the contributing guide itself

Thanks for taking the time to contribute to pyfakefs!
