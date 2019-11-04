#!/bin/bash

echo "Running tests in Docker image"
echo "============================="
export TEST_REAL_FS=1
export BRANCH=$(if [ "$TRAVIS_PULL_REQUEST" == "false" ]; then echo $TRAVIS_BRANCH; else echo $TRAVIS_PULL_REQUEST_BRANCH; fi)
export REPO_SLUG=$(if [ "$TRAVIS_PULL_REQUEST" == "false" ]; then echo $TRAVIS_REPO_SLUG; else echo $TRAVIS_PULL_REQUEST_SLUG; fi)
docker build -t pyfakefs . --build-arg github_repo=$REPO_SLUG --build-arg github_branch=$BRANCH
docker run -t pyfakefs
