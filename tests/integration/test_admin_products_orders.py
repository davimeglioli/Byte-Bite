from app import ottieni_db, socketio

# ==================== Amministrazione (CRUD) ====================


def imposta_admin(cliente):
    # Crea una sessione admin e assegna permesso AMMINISTRAZIONE.
    with ottieni_db() as connessione:
        # Inserisce admin nel DB temporaneo.
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("admin_crud", "hash", 1, 1),
        )
        # Recupera id dell'admin.
        id_admin = connessione.execute(
            "SELECT id FROM utenti WHERE username = 'admin_crud'"
        ).fetchone()["id"]
        # Inserisce permesso pagina.
        connessione.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)",
            (id_admin, "AMMINISTRAZIONE"),
        )
        # Commit delle modifiche.
        connessione.commit()

    # Simula sessione autenticata.
    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_admin
        sessione["username"] = "admin_crud"
        sessione["is_admin"] = 1

    # Ritorna id admin per eventuali controlli.
    return id_admin


def test_crud_prodotti(cliente):
    # Prepara contesto admin.
    imposta_admin(cliente)

    # Crea un prodotto via API.
    payload_aggiunta = {
        "nome": "Nuovo Piatto",
        "categoria_dashboard": "Cucina",
        "categoria_menu": "Primi",
        "prezzo": 12.5,
        "quantita": 10,
        "disponibile": True,
    }
    risposta = cliente.post("/api/aggiungi_prodotto", json=payload_aggiunta)
    assert risposta.status_code == 200

    # Recupera id prodotto creato e verifica campi principali.
    with ottieni_db() as connessione:
        prodotto = connessione.execute(
            "SELECT * FROM prodotti WHERE nome = 'Nuovo Piatto'"
        ).fetchone()
        assert prodotto is not None
        id_prodotto = prodotto["id"]
        assert prodotto["quantita"] == 10
        assert prodotto["disponibile"] == 1

    # Modifica il prodotto via API.
    payload_modifica = {
        "id": id_prodotto,
        "nome": "Piatto Modificato",
        "categoria_dashboard": "Cucina",
        "quantita": 5,
    }
    risposta = cliente.post("/api/modifica_prodotto", json=payload_modifica)
    assert risposta.status_code == 200

    # Verifica modifica persistita.
    with ottieni_db() as connessione:
        prodotto = connessione.execute(
            "SELECT * FROM prodotti WHERE id = ?",
            (id_prodotto,),
        ).fetchone()
        assert prodotto["nome"] == "Piatto Modificato"
        assert prodotto["quantita"] == 5

    # Rifornisce il prodotto via API.
    payload_rifornimento = {"id": id_prodotto, "quantita": 20}
    risposta = cliente.post("/api/rifornisci_prodotto", json=payload_rifornimento)
    assert risposta.status_code == 200

    # Verifica quantità aggiornata.
    with ottieni_db() as connessione:
        quantita = connessione.execute(
            "SELECT quantita FROM prodotti WHERE id = ?",
            (id_prodotto,),
        ).fetchone()["quantita"]
        assert quantita == 25

    # Elimina il prodotto via API.
    risposta = cliente.post("/api/elimina_prodotto", json={"id": id_prodotto})
    assert risposta.status_code == 200

    # Verifica che il prodotto non esista più.
    with ottieni_db() as connessione:
        prodotto = connessione.execute(
            "SELECT * FROM prodotti WHERE id = ?",
            (id_prodotto,),
        ).fetchone()
        assert prodotto is None


def test_crud_ordini(cliente):
    # Prepara contesto admin.
    imposta_admin(cliente)

    # Prepara dati ordine e prodotto correlato.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (300, 'Pizza', 10, 100, 0, 'Pizze', 'Cucina')"
        )
        connessione.execute(
            "INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (300, 'Mario', 5, CURRENT_TIMESTAMP, 0, 0, 'Contanti')"
        )
        connessione.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (300, 300, 2, 'In Attesa')"
        )
        # Simula decremento magazzino pre-esistente.
        connessione.execute("UPDATE prodotti SET quantita = 98 WHERE id = 300")
        connessione.commit()

    # Richiede dettagli ordine (HTML).
    risposta = cliente.get("/api/ordine/300/dettagli")
    assert risposta.status_code == 200
    assert b"Pizza" in risposta.data
    assert b"2" in risposta.data

    # Modifica ordine via API.
    payload_modifica = {
        "id_ordine": 300,
        "nome_cliente": "Luigi",
        "numero_tavolo": 10,
        "numero_persone": 4,
        "metodo_pagamento": "Carta",
    }
    risposta = cliente.post("/api/modifica_ordine", json=payload_modifica)
    assert risposta.status_code == 200

    # Verifica aggiornamento ordine.
    with ottieni_db() as connessione:
        ordine = connessione.execute("SELECT * FROM ordini WHERE id = 300").fetchone()
        assert ordine["nome_cliente"] == "Luigi"
        assert ordine["numero_tavolo"] == 10
        assert ordine["metodo_pagamento"] == "Carta"

    # Elimina ordine via API.
    risposta = cliente.post("/api/elimina_ordine", json={"id": 300})
    assert risposta.status_code == 200

    # Verifica eliminazione ordine e ripristino magazzino.
    with ottieni_db() as connessione:
        ordine = connessione.execute("SELECT * FROM ordini WHERE id = 300").fetchone()
        assert ordine is None
        quantita = connessione.execute(
            "SELECT quantita FROM prodotti WHERE id = 300"
        ).fetchone()["quantita"]
        assert quantita == 100

def test_elimina_utente(cliente):
    # Prepara contesto admin.
    imposta_admin(cliente)

    # Inserisce utente da eliminare.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("to_delete", "hash", 0, 1),
        )
        id_target = connessione.execute(
            "SELECT id FROM utenti WHERE username = 'to_delete'"
        ).fetchone()["id"]
        connessione.commit()

    # Invoca endpoint di eliminazione utente.
    risposta = cliente.post("/api/elimina_utente", json={"id_utente": id_target})
    assert risposta.status_code == 200

    # Verifica che l'utente sia stato rimosso.
    with ottieni_db() as connessione:
        utente = connessione.execute(
            "SELECT * FROM utenti WHERE id = ?",
            (id_target,),
        ).fetchone()
        assert utente is None

def test_api_extra_amministrazione(cliente):
    # Prepara contesto admin.
    imposta_admin(cliente)

    # Prepara dati minimi per testare rotte extra.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (400, 'Test Extra', 5, 50, 0, 'Extra', 'Bar')"
        )
        connessione.execute(
            "INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (400, 'Extra Client', 9, CURRENT_TIMESTAMP, 0, 0, 'Carta')"
        )
        connessione.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (400, 400, 1, 'Pronto')"
        )
        connessione.commit()

    # Verifica rotta JSON ordine.
    risposta = cliente.get("/api/ordine/400")
    assert risposta.status_code == 200
    assert risposta.json["nome_cliente"] == "Extra Client"
    assert len(risposta.json["items"]) == 1

    # Verifica rotta HTML righe ordini.
    risposta = cliente.get("/api/amministrazione/ordini_html")
    assert risposta.status_code == 200
    assert b"Extra Client" in risposta.data

    # Verifica rotta HTML righe prodotti.
    risposta = cliente.get("/api/amministrazione/prodotti_html")
    assert risposta.status_code == 200
    assert b"Test Extra" in risposta.data

def test_ricalcola_statistiche_diretto(cliente):
    # Import locale per coprire chiamata diretta.
    from app import ricalcola_statistiche

    # Pulisce tabelle statistiche e inserisce un ordine completato.
    with ottieni_db() as connessione:
        connessione.execute("DELETE FROM statistiche_totali")
        connessione.execute("DELETE FROM statistiche_categorie")
        connessione.execute("DELETE FROM statistiche_ore")

        connessione.execute(
            "INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (500, 'Stat Prod', 10, 100, 0, 'Test', 'Cucina')"
        )
        connessione.execute(
            "INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (500, 'Stat Client', 1, '2025-01-01 12:00:00', 1, 0, 'Contanti')"
        )
        connessione.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (500, 500, 2, 'Completato')"
        )
        connessione.commit()

    # Disabilita emit SocketIO per isolare il test.
    original_emit = socketio.emit
    socketio.emit = lambda *args, **kwargs: None

    # Esegue il ricalcolo e ripristina emit.
    try:
        ricalcola_statistiche()
    finally:
        socketio.emit = original_emit

    # Verifica che le statistiche siano state aggiornate.
    with ottieni_db() as connessione:
        tot = connessione.execute("SELECT * FROM statistiche_totali").fetchone()
        assert tot["ordini_totali"] >= 1
        assert tot["totale_incasso"] >= 20

        cat = connessione.execute(
            "SELECT * FROM statistiche_categorie WHERE categoria_dashboard = 'Cucina'"
        ).fetchone()
        assert cat["totale"] >= 2
