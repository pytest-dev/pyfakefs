def load(path: str) -> str:
    from pyfakefs.pytest_tests import lib_using_pathlib

    return lib_using_pathlib.use_pathlib(path)
