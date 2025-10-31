# -*- coding: utf-8 -*-
"""
creds_loader.py
Carrega credenciais do Google Service Account de forma flexível:
1) Arquivo montado em /app/creds/service-account.json (preferido)
2) Variável de ambiente GSPREAD_CREDENTIALS com JSON completo (fallback)
"""
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

def load_gspread_client():
    """
    Retorna um cliente gspread autenticado.
    Levanta RuntimeError se não encontrar credenciais.
    """
    # 1) Tenta arquivo montado
    json_path = os.getenv("GOOGLE_SA_JSON_PATH", "/app/creds/service-account.json")
    if os.path.exists(json_path) and os.path.isfile(json_path):
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, SCOPES)
        return gspread.authorize(creds)
    
    # 2) Tenta ENV com JSON string
    raw = os.getenv("GSPREAD_CREDENTIALS", "").strip()
    if raw:
        creds_dict = json.loads(raw)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
        return gspread.authorize(creds)
    
    raise RuntimeError(
        "Credenciais não encontradas. "
        "Monte /app/creds/service-account.json ou defina GSPREAD_CREDENTIALS."
    )
