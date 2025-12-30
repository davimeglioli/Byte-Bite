import logging
import bcrypt

from app import (
    app,
    cambia_stato_automatico,
    emissione_sicura,
    ottieni_db,
    ottieni_utente_loggato,
    ricalcola_statistiche,
    socketio,
    timer_attivi,
)

# ==================== Copertura ====================

def test_ricalcola_statistiche_calcola_totale_carta(cliente):
    # Prepara un ordine completato pagato con Carta.
    with ottieni_db() as connessione:
        # Pulisce tabelle rilevanti.
        connessione.execute("DELETE FROM ordini")
        connessione.execute("DELETE FROM ordini_prodotti")
        connessione.execute("DELETE FROM statistiche_totali")

        # Inserisce un prodotto e un ordine completato.
        connessione.execute(
            "INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (700, 'Card Prod', 20, 100, 0, 'Test', 'Bar')"
        )
        connessione.execute(
            "INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (700, 'Card Client', 1, '2025-01-01 12:00:00', 1, 0, 'Carta')"
        )
        connessione.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (700, 700, 1, 'Completato')"
        )
        # Commit inserimenti.
        connessione.commit()

    # Disabilita emit SocketIO per isolare il test.
    original_emit = socketio.emit
    socketio.emit = lambda *args, **kwargs: None

    # Esegue ricalcolo statistiche e ripristina emit.
    try:
        ricalcola_statistiche()
    finally:
        socketio.emit = original_emit

    # Verifica i totali carta/contanti.
    with ottieni_db() as connessione:
        stats = connessione.execute("SELECT * FROM statistiche_totali").fetchone()
        assert stats["totale_carta"] == 20
        assert stats["totale_contanti"] == 0

def test_cambia_stato_automatico_non_prosegue_se_annullato(cliente, monkeypatch):
    # Simula un timer già annullato prima della scadenza.
    ordine_id = 701
    categoria = "Cucina"
    timer_id = "test_timer"
    chiave = (ordine_id, categoria)

    # Registra lo stato del timer come annullato.
    timer_attivi[chiave] = {"id": timer_id, "annulla": True}

    # Evita attese reali durante il test.
    monkeypatch.setattr("app.socketio.sleep", lambda x: None)

    # Inserisce un ordine pronto per verificare che non venga completato.
    with ottieni_db() as connessione:
        connessione.execute("DELETE FROM ordini WHERE id = ?", (ordine_id,))
        connessione.execute(
            "INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (701, 'Timer Prod', 10, 100, 0, 'Test', 'Cucina')"
        )
        connessione.execute(
            "INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (?, 'Timer Client', 1, '2025-01-01 12:00:00', 0, 0, 'Contanti')",
            (ordine_id,),
        )
        connessione.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (?, 701, 1, 'Pronto')",
            (ordine_id,),
        )
        connessione.commit()

    # Chiama direttamente la funzione di completamento automatico.
    cambia_stato_automatico(ordine_id, categoria, timer_id)

    # Verifica che lo stato rimanga "Pronto".
    with ottieni_db() as connessione:
        stato = connessione.execute(
            "SELECT stato FROM ordini_prodotti WHERE ordine_id = ? AND prodotto_id = 701",
            (ordine_id,),
        ).fetchone()["stato"]
        assert stato == "Pronto"

def test_accesso_fallisce_con_password_sbagliata(cliente):
    # Crea un utente con password corretta.
    password = "correct_password"
    hash_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # Inserisce utente nel DB temporaneo.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES ('validuser', ?, 0, 1)",
            (hash_password,),
        )
        connessione.commit()

    # Tenta login con password errata.
    risposta = cliente.post(
        "/login/",
        data={"username": "validuser", "password": "wrong_password"},
        follow_redirects=True,
    )
    # Verifica messaggio di errore.
    assert b"Username o password errata" in risposta.data


def test_ottieni_utente_loggato_senza_sessione(cliente):
    # Crea un contesto request senza sessione.
    with app.test_request_context():
        # La funzione deve restituire None senza id_utente in sessione.
        assert ottieni_utente_loggato() is None

def test_emissione_sicura_gestisce_eccezioni(cliente, caplog):
    # Sostituisce socketio.emit con una funzione che lancia eccezione.
    original_emit = socketio.emit

    def mock_emit(*args, **kwargs):
        raise Exception("Socket Error")

    # Applica la sostituzione.
    socketio.emit = mock_emit

    # Verifica che l'eccezione venga loggata e non propagata.
    try:
        with caplog.at_level(logging.WARNING):
            emissione_sicura("test_event", {})
            assert "Errore durante emissione: Socket Error" in caplog.text
    finally:
        # Ripristina emit originale.
        socketio.emit = original_emit
