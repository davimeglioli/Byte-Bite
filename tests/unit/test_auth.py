import bcrypt
from app import ottieni_db

# ==================== Accesso ====================


def test_accesso_riuscito_con_credenziali_valide(cliente):
    # Prepara password e hash per un utente di test.
    password = "password123"
    hash_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # Inserisce l'utente nel DB temporaneo.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("utente_test", hash_password, 0, 1),
        )
        connessione.commit()

    # Esegue il login e segue i redirect.
    risposta = cliente.post(
        "/login/",
        data={"username": "utente_test", "password": password},
        follow_redirects=True,
    )

    # Verifica risposta OK.
    assert risposta.status_code == 200
    # Verifica che ci sia stato almeno un redirect.
    assert len(risposta.history) > 0
    # Verifica che la destinazione finale sia la home.
    assert risposta.request.path == "/"


def test_accesso_fallisce_con_credenziali_errate(cliente):
    # Esegue login con credenziali errate.
    risposta = cliente.post(
        "/login/",
        data={"username": "utente_sbagliato", "password": "password_sbagliata"},
        follow_redirects=True,
    )

    # La pagina di login risponde comunque 200 (errore mostrato a video).
    assert risposta.status_code == 200
    # Verifica che venga mostrato il messaggio di errore.
    assert b"Username o password errata" in risposta.data


def test_pagina_protetta_richiede_accesso(cliente):
    # Prova ad accedere alla cassa senza sessione.
    risposta = cliente.get("/cassa/", follow_redirects=True)
    # Verifica che il contenuto sia quello del login (redirect).
    assert risposta.status_code == 200
    # Verifica presenza testo login.
    assert b"Login" in risposta.data
    # Verifica che la path finale sia login.
    assert "login" in risposta.request.path
