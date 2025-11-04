#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
cd /app
python -u app/matic_fluxo_integrado.py
