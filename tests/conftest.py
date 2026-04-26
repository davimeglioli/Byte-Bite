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

import app as modulo_app
from app import app, socketio

# ==================== E2E ====================

PORTA_SERVER_TEST = 5001
URL_BASE_SERVER_TEST = f"http://127.0.0.1:{PORTA_SERVER_TEST}"


def _connessione_test():
    """Crea una connessione psycopg2 al database usando le variabili d'ambiente."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "byte_bite"),
        user=os.getenv("DB_USER", "byte_bite_user"),
        password=os.getenv("DB_PASSWORD", "secure_password_change_me"),
        connect_timeout=30,
    )
    conn.cursor_factory = RealDictCursor
    return conn


def _azzera_db(conn):
    """Svuota tutte le tabelle e riporta le sequenze a 1."""
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE ordini_prodotti, ordini, prodotti, permessi_pagine, utenti"
            " RESTART IDENTITY CASCADE"
        )
    conn.commit()


@pytest.fixture(scope="session", autouse=True)
def inizializza_schema():
    """Crea lo schema nel DB di test se non esiste ancora (idempotente)."""
    conn = _connessione_test()
    try:
        schema = (radice_progetto / "db.sql").read_text()
        with conn.cursor() as cur:
            for stmt in schema.split(";"):
                stmt = "\n".join(
                    riga for riga in stmt.splitlines()
                    if not riga.strip().startswith("--")
                ).strip()
                if stmt:
                    cur.execute(stmt)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope="session")
def avvia_server_e2e():
    """Inizializza i dati E2E e avvia il server Flask in un thread daemon."""
    conn = _connessione_test()
    try:
        _azzera_db(conn)
        hash_admin = bcrypt.hashpw("admin".encode(), bcrypt.gensalt()).decode()
        hash_cassa = bcrypt.hashpw("cassa".encode(), bcrypt.gensalt()).decode()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
                " VALUES (%s, %s, %s, %s)",
                ("admin", hash_admin, True, True),
            )
            cur.execute(
                "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
                " VALUES (%s, %s, %s, %s) RETURNING id",
                ("cassa", hash_cassa, False, True),
            )
            id_cassa = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
                (id_cassa, "CASSA"),
            )
            cur.executemany(
                "INSERT INTO prodotti"
                " (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [
                    ("Caffè Test", 1.0, "Bar", "Bar", True, 100, 0),
                    ("Pasta Test", 10.0, "Primi", "Cucina", True, 50, 0),
                ],
            )
        conn.commit()
    finally:
        conn.close()

    def avvio_app():
        import logging
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
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
    conn = _connessione_test()
    _azzera_db(conn)
    conn.close()

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
        return self._cliente.get("/logout/")


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
