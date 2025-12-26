import pytest
import time
from app import app, socketio, ottieni_db, cambia_stato_automatico, timer_attivi

def test_timer_automatico_completamento(client):
    """Testa che un ordine 'Pronto' passi a 'Completato' dopo 300s (simulati)."""
    # 1. Setup DB
    with ottieni_db() as conn:
        # Crea prodotto e ordine
        conn.execute("INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (200, 'Test Timer', 10, 100, 0, 'Test', 'Cucina')")
        conn.execute("INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (200, 'Timer Client', 1, CURRENT_TIMESTAMP, 0, 0, 'Contanti')")
        conn.execute("INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (200, 200, 1, 'Pronto')")
        conn.commit()

    # 2. Registra timer finto
    ordine_id = 200
    categoria = 'Cucina'
    timer_id = "test-timer-id"
    chiave_timer = (ordine_id, categoria)
    
    timer_attivi[chiave_timer] = {"annulla": False, "id": timer_id}

    # 3. Invoca direttamente la funzione del timer
    
    original_sleep = socketio.sleep
    socketio.sleep = lambda x: None # No wait
    
    try:
        cambia_stato_automatico(ordine_id, categoria, timer_id)
    finally:
        socketio.sleep = original_sleep # Restore

    # 4. Verifica stato 'Completato'
    with ottieni_db() as conn:
        stato = conn.execute("SELECT stato FROM ordini_prodotti WHERE ordine_id=200 AND prodotto_id=200").fetchone()["stato"]
        completato = conn.execute("SELECT completato FROM ordini WHERE id=200").fetchone()["completato"]
    
    assert stato == 'Completato'
    assert completato == 1
    assert chiave_timer not in timer_attivi

def test_timer_annullamento(client):
    """Testa che il timer si interrompa se annullato (es. stato cambia manualmente)."""
    # 1. Setup
    with ottieni_db() as conn:
        conn.execute("INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (201, 'Test Timer Cancel', 10, 100, 0, 'Test', 'Cucina')")
        conn.execute("INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (201, 'Timer Client 2', 1, CURRENT_TIMESTAMP, 0, 0, 'Contanti')")
        conn.execute("INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (201, 201, 1, 'Pronto')")
        conn.commit()

    ordine_id = 201
    categoria = 'Cucina'
    timer_id = "test-cancel-id"
    chiave_timer = (ordine_id, categoria)
    
    timer_attivi[chiave_timer] = {"annulla": True, "id": timer_id} # Già annullato

    # Monkeypatch sleep
    original_sleep = socketio.sleep
    socketio.sleep = lambda x: None 
    
    try:
        cambia_stato_automatico(ordine_id, categoria, timer_id)
    finally:
        socketio.sleep = original_sleep

    # 2. Verifica che NON sia cambiato
    with ottieni_db() as conn:
        stato = conn.execute("SELECT stato FROM ordini_prodotti WHERE ordine_id=201 AND prodotto_id=201").fetchone()["stato"]
    
    assert stato == 'Pronto' # Non deve essere cambiato
