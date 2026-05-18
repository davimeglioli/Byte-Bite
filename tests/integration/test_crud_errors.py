from app import ottieni_db

# ==================== Gestione Errori (CRUD) ====================


def _imposta_admin(cliente):
    """Crea un utente admin e imposta la sessione."""
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("admin_err", "hash", True, True),
        )
        id_admin = cursore.fetchone()["id"]
        connessione.commit()
    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_admin
        sessione["username"] = "admin_err"
    return id_admin


def test_aggiungi_utente_username_duplicato_restituisce_400(cliente):
    _imposta_admin(cliente)
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash) VALUES (%s, %s)",
            ("dup_user", "hash"),
        )
        connessione.commit()

    risposta = cliente.post(
        "/api/utenti",
        json={"username": "dup_user", "password": "pass", "is_admin": False, "attivo": True},
    )
    assert risposta.status_code == 400
    assert b"in uso" in risposta.data


def test_aggiungi_utente_senza_credenziali_restituisce_400(cliente):
    _imposta_admin(cliente)
    risposta = cliente.post(
        "/api/utenti",
        json={"is_admin": False, "attivo": True},  # mancano username e password
    )
    assert risposta.status_code == 400



def test_elimina_utente_inesistente_restituisce_404(cliente):
    _imposta_admin(cliente)
    risposta = cliente.delete("/api/utenti/99999")
    assert risposta.status_code == 404


def test_aggiungi_prodotto_campi_mancanti_restituisce_400(cliente):
    _imposta_admin(cliente)
    risposta = cliente.post(
        "/api/prodotti",
        json={"prezzo": 10, "quantita": 5},  # mancano nome e categorie
    )
    assert risposta.status_code == 400


def test_rifornisci_prodotto_quantita_zero_restituisce_400(cliente):
    _imposta_admin(cliente)
    risposta = cliente.post(
        "/api/prodotti/1/rifornimento",
        json={"quantita": 0},  # quantita <= 0 non valida
    )
    assert risposta.status_code == 400


def test_api_ordine_inesistente_restituisce_404(cliente):
    _imposta_admin(cliente)
    risposta = cliente.get("/api/ordini/99999")
    assert risposta.status_code == 404


def test_elimina_utente_proprio_account_restituisce_400(cliente):
    id_admin = _imposta_admin(cliente)
    risposta = cliente.delete(f"/api/utenti/{id_admin}")
    assert risposta.status_code == 400
    assert b"eliminare il tuo stesso account" in risposta.data


def test_rifornimento_quantita_non_numerica_restituisce_400(cliente):
    _imposta_admin(cliente)
    risposta = cliente.post(
        "/api/prodotti/1/rifornimento",
        json={"quantita": "abc"},
    )
    assert risposta.status_code == 400


def test_cambia_stato_ordine_gia_completato_restituisce_400(cliente):
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("staff_completato", "hash", True, True),
        )
        id_staff = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO prodotti"
            " (nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti)"
            " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            ("Risotto", 14.0, "Primi", "Cucina", 100, 0),
        )
        id_prodotto = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO ordini"
            " (nome_cliente, numero_tavolo, metodo_pagamento, asporto)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("Test Completato", 1, "Contanti", False),
        )
        id_ordine = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)"
            " VALUES (%s, %s, %s, %s)",
            (id_ordine, id_prodotto, 1, "Completato"),
        )
        connessione.commit()
    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_staff
        sessione["username"] = "staff_completato"

    risposta = cliente.patch(f"/api/ordini/{id_ordine}/stato/Cucina")
    assert risposta.status_code == 400
    assert "completato" in risposta.get_json()["errore"]


def test_cambia_stato_ordine_non_trovato_restituisce_404(cliente):
    id_admin = _imposta_admin(cliente)
    risposta = cliente.patch("/api/ordini/99999/stato/Cucina")
    assert risposta.status_code == 404
