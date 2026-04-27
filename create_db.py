"""
Script per inizializzare il database (SQLite o PostgreSQL a seconda dell'ambiente).
Crea lo schema leggendo da db.sql, poi inserisce utente admin e prodotti di default.
"""
import os
import sqlite3 as sq
import psycopg2
import bcrypt

# Variabili di ambiente per PostgreSQL
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

PERCORSO_SCHEMA = "db.sql"

PRODOTTI_DEFAULT = [
    # (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti)
    # APERITIVI
    ('Spritz Aperol',               4,    'Aperitivi',        'Bar',        True, 100, 0),
    ('Spritz Campari',              4,    'Aperitivi',        'Bar',        True, 100, 0),
    ('Spritz Hugo',                 4,    'Aperitivi',        'Bar',        True, 100, 0),
    ('Analcolico',                  4,    'Aperitivi',        'Bar',        True, 100, 0),
    # PAELLA
    ('Menu Completo: Antipasto - Paella - Dolce', 25, 'Paella', 'Cucina',   True, 100, 0),
    # PRIMI
    ('Tortelli Verdi Vecchia Modena',  9.5, 'Primi',          'Cucina',     True, 100, 0),
    ('Tortelli Verdi Burro e Salvia',  9,   'Primi',          'Cucina',     True, 100, 0),
    ("Riso Venere dell'Orto",          8,   'Primi',          'Cucina',     True, 100, 0),
    ('Garganelli al Ragù di Carne',    8,   'Primi',          'Cucina',     True, 100, 0),
    # SECONDI
    ('Picanha ai Ferri',            16.5, 'Secondi',          'Griglia',    True, 100, 0),
    ('Grigliata Mista di Carne',    12,   'Secondi',          'Griglia',    True, 100, 0),
    ('Salsiccia, Wurstel e Patatine', 8.5, 'Secondi',         'Griglia',    True, 100, 0),
    ('Caprese',                      8,   'Secondi',          'Griglia',    True, 100, 0),
    ('Fritto Misto di Pesce',       12.5, 'Secondi',          'Griglia',    True, 100, 0),
    ('Patatine Fritte',              3,   'Secondi',          'Gnoccheria', True, 100, 0),
    ('Misticanza',                   3,   'Secondi',          'Gnoccheria', True, 100, 0),
    # GNOCCO E TIGELLE
    ('Gnocco Fritto Vuoto',          0.6, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Gnocco Fritto con Prosciutto Cotto',  3.5, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Gnocco Fritto con Prosciutto Crudo',  3.5, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Gnocco Fritto con Salame',     3.5, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Gnocco Fritto con Coppa',      3.5, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Tigella Semplice',             0.6, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Tigella con Prosciutto Cotto', 2.5, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Tigella con Prosciutto Crudo', 2.5, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Tigella con Salame',           2.5, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Tigella con Coppa',            2.5, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Piatto Affettato Misto',       7,   'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Piatto Prosciutto Crudo',      8,   'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Stracchino e Rucola',          2.5, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Nutella',                      1,   'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Lardo',                        1.5, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Parmigiano',                   1.5, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Lardo e Parmigiano',           2.5, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    ('Maionese/ Ketchup',            0.5, 'Gnocco e Tigelle', 'Gnoccheria', True, 100, 0),
    # DA BERE
    ('Acqua Naturale 0,5L',          1.0, 'Da Bere', 'Bar', True, 100, 0),
    ('Acqua Naturale 1,5L',          2.0, 'Da Bere', 'Bar', True, 100, 0),
    ('Acqua Frizzante 0,5L',         1.0, 'Da Bere', 'Bar', True, 100, 0),
    ('Acqua Frizzante 1,5L',         1.0, 'Da Bere', 'Bar', True, 100, 0),
    ('Birra Spina Piccola',          2,   'Da Bere', 'Bar', True, 100, 0),
    ('Birra Spina Media',            3.5, 'Da Bere', 'Bar', True, 100, 0),
    ('Birra Spina Weiss Piccola',    3,   'Da Bere', 'Bar', True, 100, 0),
    ('Birra Spina Weiss Media',      4.5, 'Da Bere', 'Bar', True, 100, 0),
    ('Coca Cola Spina Piccola',      2,   'Da Bere', 'Bar', True, 100, 0),
    ('Coca Cola Spina Media',        3.5, 'Da Bere', 'Bar', True, 100, 0),
    ('Coca Cola in lattina',         2.5, 'Da Bere', 'Bar', True, 100, 0),
    ('Fanta in lattina',             2.5, 'Da Bere', 'Bar', True, 100, 0),
    ('Lambrusco Bottiglia 0,75L',    6,   'Da Bere', 'Bar', True, 100, 0),
    ('Vino Bianco Bicchiere',        1.5, 'Da Bere', 'Bar', True, 100, 0),
    ('Vino Bianco Caraffa 0,50L',    4,   'Da Bere', 'Bar', True, 100, 0),
    ('Vino Bianco Caraffa 1L',       6.5, 'Da Bere', 'Bar', True, 100, 0),
    # DOLCI
    ('Tiramisù',                     4,   'Dolci', 'Bar', True, 100, 0),
    ('Zuppa Inglese',                4,   'Dolci', 'Bar', True, 100, 0),
    ('Cheescake ai Frutti di Bosco', 4,   'Dolci', 'Bar', True, 100, 0),
    ('Sorbetto al Limone',           3,   'Dolci', 'Bar', True, 100, 0),
    ('Caffè',                        1,   'Dolci', 'Bar', True, 100, 0),
    ('Caffè Corretto',               2,   'Dolci', 'Bar', True, 100, 0),
    ('Limoncino',                    3,   'Dolci', 'Bar', True, 100, 0),
    ('Nocino',                       3,   'Dolci', 'Bar', True, 100, 0),
    ('Amaro del Capo',               3,   'Dolci', 'Bar', True, 100, 0),
    ('Montenegro',                   3,   'Dolci', 'Bar', True, 100, 0),
    ('Grappa',                       3,   'Dolci', 'Bar', True, 100, 0),
    # LONG DRINK
    ('Gin Tonic',                    5,   'Long Drink', 'Bar', True, 100, 0),
    ('Gin Tonic Premium',            8,   'Long Drink', 'Bar', True, 100, 0),
    ('Gin Lemon',                    5,   'Long Drink', 'Bar', True, 100, 0),
    ('Vodka Tonic',                  5,   'Long Drink', 'Bar', True, 100, 0),
    ('Vodka Lemon',                  5,   'Long Drink', 'Bar', True, 100, 0),
    ('Vodka & Fruit',                5,   'Long Drink', 'Bar', True, 100, 0),
    ('Rum e Cola',                   5,   'Long Drink', 'Bar', True, 100, 0),
    ('Malibu e Cola',                5,   'Long Drink', 'Bar', True, 100, 0),
    ('Mojito',                       6,   'Long Drink', 'Bar', True, 100, 0),
    ('Barbie Mojito',                6,   'Long Drink', 'Bar', True, 100, 0),
    ('Cuba Libre',                   6,   'Long Drink', 'Bar', True, 100, 0),
    ('Caipiroska Fragola',           6,   'Long Drink', 'Bar', True, 100, 0),
    # SHORT DRINK
    ('Negroni',                      4,   'Short Drink', 'Bar', True, 100, 0),
    ('Americano',                    4,   'Short Drink', 'Bar', True, 100, 0),
]


def _inserisci_dati_default_postgres(connessione):
    """Inserisce utente admin e prodotti di default se non esistono già."""
    cursore = connessione.cursor()

    # Utente admin (idempotente: salta se esiste già)
    cursore.execute("SELECT 1 FROM utenti WHERE username = 'admin'")
    if not cursore.fetchone():
        password_hash = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("admin", password_hash, True, True),
        )
        id_admin = cursore.fetchone()[0]
        for pagina in ("CASSA", "AMMINISTRAZIONE", "DASHBOARD"):
            cursore.execute(
                "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
                (id_admin, pagina),
            )
        print("   ✅ Utente admin creato (username: admin, password: admin)")
    else:
        print("   ℹ️  Utente admin già presente, skip.")

    # Prodotti (idempotente: inserisce solo se la tabella è vuota)
    cursore.execute("SELECT COUNT(*) FROM prodotti")
    if cursore.fetchone()[0] == 0:
        cursore.executemany(
            "INSERT INTO prodotti"
            " (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            PRODOTTI_DEFAULT,
        )
        print(f"   ✅ Inseriti {len(PRODOTTI_DEFAULT)} prodotti di default.")
    else:
        print("   ℹ️  Prodotti già presenti, skip.")

    connessione.commit()


def crea_schema_sqlite():
    """Crea lo schema in SQLite (per sviluppo locale)."""
    percorso_db = "db.sqlite3"
    print(f"📂 Creazione database SQLite: {percorso_db}")

    try:
        connessione = sq.connect(percorso_db)
        with open(PERCORSO_SCHEMA, "r") as file_schema:
            schema = file_schema.read()
        connessione.executescript(schema)
        connessione.close()
        print("✅ Schema SQLite creato con successo!")
    except Exception as e:
        print(f"❌ Errore nella creazione dello schema SQLite: {e}")


def crea_schema_postgres():
    """Crea lo schema in PostgreSQL (per Docker/produzione)."""
    print("📂 Creazione schema PostgreSQL")

    connessione_postgres = None
    try:
        connessione_postgres = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            connect_timeout=30,
        )
        cursore = connessione_postgres.cursor()

        with open(PERCORSO_SCHEMA, "r") as file_schema:
            schema = file_schema.read()

        lista_query = []
        query_corrente = []

        for riga in schema.split('\n'):
            if '--' in riga:
                riga = riga[:riga.index('--')]
            riga = riga.strip()
            if riga:
                query_corrente.append(riga)
            if ';' in riga:
                query = ' '.join(query_corrente)
                lista_query.append(query.replace(';', '').strip())
                query_corrente = []

        for i, query in enumerate(lista_query):
            if query:
                try:
                    cursore.execute(query)
                    print(f"   ✅ Query {i+1}/{len(lista_query)} eseguita")
                except Exception as e:
                    print(f"   ⚠️  Query {i+1}: {e}")
                    print(f"      Query: {query[:100]}...")

        connessione_postgres.commit()
        print("✅ Schema PostgreSQL creato con successo!")

        print("📂 Inserimento dati di default")
        _inserisci_dati_default_postgres(connessione_postgres)

    except Exception as e:
        print(f"❌ Errore nella creazione dello schema PostgreSQL: {e}")
        if connessione_postgres:
            connessione_postgres.rollback()
    finally:
        if connessione_postgres:
            connessione_postgres.close()


def crea_database():
    """Crea il database: PostgreSQL se sono presenti le variabili d'ambiente, altrimenti SQLite."""
    if DB_HOST and DB_USER and DB_PASSWORD and DB_NAME:
        crea_schema_postgres()
    else:
        crea_schema_sqlite()


if __name__ == "__main__":
    crea_database()
