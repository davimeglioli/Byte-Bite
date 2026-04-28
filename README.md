# Byte-Bite

Sistema di gestione ordini per ristoranti. La **cassa** crea gli ordini, le **dashboard** (cucina, bar, ecc.) seguono la preparazione in tempo reale, il pannello **admin** gestisce prodotti, ordini e utenti.

---

## Avvio con Docker

```bash
docker compose up --build
```

Al primo avvio crea automaticamente lo schema e un utente `admin` / `admin`.

Apri [http://localhost:8000](http://localhost:8000).

---

## Avvio senza Docker

```bash
pip install -r requirements.txt
python create_db.py   # crea schema e dati di default
python app.py
```

---

## Variabili d'ambiente

Crea un file `.env` nella root del progetto:

```env
DB_HOST = localhost
DB_PORT = 5432
DB_NAME = byte-bite
DB_USER = byte-bite-user
DB_PASSWORD = <password>
SECRET_KEY = <stringa-casuale-lunga>
DEBUG = false
LOG_LEVEL = INFO
```

In produzione cambia **obbligatoriamente** `DB_PASSWORD` e `SECRET_KEY`.

---

## Credenziali di default

| Username | Password | Ruolo |
|----------|----------|-------|
| `admin` | `admin` | Amministratore |

Cambia la password dopo il primo accesso.
