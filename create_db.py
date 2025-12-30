import sqlite3 as sq

# Percorso del database locale.
PERCORSO_DB = "db.sqlite3"
# Percorso del file schema SQL.
PERCORSO_SCHEMA = "db.sql"


def crea_database(percorso_db=PERCORSO_DB, percorso_schema=PERCORSO_SCHEMA):
    # Apre connessione al database SQLite (crea il file se non esiste).
    connessione = sq.connect(percorso_db)
    try:
        # Legge lo schema dal file e lo esegue.
        with open(percorso_schema, "r") as file_schema:
            schema = file_schema.read()
        connessione.executescript(schema)
    finally:
        # Chiude sempre la connessione.
        connessione.close()


if __name__ == "__main__":
    crea_database()
