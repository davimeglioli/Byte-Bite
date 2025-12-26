import pytest
from app import ottieni_db, ricalcola_statistiche, cambia_stato_automatico, timer_attivi, ottieni_utente_loggato, emissione_sicura, socketio, app
import bcrypt
import logging

def test_ricalcola_statistiche_carta(client):
    """Test ricalcola_statistiche con pagamento Carta."""
    with ottieni_db() as conn:
        conn.execute("DELETE FROM ordini")
        conn.execute("DELETE FROM ordini_prodotti")
        conn.execute("DELETE FROM statistiche_totali")
        
        # Inserisci ordine con Carta
        conn.execute("INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (700, 'Card Prod', 20, 100, 0, 'Test', 'Bar')")
        conn.execute("INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (700, 'Card Client', 1, '2025-01-01 12:00:00', 1, 0, 'Carta')")
        conn.execute("INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (700, 700, 1, 'Completato')")
        conn.commit()

    # Mock socketio to avoid background tasks
    original_emit = socketio.emit
    socketio.emit = lambda *args, **kwargs: None
    
    try:
        ricalcola_statistiche()
    finally:
        socketio.emit = original_emit
        
    with ottieni_db() as conn:
        stats = conn.execute("SELECT * FROM statistiche_totali").fetchone()
        assert stats["totale_carta"] == 20
        assert stats["totale_contanti"] == 0

def test_cambia_stato_automatico_annullato(client, monkeypatch):
    """Test che il timer si ferma se annullato."""
    # Setup dati
    ordine_id = 701
    categoria = 'Cucina'
    timer_id = 'test_timer'
    chiave = (ordine_id, categoria)
    
    # Simula timer attivo e poi annullato
    timer_attivi[chiave] = {"id": timer_id, "annulla": True}
    
    # Mock sleep per non aspettare davvero
    monkeypatch.setattr("app.socketio.sleep", lambda x: None)
    
    # Esegui funzione (dovrebbe uscire subito o dopo i controlli senza fare update)
    with ottieni_db() as conn:
        conn.execute("DELETE FROM ordini WHERE id = ?", (ordine_id,))
        conn.execute("INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (701, 'Timer Prod', 10, 100, 0, 'Test', 'Cucina')")
        conn.execute("INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (?, 'Timer Client', 1, '2025-01-01 12:00:00', 0, 0, 'Contanti')", (ordine_id,))
        conn.execute("INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (?, 701, 1, 'Pronto')", (ordine_id,))
        conn.commit()
        
    cambia_stato_automatico(ordine_id, categoria, timer_id)
    
    # Verifica che lo stato sia ancora 'Pronto' (non 'Completato')
    with ottieni_db() as conn:
        stato = conn.execute("SELECT stato FROM ordini_prodotti WHERE ordine_id = ? AND prodotto_id = 701", (ordine_id,)).fetchone()["stato"]
        assert stato == 'Pronto'

def test_login_wrong_password(client):
    """Test login con username corretto ma password errata."""
    password = "correct_password"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    with ottieni_db() as conn:
        conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES ('validuser', ?, 0, 1)", (password_hash,))
        conn.commit()
        
    response = client.post('/login/', data={
        "username": "validuser",
        "password": "wrong_password"
    }, follow_redirects=True)
    
    assert b"Username o password errata" in response.data

def test_ottieni_utente_loggato_no_session(client):
    """Test ottieni_utente_loggato senza sessione."""
    with app.test_request_context():
        # Session is empty by default in test context
        assert ottieni_utente_loggato() is None

def test_emissione_sicura_errore(client, caplog):
    """Test emissione_sicura gestisce eccezioni."""
    # Mock socketio.emit to raise exception
    original_emit = socketio.emit
    def mock_emit(*args, **kwargs):
        raise Exception("Socket Error")
    socketio.emit = mock_emit
    
    try:
        with caplog.at_level(logging.WARNING):
            emissione_sicura('test_event', {})
            assert "Errore durante emissione: Socket Error" in caplog.text
    finally:
        socketio.emit = original_emit
