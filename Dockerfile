# Usa uma imagem oficial e leve do Python
FROM python:3.11-slim

# Evita que a instalação fique travada pedindo confirmações no terminal
ENV DEBIAN_FRONTEND=noninteractive

# Atualizado: Lista exata de pacotes exigidos pelo WeasyPrint nas versões novas do Linux
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    python3-cffi \
    python3-brotli \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    pango1.0-tools \
    shared-mime-info \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Define onde o seu projeto vai morar dentro do container
WORKDIR /app

# Copia e instala as bibliotecas Python (Flask, WeasyPrint, etc)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do código do seu projeto
COPY . .

# Comando que o Render vai usar para iniciar seu servidor Flask
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
