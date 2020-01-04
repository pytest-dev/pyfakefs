#!/bin/bash

if [[ $VM == 'Docker' ]]; then
    echo "Running tests in Docker image '$DOCKERFILE'"
    echo "============================="
    export BRANCH=$(if [ "$TRAVIS_PULL_REQUEST" == "false" ]; then echo $TRAVIS_BRANCH; else echo $TRAVIS_PULL_REQUEST_BRANCH; fi)
    export REPO_SLUG=$(if [ "$TRAVIS_PULL_REQUEST" == "false" ]; then echo $TRAVIS_REPO_SLUG; else echo $TRAVIS_PULL_REQUEST_SLUG; fi)
    docker build -t pyfakefs -f .travis/dockerfiles/Dockerfile_$DOCKERFILE . --build-arg github_repo=$REPO_SLUG --build-arg github_branch=$BRANCH
    docker run -t pyfakefs
fi
