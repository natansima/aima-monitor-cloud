FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Copiar arquivos
COPY requirements.txt .
COPY aima_monitor.py .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Criar diretório de dados
RUN mkdir -p /app/data

# Variáveis de ambiente para Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

CMD ["python", "aima_monitor.py"]
