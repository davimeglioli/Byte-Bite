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
        "/api/aggiungi_utente",
        json={"username": "dup_user", "password": "pass", "is_admin": False, "attivo": True},
    )
    assert risposta.status_code == 400
    assert b"in uso" in risposta.data


def test_aggiungi_utente_senza_credenziali_restituisce_400(cliente):
    _imposta_admin(cliente)
    risposta = cliente.post(
        "/api/aggiungi_utente",
        json={"is_admin": False, "attivo": True},  # mancano username e password
    )
    assert risposta.status_code == 400


def test_modifica_ordine_senza_id_ordine_restituisce_400(cliente):
    _imposta_admin(cliente)
    risposta = cliente.post(
        "/api/modifica_ordine",
        json={"nome_cliente": "Fantasma"},  # manca id_ordine
    )
    assert risposta.status_code == 400


def test_elimina_utente_inesistente_restituisce_404(cliente):
    _imposta_admin(cliente)
    risposta = cliente.post("/api/elimina_utente", json={"id_utente": 99999})
    assert risposta.status_code == 404


def test_aggiungi_prodotto_campi_mancanti_restituisce_400(cliente):
    _imposta_admin(cliente)
    risposta = cliente.post(
        "/api/aggiungi_prodotto",
        json={"prezzo": 10, "quantita": 5},  # mancano nome e categorie
    )
    assert risposta.status_code == 400


def test_rifornisci_prodotto_quantita_zero_restituisce_400(cliente):
    _imposta_admin(cliente)
    risposta = cliente.post(
        "/api/rifornisci_prodotto",
        json={"id": 1, "quantita": 0},  # quantita <= 0 non valida
    )
    assert risposta.status_code == 400


def test_api_ordine_inesistente_restituisce_404(cliente):
    _imposta_admin(cliente)
    risposta = cliente.get("/api/ordine/99999")
    assert risposta.status_code == 404
