import os
import sys
import threading
import time
from pathlib import Path

import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

radice_progetto = Path(__file__).resolve().parents[1]
if str(radice_progetto) not in sys.path:
    sys.path.insert(0, str(radice_progetto))

# Forza il database di test PRIMA di importare qualsiasi modulo che apre connessioni.
# Senza questa riga i test scrivono nel DB di produzione.
DB_TEST_NAME = "byte_bite_test"
os.environ["DB_NAME"] = DB_TEST_NAME

import app as modulo_app
from app import app, socketio

# ==================== E2E ====================

PORTA_SERVER_TEST = 5001
URL_BASE_SERVER_TEST = f"http://127.0.0.1:{PORTA_SERVER_TEST}"


def _connessione_test():
    """Crea una connessione psycopg2 al database usando le variabili d'ambiente."""
    connessione = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "byte_bite"),
        user=os.getenv("DB_USER", "byte_bite_user"),
        password=os.getenv("DB_PASSWORD", "secure_password_change_me"),
        connect_timeout=30,
    )
    connessione.cursor_factory = RealDictCursor
    return connessione


def _azzera_db(connessione):
    """Svuota tutte le tabelle e riporta le sequenze a 1."""
    with connessione.cursor() as cursore:
        cursore.execute(
            "TRUNCATE ordini_prodotti, ordini, prodotti, permessi_pagine, utenti"
            " RESTART IDENTITY CASCADE"
        )
    connessione.commit()


@pytest.fixture(scope="session", autouse=True)
def crea_db_test():
    """Crea il database di test se non esiste (idempotente)."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database="postgres",
        user=os.getenv("DB_USER", "byte_bite_user"),
        password=os.getenv("DB_PASSWORD", "secure_password_change_me"),
        connect_timeout=30,
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_TEST_NAME,))
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE "{DB_TEST_NAME}"')
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def inizializza_schema(crea_db_test):
    """Crea lo schema nel DB di test se non esiste ancora (idempotente)."""
    connessione = _connessione_test()
    try:
        schema = (radice_progetto / "db.sql").read_text()
        with connessione.cursor() as cursore:
            for stmt in schema.split(";"):
                stmt = "\n".join(
                    riga for riga in stmt.splitlines()
                    if not riga.strip().startswith("--")
                ).strip()
                if stmt:
                    cursore.execute(stmt)
        connessione.commit()
    finally:
        connessione.close()


@pytest.fixture(scope="session")
def avvia_server_e2e(inizializza_schema):
    """Inizializza i dati E2E e avvia il server Flask in un thread daemon."""
    connessione = _connessione_test()
    try:
        _azzera_db(connessione)
        hash_admin = bcrypt.hashpw("admin".encode(), bcrypt.gensalt()).decode()
        hash_cassa = bcrypt.hashpw("cassa".encode(), bcrypt.gensalt()).decode()
        with connessione.cursor() as cursore:
            cursore.execute(
                "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
                " VALUES (%s, %s, %s, %s)",
                ("admin", hash_admin, True, True),
            )
            cursore.execute(
                "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
                " VALUES (%s, %s, %s, %s) RETURNING id",
                ("cassa", hash_cassa, False, True),
            )
            id_cassa = cursore.fetchone()["id"]
            cursore.execute(
                "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
                (id_cassa, "CASSA"),
            )
            cursore.executemany(
                "INSERT INTO prodotti"
                " (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [
                    ("Caffè Test", 1.0, "Bar", "Bar", True, 100, 0),
                    ("Pasta Test", 10.0, "Primi", "Cucina", True, 50, 0),
                ],
            )
        connessione.commit()
    finally:
        connessione.close()

    def avvio_app():
        socketio.run(
            app,
            port=PORTA_SERVER_TEST,
            host="127.0.0.1",
            use_reloader=False,
            allow_unsafe_werkzeug=True,
            debug=False,
        )

    thread_server = threading.Thread(target=avvio_app, daemon=True)
    thread_server.start()
    time.sleep(2)
    yield


@pytest.fixture(scope="session")
def url_base(avvia_server_e2e):
    return URL_BASE_SERVER_TEST


@pytest.fixture(scope="session", name="base_url")
def base_url_alias(url_base):
    return url_base


# ==================== Playwright ====================


@pytest.fixture
def pagina(page):
    return page


@pytest.fixture
def navigatore(browser):
    return browser


# ==================== Unit / Integration ====================


@pytest.fixture
def cliente(monkeypatch):
    """Fixture principale: DB pulito + Flask test client per ogni test."""
    testing_precedente = app.config.get("TESTING", False)
    app.config["TESTING"] = True

    # Svuota il DB e azzera le sequenze per isolare ogni test.
    connessione = _connessione_test()
    _azzera_db(connessione)
    connessione.close()

    # Azzera la cache statistiche in memoria per evitare dati residui.
    import services
    services._statistiche_cache = None

    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    with app.test_client() as cliente_flask:
        yield cliente_flask

    app.config["TESTING"] = testing_precedente


@pytest.fixture(name="client")
def client_alias(cliente):
    return cliente


class AzioniAutenticazione:
    def __init__(self, cliente):
        self._cliente = cliente

    def accedi(self, username="admin", password="password"):
        return self._cliente.post(
            "/login/",
            data={"username": username, "password": password},
        )

    def esci(self):
        return self._cliente.post("/logout/")


@pytest.fixture
def autenticazione(cliente):
    """Garantisce un utente admin (admin/password) nel DB di test."""
    from app import ottieni_db
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT 1 FROM utenti WHERE username = 'admin'")
        if not cursore.fetchone():
            hash_password = bcrypt.hashpw("password".encode(), bcrypt.gensalt()).decode()
            cursore.execute(
                "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
                " VALUES (%s, %s, %s, %s)",
                ("admin", hash_password, True, True),
            )
            connessione.commit()
    return AzioniAutenticazione(cliente)


@pytest.fixture(name="auth")
def auth_alias(autenticazione):
    return autenticazione


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker(pytest.mark.nondestructive)
