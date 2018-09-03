try:
    import pathlib
    pathlib2 = None
except ImportError:
    try:
        import pathlib2
        pathlib = pathlib2
    except ImportError:
        pathlib = None
        pathlib2 = None


try:
    from os import scandir
    use_scandir = True
    use_scandir_package = False
except ImportError:
    try:
        import scandir
        use_scandir = True
        use_scandir_package = True
    except ImportError:
        use_scandir = False
        use_scandir_package = False
