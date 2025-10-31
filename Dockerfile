FROM python:3.11-slim

# 1) Chrome + Chromedriver + cron
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-liberation \
    ca-certificates \
    curl \
    unzip \
    cron \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) Dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) Código
COPY app/ ./app

# 3.1) Normaliza LF e dá permissão no run-once
RUN sed -i 's/\r$//' /app/app/run-once.sh && chmod +x /app/app/run-once.sh

# 4) Pastas
RUN mkdir -p /app/logs /app/creds /app/downloads /app/chrome-profile

# 5) Ambiente padrão (pode ser sobrescrito no painel)
ENV PYTHONUNBUFFERED=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_BIN=/usr/bin/chromedriver \
    CHROME_USER_DIR_BASE=/app/chrome-profile \
    GOOGLE_SA_JSON_PATH=/app/creds/service-account.json \
    LOGS_DIR=/app/logs \
    DOWNLOAD_DIR=/app/downloads \
    TZ=America/Sao_Paulo

# 6) Cron job: a cada 30 min das 07h às 19h BRT
RUN printf "SHELL=/bin/bash\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\nTZ=America/Sao_Paulo\n\n" > /etc/cron.d/vincular-notas \
 && echo '*/30 7-19 * * * root cd /app && flock -n /app/.lock bash /app/app/run-once.sh >> /app/logs/cron.log 2>&1' >> /etc/cron.d/vincular-notas \
 && chmod 0644 /etc/cron.d/vincular-notas

# 7) Mantém cron em foreground
CMD ["cron", "-f"]
