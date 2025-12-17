#!/bin/bash

set -e

if [ "$(git config user.name)" != "github-actions[bot]" ]; then
    echo "Error: This script is intended to run in github actions."
    exit 1
fi

python3 generate.py

mv ics /tmp

if git fetch origin "$DATA_BRANCH"; then
    git checkout FETCH_HEAD
else
    git checkout --orphan "$DATA_BRANCH"
    git reset --hard
fi

rm -rf *

mv /tmp/ics/* .

git add .

if git commit -m "Update calendar data"; then
    git push origin "HEAD:$DATA_BRANCH"
fi
