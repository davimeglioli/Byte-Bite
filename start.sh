#!/bin/bash

# Attiva l'ambiente virtuale se esiste (opzionale, decommenta se usi venv)
# source venv/bin/activate

# Avvia Gunicorn
# -w 4: usa 4 worker (processi) per gestire le richieste in parallelo
# -b 0.0.0.0:8000: ascolta su tutte le interfacce alla porta 8000
# app:app : cerca l'oggetto 'app' dentro il file 'app.py'
# --worker-class gthread --threads 4: necessario per supportare SocketIO/WebSocket con Flask in modo stabile

echo "Avvio Byte-Bite Server in modalità PRODUZIONE..."
exec gunicorn -w 1 --threads 100 --worker-class gthread -b 0.0.0.0:8000 app:app
