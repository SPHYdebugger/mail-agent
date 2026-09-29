#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/santiago/.nvm/versions/node/v24.21.0/bin:${PATH}"

LOCK_FILE="/home/santiago/mail-agent/data/poll-once.lock"
PYTHON="/home/santiago/mail-agent/.venv-gmail-readonly/bin/python"
SOURCE="/home/santiago/mail-agent/gmail_readonly/src"
CLIENT_SECRETS="/home/santiago/.local/state/mail-agent/gmail/client_secret.json"
TOKEN_PATH="/home/santiago/.local/state/mail-agent/gmail/token.json"
ACCOUNT="santiagoperez.developer@gmail.com"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
    exit 0
fi

env PYTHONPATH="${SOURCE}" "${PYTHON}" -m gmail_readonly.cli poll-once \
    --account "${ACCOUNT}" \
    --client-secrets "${CLIENT_SECRETS}" \
    --token-path "${TOKEN_PATH}" \
    --max-results 25

exec env PYTHONPATH="${SOURCE}" "${PYTHON}" -m gmail_readonly.cli \
    send-notifications-once
