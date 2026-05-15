from app import ottieni_db, socketio

# ==================== Amministrazione (CRUD) ====================


def imposta_admin(cliente):
    """Crea una sessione admin con permesso AMMINISTRAZIONE."""
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("admin_crud", "hash", True, True),
        )
        id_admin = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
            (id_admin, "AMMINISTRAZIONE"),
        )
        connessione.commit()

    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_admin
        sessione["username"] = "admin_crud"
        sessione["is_admin"] = True

    return id_admin


def test_crud_prodotti(cliente):
    imposta_admin(cliente)

    payload_aggiunta = {
        "nome": "Nuovo Piatto",
        "categoria_dashboard": "Cucina",
        "categoria_menu": "Primi",
        "prezzo": 12.5,
        "quantita": 10,
        "disponibile": True,
    }
    risposta = cliente.post("/api/prodotti/", json=payload_aggiunta)
    assert risposta.status_code == 201

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT * FROM prodotti WHERE nome = 'Nuovo Piatto'")
        prodotto = cursore.fetchone()
        assert prodotto is not None
        id_prodotto = prodotto["id"]
        assert prodotto["quantita"] == 10
        assert prodotto["disponibile"] == True

    payload_modifica = {
        "nome": "Piatto Modificato",
        "categoria_dashboard": "Cucina",
        "prezzo": 15.0,
        "quantita": 5,
    }
    risposta = cliente.put(f"/api/prodotti/{id_prodotto}", json=payload_modifica)
    assert risposta.status_code == 200

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT * FROM prodotti WHERE id = %s", (id_prodotto,))
        prodotto = cursore.fetchone()
        assert prodotto["nome"] == "Piatto Modificato"
        assert prodotto["prezzo"] == 15.0
        assert prodotto["quantita"] == 5

    payload_rifornimento = {"quantita": 20}
    risposta = cliente.patch(f"/api/prodotti/{id_prodotto}", json=payload_rifornimento)
    assert risposta.status_code == 200

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT quantita FROM prodotti WHERE id = %s", (id_prodotto,))
        assert cursore.fetchone()["quantita"] == 25

    risposta = cliente.delete(f"/api/prodotti/{id_prodotto}")
    assert risposta.status_code == 200

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT * FROM prodotti WHERE id = %s", (id_prodotto,))
        assert cursore.fetchone() is None


def test_crud_ordini(cliente):
    imposta_admin(cliente)

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO prodotti"
            " (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard)"
            " VALUES (300, 'Pizza', 10, 100, 0, 'Pizze', 'Cucina')"
        )
        cursore.execute(
            "INSERT INTO ordini"
            " (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento)"
            " VALUES (300, 'Mario', 5, CURRENT_TIMESTAMP, FALSE, FALSE, 'Contanti')"
        )
        cursore.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)"
            " VALUES (300, 300, 2, 'In Attesa')"
        )
        cursore.execute("UPDATE prodotti SET quantita = 98 WHERE id = 300")
        connessione.commit()

    risposta = cliente.get("/api/ordini/300")
    assert risposta.status_code == 200
    assert b"Pizza" in risposta.data
    assert b"2" in risposta.data

    payload_modifica = {
        "id_ordine": 300,
        "nome_cliente": "Luigi",
        "numero_tavolo": 10,
        "numero_persone": 4,
        "metodo_pagamento": "Carta",
    }
    risposta = cliente.put(f"/api/ordini/{payload_modifica['id_ordine']}", json=payload_modifica)
    assert risposta.status_code == 200

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT * FROM ordini WHERE id = 300")
        ordine = cursore.fetchone()
        assert ordine["nome_cliente"] == "Luigi"
        assert ordine["numero_tavolo"] == 10
        assert ordine["metodo_pagamento"] == "Carta"

    risposta = cliente.delete("/api/ordini/300")
    assert risposta.status_code == 200

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT * FROM ordini WHERE id = 300")
        assert cursore.fetchone() is None
        cursore.execute("SELECT quantita FROM prodotti WHERE id = 300")
        assert cursore.fetchone()["quantita"] == 100


def test_elimina_utente(cliente):
    imposta_admin(cliente)

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("to_delete", "hash", False, True),
        )
        id_target = cursore.fetchone()["id"]
        connessione.commit()

    risposta = cliente.delete(f"/api/utenti/{id_target}")
    assert risposta.status_code == 200

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT * FROM utenti WHERE id = %s", (id_target,))
        assert cursore.fetchone() is None


def test_api_extra_amministrazione(cliente):
    imposta_admin(cliente)

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO prodotti"
            " (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard)"
            " VALUES (400, 'Test Extra', 5, 50, 0, 'Extra', 'Bar')"
        )
        cursore.execute(
            "INSERT INTO ordini"
            " (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento)"
            " VALUES (400, 'Extra Client', 9, CURRENT_TIMESTAMP, FALSE, FALSE, 'Carta')"
        )
        cursore.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)"
            " VALUES (400, 400, 1, 'Pronto')"
        )
        connessione.commit()

    risposta = cliente.get("/api/ordini/400")
    assert risposta.status_code == 200
    assert risposta.json["nome_cliente"] == "Extra Client"
    assert len(risposta.json["prodotti"]) == 1

    risposta = cliente.get("/api/ordini/")
    assert risposta.status_code == 200
    assert b"Extra Client" in risposta.data

    risposta = cliente.get("/api/prodotti/")
    assert risposta.status_code == 200
    assert b"Test Extra" in risposta.data


def test_modifica_prodotto_quantita_zero_rende_non_disponibile(cliente):
    imposta_admin(cliente)

    risposta = cliente.post("/api/prodotti/", json={
        "nome": "Prodotto Esauribile",
        "categoria_dashboard": "Bar",
        "categoria_menu": "Bar",
        "prezzo": 2.0,
        "quantita": 10,
        "disponibile": True,
    })
    assert risposta.status_code == 201

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT id FROM prodotti WHERE nome = 'Prodotto Esauribile'")
        id_prodotto = cursore.fetchone()["id"]

    risposta = cliente.put(f"/api/prodotti/{id_prodotto}", json={
        "nome": "Prodotto Esauribile",
        "categoria_dashboard": "Bar",
        "prezzo": 2.0,
        "quantita": 0,
    })
    assert risposta.status_code == 200

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT disponibile FROM prodotti WHERE id = %s", (id_prodotto,))
        assert cursore.fetchone()["disponibile"] == False


def test_ricalcola_statistiche_diretto(cliente):
    from app import ricalcola_statistiche

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("DELETE FROM ordini_prodotti")
        cursore.execute("DELETE FROM ordini")
        cursore.execute(
            "INSERT INTO prodotti"
            " (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard)"
            " VALUES (500, 'Stat Prod', 10, 100, 0, 'Test', 'Cucina')"
        )
        cursore.execute(
            "INSERT INTO ordini"
            " (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento)"
            " VALUES (500, 'Stat Client', 1, '2025-01-01 12:00:00', TRUE, FALSE, 'Contanti')"
        )
        cursore.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)"
            " VALUES (500, 500, 2, 'Completato')"
        )
        connessione.commit()

    original_emit = socketio.emit
    socketio.emit = lambda *args, **kwargs: None
    try:
        ricalcola_statistiche()
    finally:
        socketio.emit = original_emit

    from services import costruisci_dati_statistiche
    stats = costruisci_dati_statistiche()
    assert stats["totali"]["ordini_totali"] >= 1
    assert stats["totali"]["totale_incasso"] >= 20
    cucina = next((r for r in stats["categorie"] if r["categoria_dashboard"] == "Cucina"), None)
    assert cucina is not None
    assert cucina["totale"] >= 2
