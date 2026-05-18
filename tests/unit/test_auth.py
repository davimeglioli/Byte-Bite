import bcrypt
from app import ottieni_db

# ==================== Accesso ====================


def test_accesso_riuscito_con_credenziali_valide(cliente):
    password = "password123"
    hash_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s)",
            ("utente_test", hash_password, False, True),
        )
        connessione.commit()

    risposta = cliente.post(
        "/login/",
        data={"username": "utente_test", "password": password},
        follow_redirects=True,
    )

    assert risposta.status_code == 200
    assert len(risposta.history) > 0
    assert risposta.request.path == "/"


def test_accesso_fallisce_con_credenziali_errate(cliente):
    risposta = cliente.post(
        "/login/",
        data={"username": "utente_sbagliato", "password": "password_sbagliata"},
        follow_redirects=True,
    )

    assert risposta.status_code == 200
    assert b"Username o password errata" in risposta.data


def test_pagina_protetta_richiede_accesso(cliente):
    risposta = cliente.get("/cassa/", follow_redirects=True)
    assert risposta.status_code == 200
    assert b"Login" in risposta.data
    assert "login" in risposta.request.path


def test_login_get_mostra_form(cliente):
    risposta = cliente.get("/login/")
    assert risposta.status_code == 200
    assert b'name="username"' in risposta.data
    assert b'name="password"' in risposta.data


def test_login_fallisce_senza_campo_password(cliente):
    risposta = cliente.post(
        "/login/",
        data={"username": "qualcuno"},
        follow_redirects=True,
    )
    assert risposta.status_code == 200
    assert b"Username o password errata" in risposta.data


def test_login_account_disattivato(cliente):
    hash_pass = bcrypt.hashpw("pass".encode(), bcrypt.gensalt()).decode()
    with ottieni_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s)",
            ("disattivo_login", hash_pass, False, False),
        )
        conn.commit()
    risposta = cliente.post(
        "/login/",
        data={"username": "disattivo_login", "password": "pass"},
        follow_redirects=True,
    )
    assert risposta.status_code == 200
    assert b"Account disattivato" in risposta.data


def test_logout_reindirizza_al_login(cliente, autenticazione):
    autenticazione.accedi()
    risposta = cliente.post("/logout/")
    assert risposta.status_code == 302
    assert "/login/" in risposta.location
