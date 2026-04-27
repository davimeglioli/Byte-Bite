from app import cambia_stato_automatico, ottieni_db, socketio, timer_attivi

# ==================== Timer ====================


def test_timer_completa_ordine_pronto(cliente):
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO prodotti"
            " (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard)"
            " VALUES (200, 'Test Timer', 10, 100, 0, 'Test', 'Cucina')"
        )
        cursore.execute(
            "INSERT INTO ordini"
            " (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento)"
            " VALUES (200, 'Timer Client', 1, CURRENT_TIMESTAMP, FALSE, FALSE, 'Contanti')"
        )
        cursore.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)"
            " VALUES (200, 200, 1, 'Pronto')"
        )
        connessione.commit()

    ordine_id = 200
    categoria = "Cucina"
    id_timer = "test-timer-id"
    chiave_timer = (ordine_id, categoria)

    timer_attivi[chiave_timer] = {"annulla": False, "id": id_timer}

    original_sleep = socketio.sleep
    socketio.sleep = lambda x: None
    try:
        cambia_stato_automatico(ordine_id, categoria, id_timer)
    finally:
        socketio.sleep = original_sleep

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "SELECT stato FROM ordini_prodotti WHERE ordine_id = 200 AND prodotto_id = 200"
        )
        stato = cursore.fetchone()["stato"]
        cursore.execute("SELECT completato FROM ordini WHERE id = 200")
        completato = cursore.fetchone()["completato"]

    assert stato == "Completato"
    assert completato == True
    assert chiave_timer not in timer_attivi


def test_timer_non_modifica_se_annullato(cliente):
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO prodotti"
            " (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard)"
            " VALUES (201, 'Test Timer Cancel', 10, 100, 0, 'Test', 'Cucina')"
        )
        cursore.execute(
            "INSERT INTO ordini"
            " (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento)"
            " VALUES (201, 'Timer Client 2', 1, CURRENT_TIMESTAMP, FALSE, FALSE, 'Contanti')"
        )
        cursore.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)"
            " VALUES (201, 201, 1, 'Pronto')"
        )
        connessione.commit()

    ordine_id = 201
    categoria = "Cucina"
    id_timer = "test-cancel-id"
    chiave_timer = (ordine_id, categoria)

    timer_attivi[chiave_timer] = {"annulla": True, "id": id_timer}

    original_sleep = socketio.sleep
    socketio.sleep = lambda x: None
    try:
        cambia_stato_automatico(ordine_id, categoria, id_timer)
    finally:
        socketio.sleep = original_sleep

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "SELECT stato FROM ordini_prodotti WHERE ordine_id = 201 AND prodotto_id = 201"
        )
        assert cursore.fetchone()["stato"] == "Pronto"
