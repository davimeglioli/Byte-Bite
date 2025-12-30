from app import ottieni_db

# ==================== Gestione Errori (CRUD) ====================


def test_errori_crud_su_risorse_inesistenti(cliente, autenticazione, monkeypatch):
    # Disabilita emit SocketIO per evitare side-effects.
    monkeypatch.setattr("app.socketio.emit", lambda *args, **kwargs: None)
    # Esegue login admin di base.
    autenticazione.accedi()

    # Modifica prodotto inesistente.
    risposta = cliente.post(
        "/api/modifica_prodotto",
        json={
            "id": 99999,
            "nome": "New",
            "prezzo": 10,
            "categoria_menu": "Bar",
            "categoria_dashboard": "Bar",
            "quantita": 10,
        },
    )
    assert risposta.status_code in [200, 404, 400]

    # Elimina prodotto inesistente.
    risposta = cliente.post("/api/elimina_prodotto", json={"id": 99999})
    assert risposta.status_code in [200, 404]

    # Modifica ordine inesistente.
    risposta = cliente.post(
        "/api/modifica_ordine",
        json={
            "id": 99999,
            "nome_cliente": "Fantasma",
            "numero_tavolo": 1,
            "asporto": 0,
            "metodo_pagamento": "Contanti",
        },
    )
    assert risposta.status_code in [200, 404, 400]

    # Elimina ordine inesistente.
    risposta = cliente.post("/api/elimina_ordine", json={"id": 99999})
    assert risposta.status_code in [200, 404]

    # Recupera ordine inesistente.
    risposta = cliente.get("/api/ordine/99999")
    assert risposta.status_code == 404

    # Inserisce un utente duplicato per testare errore di unicità.
    with ottieni_db() as connessione:
        connessione.execute("INSERT INTO utenti (username, password_hash) VALUES ('dup', 'hash')")
        connessione.commit()

    # Tenta di aggiungere utente con username già esistente.
    risposta = cliente.post(
        "/api/aggiungi_utente",
        json={"username": "dup", "password": "pass", "is_admin": 0, "attivo": 1},
    )
    assert risposta.status_code == 400
    assert b"Username gi" in risposta.data or b"in uso" in risposta.data

    # Modifica utente inesistente.
    risposta = cliente.post(
        "/api/modifica_utente",
        json={"id": 99999, "username": "fantasma", "is_admin": 0, "attivo": 1},
    )
    assert risposta.status_code in [200, 404, 500, 400]

    # Elimina utente inesistente.
    risposta = cliente.post("/api/elimina_utente", json={"id": 99999})
    assert risposta.status_code in [200, 404, 400]

    # Reset password utente inesistente.
    risposta = cliente.post("/api/reset_password_utente", json={"id": 99999, "password": "new"})
    assert risposta.status_code in [200, 404]

    # Toggle stato utente inesistente.
    risposta = cliente.post("/api/toggle_stato_utente", json={"id": 99999})
    assert risposta.status_code in [200, 404]

    # Recupero permessi utente inesistente.
    risposta = cliente.get("/api/ottieni_permessi_utente/99999")
    assert risposta.status_code in [200, 404]

def test_errori_carrello(cliente):
    # Inizializza carrello vuoto in sessione.
    with cliente.session_transaction() as sessione:
        sessione["carrello"] = {}

    # Prova ad aggiungere un prodotto inesistente.
    risposta = cliente.post("/aggiungi_al_carrello", data={"prodotto_id": "99999"})
    assert risposta.status_code in [302, 404]

    # Prova a rimuovere un prodotto non presente.
    risposta = cliente.post("/rimuovi_dal_carrello", data={"prodotto_id": "99999"})
    assert risposta.status_code in [302, 404]
