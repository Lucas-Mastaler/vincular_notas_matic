# -*- coding: utf-8 -*-
"""
google_sheets_auth.py
Carrega credenciais do Google Service Account de forma flexível:
1) JSON inline via GOOGLE_SA_JSON
2) JSON base64 via GOOGLE_SA_JSON_B64
3) Arquivo via GOOGLE_SA_JSON_PATH (padrão: /app/creds/service-account.json)
"""
import os
import json
import base64
from google.oauth2 import service_account
from googleapiclient.discovery import build


def load_sa_credentials(scopes: list):
    """
    Carrega credenciais do Service Account a partir de variáveis de ambiente.
    Prioridade: GOOGLE_SA_JSON > GOOGLE_SA_JSON_B64 > GOOGLE_SA_JSON_PATH
    """
    # 1) Tenta JSON inline
    raw = os.environ.get("GOOGLE_SA_JSON")
    if raw:
        info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)

    # 2) Tenta JSON base64
    b64 = os.environ.get("GOOGLE_SA_JSON_B64")
    if b64:
        info = json.loads(base64.b64decode(b64).decode("utf-8"))
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)

    # 3) Tenta arquivo
    path = os.environ.get("GOOGLE_SA_JSON_PATH", "/app/creds/service-account.json")
    if not os.path.exists(path):
        raise RuntimeError(
            f"Credenciais não encontradas. "
            f"Defina GOOGLE_SA_JSON, GOOGLE_SA_JSON_B64 ou monte o arquivo em {path}"
        )
    return service_account.Credentials.from_service_account_file(path, scopes=scopes)


def values_api(creds):
    """Retorna a API de values do Google Sheets."""
    return build("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets().values()


def sheets_api(creds):
    """Retorna a API completa do Google Sheets."""
    return build("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets()
