#!/bin/bash

if [[ $VM == 'Docker' ]]; then
    echo "Running tests in Docker image"
    echo "============================="
    docker build -t pyfakefs .
    docker run -t pyfakefs
fi
