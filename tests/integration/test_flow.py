import json
from app import ottieni_db

# ==================== Flusso Ordine ====================


def test_flusso_completo_ordine(cliente, monkeypatch):
    # Prepara utente staff e prodotto per la Cucina.
    with ottieni_db() as connessione:
        # Crea utente cassiere.
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("cassiere", "hash_finto", 0, 1),
        )
        # Recupera id utente.
        id_staff = connessione.execute(
            "SELECT id FROM utenti WHERE username = 'cassiere'"
        ).fetchone()["id"]
        # Assegna permesso CASSA.
        connessione.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)",
            (id_staff, "CASSA"),
        )
        # Inserisce un prodotto per test ordine.
        connessione.execute(
            "INSERT INTO prodotti (id, nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (10, "Carbonara", 12.0, "Primi", "Cucina", 50, 0),
        )
        # Commit delle modifiche.
        connessione.commit()

    # Disabilita emissioni SocketIO per rendere il test deterministico.
    monkeypatch.setattr("app.emissione_sicura", lambda *args, **kwargs: None)
    # Disabilita task in background.
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    # Simula sessione staff.
    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_staff
        sessione["username"] = "cassiere"

    # Crea un ordine con un prodotto.
    dati_ordine = {
        "nome_cliente": "FlussoTest",
        "numero_tavolo": "5",
        "numero_persone": "2",
        "metodo_pagamento": "Contanti",
        "prodotti": json.dumps([{"id": 10, "quantita": 2, "nome": "Carbonara"}]),
    }
    # Invia l'ordine e segue i redirect.
    risposta = cliente.post("/aggiungi_ordine/", data=dati_ordine, follow_redirects=True)
    assert risposta.status_code == 200

    # Recupera id dell'ordine creato.
    with ottieni_db() as connessione:
        ordine = connessione.execute(
            "SELECT id FROM ordini WHERE nome_cliente = 'FlussoTest'"
        ).fetchone()
        assert ordine is not None
        id_ordine = ordine["id"]

    # Aggiunge permesso DASHBOARD per poter leggere partial.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)",
            (id_staff, "DASHBOARD"),
        )
        connessione.commit()

    # Richiede HTML partial della dashboard cucina.
    risposta = cliente.get("/dashboard/cucina/partial")
    assert risposta.status_code == 200
    dati = risposta.get_json()
    # Verifica che l'ordine sia presente.
    assert "Carbonara" in dati["html_non_completati"]
    assert "FlussoTest" in dati["html_non_completati"]

    # Esegue avanzamento stato tramite endpoint.
    payload = {"ordine_id": id_ordine, "categoria": "Cucina"}
    risposta = cliente.post("/cambia_stato/", json=payload)
    assert risposta.status_code == 200
    assert risposta.get_json()["nuovo_stato"] == "In Preparazione"

    # Verifica che lo stato sia stato aggiornato nel DB.
    with ottieni_db() as connessione:
        stato = connessione.execute(
            "SELECT stato FROM ordini_prodotti WHERE ordine_id = ? AND prodotto_id = 10",
            (id_ordine,),
        ).fetchone()["stato"]
        assert stato == "In Preparazione"

    # Avanza a Pronto.
    risposta = cliente.post("/cambia_stato/", json=payload)
    assert risposta.get_json()["nuovo_stato"] == "Pronto"

    # Verifica nuovamente nuovo stato.
    assert risposta.get_json()["nuovo_stato"] == "Pronto"

    # Toggle per tornare a In Preparazione.
    risposta = cliente.post("/cambia_stato/", json=payload)
    assert risposta.get_json()["nuovo_stato"] == "In Preparazione"

    # Riporta a Pronto.
    risposta = cliente.post("/cambia_stato/", json=payload)
    assert risposta.get_json()["nuovo_stato"] == "Pronto"

    # Simula completamento (come se scadesse il timer).
    with ottieni_db() as connessione:
        connessione.execute(
            "UPDATE ordini_prodotti SET stato = 'Completato' WHERE ordine_id = ? AND prodotto_id = 10",
            (id_ordine,),
        )
        connessione.commit()

    # Verifica che l'ordine non sia più tra i non completati.
    risposta = cliente.get("/dashboard/cucina/partial")
    dati = risposta.get_json()
    assert "FlussoTest" not in dati["html_non_completati"]
