#!/bin/bash

set -e

if [ "$(git config user.name)" != "github-actions[bot]" ]; then
    echo "Error: This script is intended to run in github actions."
    exit 1
fi

git checkout --orphan ics

python3 generate.py

git reset --hard

git add sydneytrains

git commit -m "Update calendar data"

git push -f origin ics
