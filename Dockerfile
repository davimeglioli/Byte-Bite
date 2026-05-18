FROM python:3.11-slim

WORKDIR /app

# Installa dipendenze di sistema (per PostgreSQL e gevent)
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e installa dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il resto dell'app
COPY . .

# Espone la porta
EXPOSE 8000

# Inizializza il database, poi avvia l'app
CMD python scripts/create_db.py && python run.py
