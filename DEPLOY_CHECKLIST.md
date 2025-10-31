# Checklist de Deploy - VINCULAR NOTAS ENTRADA MATIC

## ✅ Estrutura do Projeto

```
/app
  ├─ app/
  │   ├─ __init__.py                      ✅ Existe
  │   ├─ vincular_notas_entrada_matic.py  ✅ Refatorado para ENV
  │   ├─ google_sheets_auth.py            ✅ Criado
  │   ├─ run-once.sh                      ✅ Criado (LF + chmod +x)
  │   └─ creds_loader.py                  ⚠️  Legado (não usado)
  ├─ requirements.txt                     ✅ Atualizado
  ├─ .env.example                         ✅ Completo
  └─ Dockerfile                           ✅ Com cron configurado
```

## ✅ Arquivos Criados/Atualizados

### 1. `requirements.txt`
- ✅ Removido `webdriver-manager`
- ✅ Adicionado `packaging`, `tabulate`, `loguru`, `beautifulsoup4`, `python-dotenv`, `requests`
- ✅ Mantido `selenium`, `google-api-python-client`, `google-auth`, `gspread`, `oauth2client`, `pandas`, `openpyxl`

### 2. `app/google_sheets_auth.py`
- ✅ Suporta 3 métodos de credenciais:
  - `GOOGLE_SA_JSON` (JSON inline)
  - `GOOGLE_SA_JSON_B64` (JSON base64)
  - `GOOGLE_SA_JSON_PATH` (arquivo)
- ✅ Funções: `load_sa_credentials()`, `values_api()`, `sheets_api()`

### 3. `app/run-once.sh`
- ✅ Shebang: `#!/usr/bin/env bash`
- ✅ Flags: `set -euo pipefail`
- ✅ Comando: `python -u -m app.vincular_notas_entrada_matic`
- ✅ Será normalizado para LF pelo Dockerfile

### 4. `Dockerfile`
- ✅ Base: `python:3.11-slim`
- ✅ Instalado: `chromium`, `chromium-driver`, `cron`
- ✅ Normaliza LF do `run-once.sh`: `sed -i 's/\r$//'`
- ✅ Permissão: `chmod +x /app/app/run-once.sh`
- ✅ Cron job: `*/30 7-19 * * *` (a cada 30 min, 7h-19h BRT)
- ✅ Flock: evita execuções simultâneas
- ✅ CMD: `cron -f` (foreground)

### 5. `.env.example`
- ✅ `SGI_USERNAME` / `SGI_PASSWORD`
- ✅ `PLANILHA_ID`, `ABA_CONTROLE`, `ID_PASTA_GOOGLE_DRIVE`
- ✅ `GOOGLE_SA_JSON_PATH` (+ alternativas comentadas)
- ✅ `LOGS_DIR`, `DOWNLOAD_DIR`
- ✅ `CHROME_BIN`, `CHROMEDRIVER_BIN`, `CHROME_USER_DIR_BASE`
- ✅ `TZ=America/Sao_Paulo`

### 6. `app/vincular_notas_entrada_matic.py`
- ✅ Removidos todos os caminhos Windows (`C:\Users\...`)
- ✅ Credenciais via `os.environ.get("SGI_USERNAME")` / `SGI_PASSWORD`
- ✅ Paths via `LOGS_DIR`, `DOWNLOAD_DIR`, `PASTA_LOCAL_XML`
- ✅ Google Sheets: usa `app.google_sheets_auth.load_sa_credentials()`
- ✅ Driver: usa `CHROME_BIN`, `CHROMEDRIVER_BIN`, `CHROME_USER_DIR_BASE`
- ✅ Perfil único por execução (evita "user data dir in use")
- ✅ WhatsApp desabilitado (requer perfil persistente + QR scan)
- ✅ Logs: registra início/fim da execução

## 🔧 Variáveis de Ambiente (EasyPanel)

Configure no painel da VPS:

```bash
# SGI
SGI_USERNAME=AUTOMACOES.lebebe
SGI_PASSWORD=sua_senha_aqui

# Google Sheets/Drive
PLANILHA_ID=1Xs-z_LDbB1E-kp9DK-x4-dFkU58xKpYhz038NNrTb54
ABA_CONTROLE=PROCESSO ENTRADA
ID_PASTA_GOOGLE_DRIVE=1tCYuAqkvgqkFyPJreuInc_Erd-Z1pSJV

# Service Account (escolha um método)
# Método 1: Montar arquivo
GOOGLE_SA_JSON_PATH=/app/creds/service-account.json

# Método 2: JSON inline (alternativa)
# GOOGLE_SA_JSON={"type":"service_account",...}

# Método 3: Base64 (alternativa)
# GOOGLE_SA_JSON_B64=eyJ0eXBlIjoic2VydmljZV9hY2NvdW50Ii...

# Paths (já configurados no Dockerfile, mas podem ser sobrescritos)
LOGS_DIR=/app/logs
DOWNLOAD_DIR=/app/downloads
CHROME_USER_DIR_BASE=/app/chrome-profile

# Chromium (já configurados no Dockerfile)
CHROME_BIN=/usr/bin/chromium
CHROMEDRIVER_BIN=/usr/bin/chromedriver

# Timezone
TZ=America/Sao_Paulo
```

## 🧪 Testes Dentro do Container

Após deploy, acesse o container e teste:

```bash
# 1. Teste direto
python -u -m app.vincular_notas_entrada_matic

# 2. Teste como o cron executaria
cd /app && flock -n /app/.lock bash /app/app/run-once.sh >> /app/logs/cron.log 2>&1

# 3. Ver logs do cron
tail -n 200 /app/logs/cron.log

# 4. Ver cron configurado
cat /etc/cron.d/vincular-notas
crontab -l  # (pode estar vazio se usar /etc/cron.d)

# 5. Verificar processo cron
ps aux | grep "[c]ron -f"

# 6. Ver logs individuais
ls -lh /app/logs/
tail -f /app/logs/log_*.txt
```

## 📋 Checklist Final

- [ ] `app/__init__.py` existe (módulo importável)
- [ ] `run-once.sh` com permissão de execução
- [ ] `requirements.txt` tem `packaging`
- [ ] Sem `webdriver-manager` no requirements
- [ ] Sem caminhos Windows no código
- [ ] Variáveis configuradas no painel EasyPanel
- [ ] Service Account JSON montado em `/app/creds/service-account.json` OU configurado via ENV
- [ ] `cron.log` mostra execuções a cada 30 min
- [ ] Logs individuais em `/app/logs/log_*.txt`
- [ ] XMLs baixados em `/app/downloads/xml/`

## 🚀 Comandos de Deploy

```bash
# Build local (teste)
docker build -t vincular-notas .

# Run local (teste)
docker run --rm \
  -e SGI_USERNAME=AUTOMACOES.lebebe \
  -e SGI_PASSWORD=sua_senha \
  -e PLANILHA_ID=1Xs-z_LDbB1E-kp9DK-x4-dFkU58xKpYhz038NNrTb54 \
  -e ID_PASTA_GOOGLE_DRIVE=1tCYuAqkvgqkFyPJreuInc_Erd-Z1pSJV \
  -v /caminho/local/service-account.json:/app/creds/service-account.json \
  vincular-notas

# Deploy no EasyPanel
# 1. Fazer push para repositório Git
# 2. Conectar repositório no EasyPanel
# 3. Configurar variáveis de ambiente
# 4. Montar service-account.json como secret/volume
# 5. Deploy!
```

## 📝 Commits Sugeridos

```bash
git add .
git commit -m "feat(container): chromium + cron + run-once for vincular_notas_entrada_matic"
git commit -m "chore(env): add .env.example and move IDs/creds to env"
git commit -m "fix(reqs): add packaging and drop webdriver-manager"
git commit -m "refactor(paths): use LOGS_DIR/DOWNLOAD_DIR and ensure dirs"
```

## ⚠️ Notas Importantes

1. **WhatsApp desabilitado**: Notificações via WhatsApp foram desabilitadas pois requerem perfil persistente do Chrome e scan de QR code. Os relatórios são registrados nos logs.

2. **Perfil único do Chrome**: Cada execução cria um perfil temporário único em `/app/chrome-profile/run_*` para evitar conflitos de "user data dir in use".

3. **Flock**: O cron usa `flock -n /app/.lock` para garantir que apenas uma instância rode por vez.

4. **Timezone**: Configurado para `America/Sao_Paulo` (BRT) no cron e no container.

5. **Logs**: Cada execução gera um arquivo de log individual em `/app/logs/log_YYYY-MM-DD_HH-MM-SS.txt`, além do `cron.log` consolidado.

6. **Credenciais**: Prefira montar o arquivo JSON como volume/secret no EasyPanel. As alternativas (ENV inline/base64) são para casos específicos.
