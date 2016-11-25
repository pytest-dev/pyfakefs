#!/bin/bash
# Create html documentation from docstrings using sphinx
# and check it into gh-pages branch using the same commit message.
# Skipped if not the master branch, triggered by a pull request,
# or the string SKIP-AUTODOC appears in the commit message.

# only process after the last matrix build
if [ "$TRAVIS_PYTHON_VERSION" != "3.6-dev" ]; then
  exit 0
fi

SOURCE_BRANCH="autodoc-test"
TARGET_BRANCH="gh-pages"
REPO_URL="https://${GH_TOKEN}@github.com/jmcgeheeiv/pyfakefs.git"

if [ "$TRAVIS_BRANCH" != "$SOURCE_BRANCH" ]; then
  echo "Not on $SOURCE_BRANCH branch, skipping"
  exit 0
fi

if [ "$TRAVIS_PULL_REQUEST" != "false" ]; then
  echo "This is a pull request, skipping"
  exit 0
fi

# enable error reporting to the console
set -e

# save last commit log - will be used for the doc commit
LAST_COMMIT=`git log -1 --pretty=%B`
if [[ $LAST_COMMIT == *"SKIP-AUTODOC"* ]]; then
  echo "Autodoc switched off in commit message, skipping"
  exit 0
fi

# create the docs using sphinx
cd docs
make html
cd ..

# clone `gh-pages' branch of the repository using encrypted GH_TOKEN for authentification
git clone $REPO_URL -b $TARGET_BRANCH ../pyfakefs_gh-pages

# copy generated HTML files to `gh-pages' branch
cp gh-pages/*.html ../pyfakefs_gh-pages
cp gh-pages/*.js ../pyfakefs_gh-pages

# commit and push generated content to `gh-pages' branch
cd ../pyfakefs_gh-pages
git config user.name "Travis CI"
git config user.email "pyfakefs@gmail.com"
git commit -a -m "$LAST_COMMIT"
git push --quiet $REPO_URL $TARGET_BRANCH > /dev/null 2>&1
