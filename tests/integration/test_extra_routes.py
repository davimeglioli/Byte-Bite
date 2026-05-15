import bcrypt
from app import ottieni_db

# ==================== Rotte Extra ====================


def test_pagina_amministrazione_risponde(cliente, autenticazione):
    autenticazione.accedi()
    risposta = cliente.get("/amministrazione/")
    assert risposta.status_code == 200
    assert b"Amministrazione" in risposta.data


def test_errore_403_senza_permessi_amministrazione(cliente, autenticazione):
    password = "pass"
    hash_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s)",
            ("utente", hash_password, False, True),
        )
        connessione.commit()

    autenticazione.accedi(username="utente", password="pass")
    risposta = cliente.get("/amministrazione/")
    assert risposta.status_code == 403
    assert b"Accesso Negato" in risposta.data or b"403" in risposta.data


def test_utente_disattivo_viene_reindirizzato_al_login(cliente, autenticazione):
    password = "pass"
    hash_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s)",
            ("disattivo", hash_password, False, False),
        )
        connessione.commit()

    autenticazione.accedi(username="disattivo", password="pass")
    risposta = cliente.get("/amministrazione/")
    assert risposta.status_code == 302
    assert "/login/" in risposta.location


def test_esporta_statistiche_scarica_pdf(cliente, autenticazione):
    autenticazione.accedi()

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO prodotti"
            " (id, nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (1000, "ProdTest", 3.5, "TestCat", "Bar", True, 10, 0),
        )
        cursore.execute(
            "INSERT INTO ordini"
            " (id, asporto, data_ordine, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento, completato)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (1000, False, "2025-01-01 12:34:56", "Mario", 5, 2, "Contanti", True),
        )
        cursore.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)"
            " VALUES (%s, %s, %s, %s)",
            (1000, 1000, 2, "Completato"),
        )
        connessione.commit()

    risposta = cliente.get("/api/statistiche/export")
    assert risposta.status_code == 200
    assert risposta.mimetype == "application/pdf"
    assert "attachment;" in risposta.headers.get("Content-Disposition", "")
    assert risposta.data[:4] == b"%PDF"
    assert b"Ordine #1000" in risposta.data
    assert b"Mario" in risposta.data
    assert b"ProdTest" in risposta.data
