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
        py27)
            curl -O https://bootstrap.pypa.io/get-pip.py
            python get-pip.py --user
            ;;
        py33)
            pyenv install 3.3.5
            pyenv global 3.3.5
            ;;
        py34)
            pyenv install 3.4.4
            pyenv global 3.4.4
            ;;
        py35)
            pyenv install 3.5.4
            pyenv global 3.5.4
            ;;
        py36)
            pyenv install 3.6.3
            pyenv global 3.6.3
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

pip install -r requirements.txt
pip install .
