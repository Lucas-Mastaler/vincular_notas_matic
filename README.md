# Automação de Baixa de Encomendas

Automação Python para baixa de encomendas no SGI com atualização/LOG no Google Sheets e alerta via WhatsApp.

## 📋 Visão Geral

Este projeto automatiza o processo de:
1. Leitura da planilha "PROCESSO ENTRADA" no Google Sheets
2. Seleção de NFs que precisam de tratamento
3. Login no SGI e finalização de entradas
4. Extração de códigos de produtos e quantidades recebidas
5. Baixa automática de reservas/encomendas pendentes
6. Atualização da planilha com status de conclusão
7. Envio de relatório via WhatsApp

## 📁 Estrutura do Projeto

```
.
├── app/
│   ├── __init__.py
│   ├── automacao_baixa_encomendas.py    # Script principal
│   └── creds_loader.py                   # Carregador de credenciais Google
├── creds/                                # Credenciais (não versionado)
│   └── service-account.json             # Arquivo de Service Account do Google
├── downloads/                            # Diretório de downloads (persistente)
├── logs/                                 # Logs da aplicação (persistente)
├── Dockerfile                            # Configuração Docker
├── requirements.txt                      # Dependências Python
├── .env.example                          # Exemplo de variáveis de ambiente
├── .gitignore                            # Arquivos ignorados pelo Git
└── README.md                             # Este arquivo
```

## 🔧 Variáveis de Ambiente

Copie `.env.example` para `.env` e configure:

```bash
# Credenciais SGI
USUARIO_SGI=AUTOMACOES.lebebe
SENHA_SGI=sua_senha_aqui

# Google Sheets
PLANILHA_ID=1Xs-z_LDbB1E-kp9DK-x4-dFkU58xKpYhz038NNrTb54

# Diretórios (já configurados para Docker)
LOGS_DIR=/app/logs
DOWNLOAD_DIR=/app/downloads

# Credenciais Google (preferir arquivo montado)
GOOGLE_SA_JSON_PATH=/app/creds/service-account.json

# Opcional: JSON completo como string (fallback)
GSPREAD_CREDENTIALS=

# Chrome/Chromium
CHROME_BIN=/usr/bin/chromium
CHROME_USER_DIR=/app/chrome-profile
```

## 🐳 Docker

### Build Local

```bash
docker build -t automacao_baixa_encomendas .
```

### Run Local

```bash
docker run --rm -it \
  --env-file .env \
  -v $(pwd)/creds:/app/creds \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/chrome-profile:/app/chrome-profile \
  automacao_baixa_encomendas
```

**Windows (PowerShell):**
```powershell
docker run --rm -it `
  --env-file .env `
  -v ${PWD}/creds:/app/creds `
  -v ${PWD}/logs:/app/logs `
  -v ${PWD}/downloads:/app/downloads `
  -v ${PWD}/chrome-profile:/app/chrome-profile `
  automacao_baixa_encomendas
```

## 🚀 Deploy no EasyPanel

### 1. Preparação

1. Crie um repositório no GitHub e faça push do código
2. Obtenha o arquivo `service-account.json` do Google Cloud Console

### 2. Configuração no EasyPanel

**Source:**
- Type: GitHub
- Repository: `seu-usuario/automacao_baixa_encomendas`
- Branch: `main`
- Build Method: Dockerfile

**Volumes (Mounts):**
```
/app/creds       → Persistente (upload manual do service-account.json)
/app/logs        → Persistente
/app/downloads   → Persistente
/app/chrome-profile → Persistente (opcional, para sessão WhatsApp)
```

**Environment Variables:**
```
USUARIO_SGI=AUTOMACOES.lebebe
SENHA_SGI=sua_senha
PLANILHA_ID=1Xs-z_LDbB1E-kp9DK-x4-dFkU58xKpYhz038NNrTb54
LOGS_DIR=/app/logs
DOWNLOAD_DIR=/app/downloads
GOOGLE_SA_JSON_PATH=/app/creds/service-account.json
CHROME_BIN=/usr/bin/chromium
CHROME_USER_DIR=/app/chrome-profile
```

### 3. Upload de Credenciais

Após criar o serviço:
1. Acesse o volume `/app/creds`
2. Faça upload do arquivo `service-account.json`

### 4. Configurar Cron (Agendamento)

No EasyPanel, configure um Cron Job para executar periodicamente:

**Exemplo: Executar todo dia às 8h (UTC):**
```
0 8 * * * /usr/local/bin/python -u /app/app/automacao_baixa_encomendas.py
```

**Exemplo: Executar de hora em hora:**
```
0 * * * * /usr/local/bin/python -u /app/app/automacao_baixa_encomendas.py
```

⚠️ **Atenção ao fuso horário:** EasyPanel usa UTC. Ajuste conforme necessário.

## 📊 Logs

### Visualizar Logs no EasyPanel
- Acesse a aba **Logs** do serviço para ver output em tempo real

### Logs em Arquivo
- Arquivos salvos em `/app/logs/` com timestamp
- Formato: `baixas_encomendas_YYYY-MM-DD_HH-MM-SS.log`
- Acesse via volume montado

### Logs no Google Sheets
- Aba: **LOGS ENTRADA**
- Colunas: Data/Hora | Processo | Mensagem

## 🔒 Segurança

⚠️ **NUNCA commite credenciais no Git!**

- Arquivo `.gitignore` já protege:
  - `.env`
  - `creds/*`
  - `logs/*`
  - `downloads/*`

- Use volumes do EasyPanel para dados sensíveis
- Credenciais Google: sempre via arquivo montado ou ENV

## 🛠️ Desenvolvimento Local (Opcional)

### Com venv

```bash
# Criar ambiente virtual
python -m venv venv

# Ativar (Linux/Mac)
source venv/bin/activate

# Ativar (Windows)
venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Configurar .env
cp .env.example .env
# Edite .env com suas credenciais

# Executar
python app/automacao_baixa_encomendas.py
```

## 📦 Dependências Principais

- **selenium** - Automação web
- **webdriver-manager** - Gerenciamento de drivers
- **pandas** - Manipulação de dados
- **google-api-python-client** - API Google Sheets
- **gspread** - Cliente Google Sheets
- **oauth2client** - Autenticação Google

## 🐛 Troubleshooting

### Erro: "Credenciais não encontradas"
- Verifique se `service-account.json` está em `/app/creds/`
- Confirme permissões do arquivo
- Valide variável `GOOGLE_SA_JSON_PATH`

### Erro: Selenium/Chrome
- Verifique se `CHROME_BIN` aponta para `/usr/bin/chromium`
- Em ambiente Docker, use `--no-sandbox` e `--disable-dev-shm-usage`

### WhatsApp não envia
- Primeira execução: escanear QR Code manualmente
- Sessão salva em `/app/chrome-profile` (persistir volume)
- Verifique nome do grupo: "AVISOS/GRUPO - POS VENDA"

### Planilha não atualiza
- Verifique permissões do Service Account na planilha
- Confirme `PLANILHA_ID` correto
- Veja logs em `LOGS ENTRADA` na planilha

## 📝 Notas

- Script roda como **job CLI** (não é API/servidor)
- Ideal para execução via Cron
- Logs detalhados em arquivo + console + Sheets
- Retry automático em operações críticas

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

## 📄 Licença

Este projeto é de uso interno da empresa.

---

**Desenvolvido para automação de processos internos**
