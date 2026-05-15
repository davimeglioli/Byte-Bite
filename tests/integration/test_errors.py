from app import ottieni_db

# ==================== Gestione Errori ====================


def test_creazione_ordine_con_prodotto_inesistente_reindirizza_con_errore(cliente):
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("cassiere_err", "hash", False, True),
        )
        id_utente = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
            (id_utente, "CASSA"),
        )
        connessione.commit()

    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_utente
        sessione["username"] = "cassiere_err"

    dati = {
        "asporto": False,
        "prodotti": [{"id": 99999, "quantita": 1, "nome": "Fantasma"}],
        "nome_cliente": "Test Error",
        "numero_tavolo": 5,
        "metodo_pagamento": "Contanti",
    }

    risposta = cliente.post("/api/ordini/", json=dati)
    assert risposta.status_code == 500


def test_secondo_ordine_fallisce_se_prodotto_esaurito(cliente):
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO prodotti"
            " (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard)"
            " VALUES (99, 'Ultimo', 10, 1, 0, 'Test', 'Cucina')"
        )
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("user_conc", "hash", False, True),
        )
        id_utente = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
            (id_utente, "CASSA"),
        )
        connessione.commit()

    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_utente

    dati = {
        "asporto": False,
        "prodotti": [{"id": 99, "quantita": 1, "nome": "Ultimo"}],
        "nome_cliente": "Cliente 1",
        "numero_tavolo": 1,
        "metodo_pagamento": "Contanti",
    }

    risposta_1 = cliente.post("/api/ordini/", json=dati)
    assert risposta_1.status_code == 201

    dati["nome_cliente"] = "Cliente 2"
    risposta_2 = cliente.post("/api/ordini/", json=dati)
    assert risposta_2.status_code == 500
