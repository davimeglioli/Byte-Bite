import contextlib
import os
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path
import bcrypt
import pytest

radice_progetto = Path(__file__).resolve().parents[1]
if str(radice_progetto) not in sys.path:
    sys.path.insert(0, str(radice_progetto))

import app as modulo_app
from app import app, ottieni_db, socketio

# ==================== E2E ====================

# Porta dedicata ai test E2E per evitare collisioni con l'app locale.
PORTA_SERVER_TEST = 5001
# URL base usato dai test Playwright.
URL_BASE_SERVER_TEST = f"http://127.0.0.1:{PORTA_SERVER_TEST}"


@pytest.fixture(scope="session")
def percorso_db_test_e2e(tmp_path_factory):
    # Crea un file SQLite persistente per l'intera sessione di test E2E.
    percorso = tmp_path_factory.mktemp("data") / "db_test_e2e.sqlite3"
    return str(percorso)


@pytest.fixture(scope="session")
def avvia_server_e2e(percorso_db_test_e2e):
    # Carica lo schema dal file SQL.
    with open("db.sql", "r") as file_schema:
        schema = file_schema.read()

    # Inizializza il database E2E con schema e dati minimi.
    connessione = sqlite3.connect(percorso_db_test_e2e)
    connessione.executescript(schema)

    # Crea utente admin (admin/admin) per flussi amministrazione.
    hash_admin = bcrypt.hashpw("admin".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    connessione.execute(
        "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
        ("admin", hash_admin, 1, 1),
    )

    # Crea utente cassa (cassa/cassa) per flussi ordine.
    hash_cassa = bcrypt.hashpw("cassa".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    connessione.execute(
        "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
        ("cassa", hash_cassa, 0, 1),
    )

    # Assegna permesso CASSA al profilo cassa.
    id_cassa = connessione.execute("SELECT id FROM utenti WHERE username = 'cassa'").fetchone()[0]
    connessione.execute(
        "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)",
        (id_cassa, "CASSA"),
    )

    # Inserisce prodotti di base per i test E2E (Bar/Cucina).
    connessione.execute(
        """
        INSERT INTO prodotti (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti)
        VALUES
            ('Caffè Test', 1.0, 'Bar', 'Bar', 1, 100, 0),
            ('Pasta Test', 10.0, 'Primi', 'Cucina', 1, 50, 0)
        """
    )
    connessione.commit()
    connessione.close()

    # Conserva il riferimento al connect originale di sqlite3.
    connessione_originale = sqlite3.connect

    def connect_e2e(database, *args, **kwargs):
        # Se l'app prova a usare il DB reale, forza l'uso del DB E2E.
        if "db.sqlite3" in str(database):
            return connessione_originale(percorso_db_test_e2e, *args, **kwargs)
        # Altrimenti delega al comportamento standard.
        return connessione_originale(database, *args, **kwargs)

    # Patching della connessione sqlite usata dal modulo app.
    modulo_app.sq.connect = connect_e2e

    def avvio_app():
        # Riduce rumore dei log durante l'avvio del server di test.
        import logging

        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        # Avvia l'app su porta dedicata, senza reloader.
        socketio.run(
            app,
            port=PORTA_SERVER_TEST,
            host="127.0.0.1",
            use_reloader=False,
            allow_unsafe_werkzeug=True,
            debug=False,
        )

    # Esegue il server in un thread daemon.
    thread_server = threading.Thread(target=avvio_app, daemon=True)
    thread_server.start()
    # Attende che il server sia pronto prima di far partire Playwright.
    time.sleep(2)

    # Fornisce controllo ai test (sessione E2E attiva).
    yield

    # Ripristina il connect originale dopo la sessione.
    modulo_app.sq.connect = connessione_originale


@pytest.fixture(scope="session")
def url_base(avvia_server_e2e):
    # Espone l'URL del server E2E ai test.
    return URL_BASE_SERVER_TEST


@pytest.fixture(scope="session", name="base_url")
def base_url_alias(url_base):
    # Alias per compatibilità con test che usano base_url.
    return url_base


# ==================== Playwright ====================


@pytest.fixture
def pagina(page):
    # Alias in italiano del fixture page di pytest-playwright.
    return page


@pytest.fixture
def navigatore(browser):
    # Alias in italiano del fixture browser di pytest-playwright.
    return browser


# ==================== Unit / Integration ====================


@pytest.fixture
def cliente(monkeypatch):
    # Crea un file temporaneo per isolare il DB per ogni test.
    descrittore_file, percorso_db = tempfile.mkstemp()

    # Abilita modalità di test per Flask.
    testing_precedente = app.config.get("TESTING", False)
    app.config["TESTING"] = True

    # Conserva connect originale per delegare connessioni non patchate.
    connessione_originale = sqlite3.connect

    def connect_unit(database, *args, **kwargs):
        # Reindirizza l'app al DB temporaneo quando usa il nome standard.
        if database == "db.sqlite3":
            return connessione_originale(percorso_db, *args, **kwargs)
        # Per altri database, usa sqlite3 normale.
        return connessione_originale(database, *args, **kwargs)

    # Applica il patch su app.sq.connect (sqlite3 aliasato in app.py).
    monkeypatch.setattr("app.sq.connect", connect_unit)
    # Disabilita task in background per rendere i test deterministici.
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    # Inizializza lo schema nel DB temporaneo.
    with app.app_context():
        with open("db.sql", "r") as file_schema:
            schema = file_schema.read()
        with contextlib.closing(sqlite3.connect(percorso_db)) as conn:
            conn.executescript(schema)

    # Espone il test client Flask al test.
    with app.test_client() as cliente_flask:
        yield cliente_flask

    # Ripristina configurazione app.
    app.config["TESTING"] = testing_precedente
    # Chiude file descriptor e tenta di rimuovere il DB temporaneo.
    os.close(descrittore_file)
    try:
        os.unlink(percorso_db)
    except PermissionError:
        # Su Windows/lock file, l'unlink potrebbe fallire: ignora.
        pass


@pytest.fixture(name="client")
def client_alias(cliente):
    # Alias per compatibilità con test che usano client.
    return cliente


class AzioniAutenticazione:
    def __init__(self, cliente):
        # Memorizza il client per riuso nei metodi.
        self._cliente = cliente

    def accedi(self, username="admin", password="password"):
        # Esegue POST alla rotta di login con credenziali fornite.
        return self._cliente.post(
            "/login/",
            data={"username": username, "password": password},
        )

    def esci(self):
        # Esegue GET alla rotta di logout.
        return self._cliente.get("/logout/")


@pytest.fixture
def autenticazione(cliente):
    # Garantisce che esista un utente admin base per i test.
    with ottieni_db() as connessione:
        esiste = connessione.execute(
            "SELECT 1 FROM utenti WHERE username = 'admin'"
        ).fetchone()
        if not esiste:
            # Crea admin di default con password nota.
            hash_password = bcrypt.hashpw("password".encode(), bcrypt.gensalt()).decode()
            connessione.execute(
                "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
                ("admin", hash_password, 1, 1),
            )
            connessione.commit()

    # Ritorna un helper per azioni di accesso/uscita.
    return AzioniAutenticazione(cliente)


@pytest.fixture(name="auth")
def auth_alias(autenticazione):
    # Alias per compatibilità con test che usano auth.
    return autenticazione


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker(pytest.mark.nondestructive)
