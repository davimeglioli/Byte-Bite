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
