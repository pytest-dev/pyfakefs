#!/bin/bash

pip install flake8

# let the build fail for any flake8 warning
flake8 . --exclude get-pip.py --max-complexity=13 --statistics
