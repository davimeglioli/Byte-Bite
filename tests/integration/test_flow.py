from app import ottieni_db

# ==================== Flusso Ordine ====================


def test_flusso_completo_ordine(cliente, monkeypatch):
    with ottieni_db() as connessione:
        cursore = connessione.cursor()

        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("cassiere", "hash_finto", False, True),
        )
        id_staff = cursore.fetchone()["id"]

        cursore.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
            (id_staff, "CASSA"),
        )
        cursore.execute(
            "INSERT INTO prodotti"
            " (id, nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (10, "Carbonara", 12.0, "Primi", "Cucina", 50, 0),
        )
        connessione.commit()

    monkeypatch.setattr("app.emissione_sicura", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_staff
        sessione["username"] = "cassiere"

    dati_ordine = {
        "asporto": False,
        "nome_cliente": "FlussoTest",
        "numero_tavolo": 5,
        "numero_persone": 2,
        "metodo_pagamento": "Contanti",
        "prodotti": [{"id": 10, "quantita": 2, "nome": "Carbonara"}],
    }
    risposta = cliente.post("/api/ordini/", json=dati_ordine)
    assert risposta.status_code == 201

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT id FROM ordini WHERE nome_cliente = 'FlussoTest'")
        ordine = cursore.fetchone()
        assert ordine is not None
        id_ordine = ordine["id"]

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
            (id_staff, "DASHBOARD"),
        )
        connessione.commit()

    risposta = cliente.get("/api/dashboard/cucina")
    assert risposta.status_code == 200
    dati = risposta.get_json()
    nomi_clienti = [o["nome_cliente"] for o in dati["non_completati"]]
    nomi_prodotti = [p["nome"] for o in dati["non_completati"] for p in o["prodotti"]]
    assert "FlussoTest" in nomi_clienti
    assert "Carbonara" in nomi_prodotti

    risposta = cliente.patch(f"/api/ordini/{id_ordine}/stato/Cucina")
    assert risposta.status_code == 200
    assert risposta.get_json()["nuovo_stato"] == "In Preparazione"

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "SELECT stato FROM ordini_prodotti WHERE ordine_id = %s AND prodotto_id = 10",
            (id_ordine,),
        )
        assert cursore.fetchone()["stato"] == "In Preparazione"

    risposta = cliente.patch(f"/api/ordini/{id_ordine}/stato/Cucina")
    assert risposta.get_json()["nuovo_stato"] == "Pronto"

    risposta = cliente.patch(f"/api/ordini/{id_ordine}/stato/Cucina")
    assert risposta.get_json()["nuovo_stato"] == "In Preparazione"

    risposta = cliente.patch(f"/api/ordini/{id_ordine}/stato/Cucina")
    assert risposta.get_json()["nuovo_stato"] == "Pronto"

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "UPDATE ordini_prodotti SET stato = 'Completato'"
            " WHERE ordine_id = %s AND prodotto_id = 10",
            (id_ordine,),
        )
        connessione.commit()

    risposta = cliente.get("/api/dashboard/cucina")
    dati = risposta.get_json()
    assert "FlussoTest" not in [o["nome_cliente"] for o in dati["non_completati"]]
