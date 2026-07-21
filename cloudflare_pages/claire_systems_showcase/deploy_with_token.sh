#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/LuciusPrime/claire/cloudflare_pages/claire_systems_showcase"
PROJECT_NAME="claire-systems-showcase"

printf "Cloudflare API token for Pages deploy (input hidden): "
stty -echo
read -r CLOUDFLARE_API_TOKEN
stty echo
printf "\n"

if [ -z "${CLOUDFLARE_API_TOKEN}" ]; then
  echo "No token entered. Deploy aborted."
  exit 1
fi

export CLOUDFLARE_API_TOKEN
cd "${PROJECT_DIR}"

CI=1 npx wrangler@3.114.14 pages deploy . \
  --project-name "${PROJECT_NAME}" \
  --commit-dirty=true

unset CLOUDFLARE_API_TOKEN
