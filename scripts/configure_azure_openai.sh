#!/usr/bin/env bash
set -euo pipefail

ENV_DIR="/home/LuciusPrime/claire/.secrets"
ENV_FILE="${ENV_DIR}/azure_openai.env"
DROPIN_DIR="/etc/systemd/system/claire-gui.service.d"
DROPIN_FILE="${DROPIN_DIR}/azure-openai.conf"

read -r -p "Azure OpenAI endpoint, e.g. https://NAME.openai.azure.com: " endpoint
read -r -p "Azure OpenAI deployment name: " deployment
read -r -p "Azure OpenAI API version [2024-02-15-preview]: " api_version
api_version="${api_version:-2024-02-15-preview}"
read -r -s -p "Azure OpenAI API key: " api_key
printf "\n"

if [[ -z "${endpoint}" || -z "${deployment}" || -z "${api_version}" || -z "${api_key}" ]]; then
  echo "Missing required value. Nothing changed." >&2
  exit 1
fi

sudo mkdir -p "${ENV_DIR}"
sudo chmod 700 "${ENV_DIR}"

tmp_file="$(mktemp)"
cat > "${tmp_file}" <<EOF
CLAIRE_MODEL_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=${endpoint}
AZURE_OPENAI_DEPLOYMENT=${deployment}
AZURE_OPENAI_API_VERSION=${api_version}
AZURE_OPENAI_API_KEY=${api_key}
EOF

sudo install -m 600 "${tmp_file}" "${ENV_FILE}"
rm -f "${tmp_file}"

sudo mkdir -p "${DROPIN_DIR}"
dropin_tmp="$(mktemp)"
cat > "${dropin_tmp}" <<EOF
[Service]
EnvironmentFile=${ENV_FILE}
EOF
sudo install -m 644 "${dropin_tmp}" "${DROPIN_FILE}"
rm -f "${dropin_tmp}"

sudo systemctl daemon-reload
sudo systemctl restart claire-gui

echo "Azure OpenAI provider configured for claire-gui."
echo "Check: curl -sS http://127.0.0.1:8000/status"
