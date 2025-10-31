#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
# As variáveis vêm do ambiente do container (EasyPanel)
python -u -m app.vincular_notas_entrada_matic
