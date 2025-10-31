# 🚀 Instruções de Deploy

## ✅ Repositório Preparado!

O repositório foi inicializado com sucesso e está pronto para deploy no EasyPanel.

## 📤 Push para GitHub

### 1. Criar Repositório no GitHub

Acesse https://github.com/new e crie um novo repositório:
- **Nome:** `automacao_baixa_encomendas`
- **Visibilidade:** Private (recomendado)
- **NÃO** inicialize com README, .gitignore ou licença

### 2. Conectar e Fazer Push

Execute os comandos abaixo no terminal:

```bash
git remote add origin https://github.com/SEU-USUARIO/automacao_baixa_encomendas.git
git branch -M main
git push -u origin main
```

**Substitua `SEU-USUARIO` pelo seu username do GitHub!**

## 🐳 Teste Docker Local (Opcional)

Antes de fazer deploy, teste localmente:

### 1. Preparar Credenciais

```bash
# Criar diretório de credenciais
mkdir creds

# Copiar seu service-account.json para creds/
# (obtenha do Google Cloud Console)
```

### 2. Configurar .env

```bash
# Copiar exemplo
cp .env.example .env

# Editar .env com suas credenciais reais
notepad .env  # ou seu editor preferido
```

### 3. Build e Run

```bash
# Build da imagem
docker build -t automacao_baixa_encomendas .

# Executar
docker run --rm -it \
  --env-file .env \
  -v ${PWD}/creds:/app/creds \
  -v ${PWD}/logs:/app/logs \
  -v ${PWD}/downloads:/app/downloads \
  automacao_baixa_encomendas
```

**Windows (PowerShell):**
```powershell
docker run --rm -it `
  --env-file .env `
  -v ${PWD}/creds:/app/creds `
  -v ${PWD}/logs:/app/logs `
  -v ${PWD}/downloads:/app/downloads `
  automacao_baixa_encomendas
```

## 🎯 Deploy no EasyPanel

### 1. Criar Novo Serviço

1. Acesse seu painel EasyPanel
2. Clique em **"New Service"**
3. Selecione **"From GitHub"**

### 2. Configurar Source

- **Repository:** `seu-usuario/automacao_baixa_encomendas`
- **Branch:** `main`
- **Build Method:** `Dockerfile`

### 3. Configurar Volumes

Crie os seguintes volumes persistentes:

| Mount Path | Descrição |
|------------|-----------|
| `/app/creds` | Credenciais Google (upload manual) |
| `/app/logs` | Logs da aplicação |
| `/app/downloads` | Downloads temporários |
| `/app/chrome-profile` | Sessão WhatsApp (opcional) |

### 4. Configurar Environment Variables

Adicione as seguintes variáveis:

```
USUARIO_SGI=AUTOMACOES.lebebe
SENHA_SGI=sua_senha_aqui
PLANILHA_ID=1Xs-z_LDbB1E-kp9DK-x4-dFkU58xKpYhz038NNrTb54
LOGS_DIR=/app/logs
DOWNLOAD_DIR=/app/downloads
GOOGLE_SA_JSON_PATH=/app/creds/service-account.json
CHROME_BIN=/usr/bin/chromium
CHROME_USER_DIR=/app/chrome-profile
```

### 5. Upload de Credenciais

**IMPORTANTE:** Após criar o serviço:

1. Acesse o volume `/app/creds`
2. Faça upload do arquivo `service-account.json`
3. Verifique permissões do arquivo

### 6. Configurar Cron Job

Para executar automaticamente:

**Exemplo 1: Todo dia às 8h (UTC)**
```
0 8 * * * /usr/local/bin/python -u /app/app/automacao_baixa_encomendas.py
```

**Exemplo 2: A cada 2 horas**
```
0 */2 * * * /usr/local/bin/python -u /app/app/automacao_baixa_encomendas.py
```

**Exemplo 3: Segunda a Sexta às 9h e 15h (UTC)**
```
0 9,15 * * 1-5 /usr/local/bin/python -u /app/app/automacao_baixa_encomendas.py
```

⚠️ **Atenção:** EasyPanel usa fuso horário UTC. Ajuste conforme necessário.

### 7. Primeira Execução (WhatsApp)

Na primeira vez que o script tentar enviar mensagem no WhatsApp:

1. Acesse os logs do container
2. Aguarde aparecer o QR Code (ou mensagem para escanear)
3. Escaneie com WhatsApp no celular
4. A sessão será salva em `/app/chrome-profile`

## 📊 Monitoramento

### Logs em Tempo Real
```bash
# No EasyPanel, acesse a aba "Logs" do serviço
```

### Logs em Arquivo
- Acessar volume `/app/logs`
- Arquivos: `baixas_encomendas_YYYY-MM-DD_HH-MM-SS.log`

### Logs no Google Sheets
- Planilha: ID configurado em `PLANILHA_ID`
- Aba: **LOGS ENTRADA**

## 🔧 Troubleshooting

### Erro: "Credenciais não encontradas"
```bash
# Verificar se arquivo existe no volume
ls -la /app/creds/service-account.json

# Verificar permissões
chmod 644 /app/creds/service-account.json
```

### Erro: Chrome/Chromium
```bash
# Verificar instalação
which chromium
chromium --version

# Testar com headless
# Adicionar ENV: HEADLESS=true
```

### Planilha não atualiza
1. Verifique se Service Account tem permissão na planilha
2. Compartilhe planilha com email do Service Account
3. Confirme `PLANILHA_ID` correto

## 📝 Checklist de Deploy

- [ ] Repositório criado no GitHub
- [ ] Push realizado com sucesso
- [ ] Service Account JSON obtido
- [ ] Serviço criado no EasyPanel
- [ ] Volumes configurados
- [ ] Environment variables definidas
- [ ] Credenciais uploaded
- [ ] Cron job configurado
- [ ] Primeira execução testada
- [ ] WhatsApp autenticado (se necessário)
- [ ] Logs verificados

## 🎉 Pronto!

Seu serviço está configurado e rodando no EasyPanel!

Para dúvidas, consulte o **README.md** principal.

---

**Data de criação:** $(Get-Date -Format "dd/MM/yyyy HH:mm")
**Commit inicial:** b243051
