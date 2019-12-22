#!/bin/bash
# script to install Python versions under MacOS, as Travis.IO
# does not have explicit Python support for MacOS
# Taken from https://github.com/pyca/cryptography and adapted.

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    sw_vers

    # install pyenv
    git clone --depth 1 https://github.com/pyenv/pyenv ~/.pyenv
    PYENV_ROOT="$HOME/.pyenv"
    PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"

    case "${PYTHON}" in
        py34|py35|py36|py37|py38)
            pyenv install "${PY_VERSION}"
            pyenv global "${PY_VERSION}"
            ;;
        pypy*)
            pyenv install "$PYPY_VERSION"
            pyenv global "$PYPY_VERSION"
            ;;
    esac
    pyenv rehash
    python -m pip install --user virtualenv
    python -m virtualenv ~/.venv
    source ~/.venv/bin/activate
fi

if [ -n "$PY_VERSION" ]
then
  echo Checking Python version...
  if [ "$(python --version)" != "Python ${PY_VERSION}" ]
  then
      echo Incorrect version - expected "${PY_VERSION}".
      echo Exiting.
      exit 1
  fi
  echo Python version ok.
fi

if ! [[ $VM == 'Docker' ]]; then
pip install -r requirements.txt
pip install -r extra_requirements.txt
pip install .
fi