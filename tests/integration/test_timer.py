from app import cambia_stato_automatico, ottieni_db, socketio, timer_attivi

# ==================== Timer ====================


def test_timer_completa_ordine_pronto(cliente):
    # Inserisce un ordine in stato Pronto e un prodotto associato.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (200, 'Test Timer', 10, 100, 0, 'Test', 'Cucina')"
        )
        connessione.execute(
            "INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (200, 'Timer Client', 1, CURRENT_TIMESTAMP, 0, 0, 'Contanti')"
        )
        connessione.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (200, 200, 1, 'Pronto')"
        )
        # Commit degli inserimenti.
        connessione.commit()

    # Prepara chiave timer e stato attivo.
    ordine_id = 200
    categoria = "Cucina"
    timer_id = "test-timer-id"
    chiave_timer = (ordine_id, categoria)

    # Registra timer attivo.
    timer_attivi[chiave_timer] = {"annulla": False, "id": timer_id}

    # Evita attese reali.
    original_sleep = socketio.sleep
    socketio.sleep = lambda x: None

    # Invoca la funzione di completamento e ripristina sleep.
    try:
        cambia_stato_automatico(ordine_id, categoria, timer_id)
    finally:
        socketio.sleep = original_sleep

    # Verifica che stato e flag completato siano aggiornati.
    with ottieni_db() as connessione:
        stato = connessione.execute(
            "SELECT stato FROM ordini_prodotti WHERE ordine_id = 200 AND prodotto_id = 200"
        ).fetchone()["stato"]
        completato = connessione.execute(
            "SELECT completato FROM ordini WHERE id = 200"
        ).fetchone()["completato"]

    assert stato == "Completato"
    assert completato == 1
    # Verifica che il timer sia stato rimosso.
    assert chiave_timer not in timer_attivi


def test_timer_non_modifica_se_annullato(cliente):
    # Inserisce un ordine in stato Pronto e simula timer già annullato.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (201, 'Test Timer Cancel', 10, 100, 0, 'Test', 'Cucina')"
        )
        connessione.execute(
            "INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (201, 'Timer Client 2', 1, CURRENT_TIMESTAMP, 0, 0, 'Contanti')"
        )
        connessione.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (201, 201, 1, 'Pronto')"
        )
        # Commit degli inserimenti.
        connessione.commit()

    # Prepara chiave timer annullata.
    ordine_id = 201
    categoria = "Cucina"
    timer_id = "test-cancel-id"
    chiave_timer = (ordine_id, categoria)

    # Registra timer come annullato.
    timer_attivi[chiave_timer] = {"annulla": True, "id": timer_id}

    # Evita attese reali.
    original_sleep = socketio.sleep
    socketio.sleep = lambda x: None

    # Invoca la funzione e ripristina sleep.
    try:
        cambia_stato_automatico(ordine_id, categoria, timer_id)
    finally:
        socketio.sleep = original_sleep

    # Verifica che lo stato sia rimasto Pronto.
    with ottieni_db() as connessione:
        stato = connessione.execute(
            "SELECT stato FROM ordini_prodotti WHERE ordine_id = 201 AND prodotto_id = 201"
        ).fetchone()["stato"]

    assert stato == "Pronto"
