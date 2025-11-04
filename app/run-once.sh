#!/bin/bash
set -euo pipefail

# carimbo de debug das ENVs principais
{
  echo "==== $(date '+%Y-%m-%d %H:%M:%S') :: RUN ===="
  echo "PLANILHA_ID=${PLANILHA_ID:-<vazio>}"
  echo "ABA_CONTROLE=${ABA_CONTROLE:-<vazio>}"
  echo "ID_PASTA_GOOGLE_DRIVE=${ID_PASTA_GOOGLE_DRIVE:-<vazio>}"
} >> /app/logs/cron.log 2>&1

# executa o script certo
exec python3 /app/app/vincular_notas_entrada_matic.py >> /app/logs/cron.log 2>&1
