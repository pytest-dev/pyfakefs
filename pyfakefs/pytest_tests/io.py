"""
This is a test case for pyfakefs issue #708.
It tests the usage of an own module with the same name as a patched filesystem
module, the content is taken from the issue.
"""


class InputStream:
    def __init__(self, name):
        self.name = name

    def read(self):
        with open(self.name, 'r') as f:
            return f.readline()
