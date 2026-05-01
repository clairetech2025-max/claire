#!/usr/bin/env bash
set -euo pipefail

REPO="git@github.com:Claire-Systems/are-spectacle-private.git"
PAYLOAD_DIR="/home/LuciusPrime/claire/private_repo_payloads/are-spectacle-private"

cd "$PAYLOAD_DIR"

if [ ! -d .git ]; then
  git init
fi

git branch -M main
git add .

if git diff --cached --quiet; then
  echo "No staged changes to commit."
else
  git commit -m "initial private ARE Spectacle Gumroad release"
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REPO"
else
  git remote add origin "$REPO"
fi

git push -u origin main
