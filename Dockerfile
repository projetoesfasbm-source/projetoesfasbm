# 1. Usa uma versão oficial e leve do Python
FROM python:3.11-slim

# 2. Define a pasta de trabalho lá dentro do servidor
WORKDIR /app

# 3. Atualiza o Linux e instala as dependências gráficas cruciais para o WeasyPrint
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    python3-cffi \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# 4. Copia APENAS o arquivo de bibliotecas primeiro (isso acelera os próximos deploys)
COPY requirements.txt .

# 5. Instala as bibliotecas do Python (Flask, WeasyPrint, etc.)
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copia o restante do código da sua arquitetura para dentro do servidor
COPY . .

# 7. Expõe a porta de comunicação (O Render gosta de usar a porta 10000 ou 8000)
EXPOSE 10000

# 8. Comando para rodar a aplicação em PRODUÇÃO com Gunicorn
# ATENÇÃO: Substitua 'app:app' pelo nome do arquivo que inicia seu projeto e a variável da aplicação.
# Exemplo: se a aplicação inicia no arquivo 'run.py' e a variável Flask se chama 'sistema', ficará 'run:sistema'
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
