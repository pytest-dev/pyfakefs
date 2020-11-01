"""
This is a test case for pyfakefs issue #45.
This problem is resolved by using PyTest version 2.8.6 or above.

To run these doctests, install pytest and run:

    $ pytest --doctest-modules pytest_doctest_test.py

Add `-s` option to enable print statements.
"""
from __future__ import unicode_literals


def make_file_factory(func_name, fake, result):
    """ Return a simple function with parametrized doctest. """

    def make_file(name, content=''):
        with open(name, 'w') as f:
            f.write(content)

    make_file.__doc__ = """
        >>> import os
        >>> {command}
        >>> name, content = 'foo', 'bar'
        >>> {func_name}(name, content)
        >>> open(name).read() == content
        {result}
        >>> os.remove(name)  # Cleanup
        """.format(
        command="getfixture('fs')" if fake else "pass",
        func_name=func_name,
        result=result)

    return make_file


passes = make_file_factory('passes', fake=False, result=True)
passes_too = make_file_factory('passes_too', fake=True, result=True)

passes_too.__doc__ = passes_too.__doc__.replace('>>> os.remove(name)',
                                                '>>> pass')

fails = make_file_factory('fails', fake=False, result=False)

# Pytest versions below 2.8.6 raise an internal error when running
# these doctests:
crashes = make_file_factory('crashes', fake=True, result=False)
crashes_too = make_file_factory(') SyntaxError', fake=True, result=False)
