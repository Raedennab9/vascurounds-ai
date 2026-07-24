#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${script_dir}/.." && pwd)"
cd "${repository_root}"

export DATAHUB_MODE="${DATAHUB_MODE:-real}"
export DATAHUB_REQUIRED="${DATAHUB_REQUIRED:-true}"
export DATAHUB_GMS_URL="${DATAHUB_GMS_URL:-http://localhost:8080}"

python3 scripts/check_datahub.py

printf '%s\n' \
  "DataHub validation passed. Starting VascuRounds AI." \
  "In the Codespace Ports panel, make port 8501 Public." \
  "Port 8080 may remain private; port 9002 is the DataHub UI when needed."

exec python3 -m streamlit run app.py \
  --server.address 0.0.0.0 \
  --server.port 8501
