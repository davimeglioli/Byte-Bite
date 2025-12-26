import pytest
from app import ottieni_db, socketio

def setup_admin(client):
    """Helper per creare e loggare un admin."""
    with ottieni_db() as conn:
        conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
                     ("admin_crud", "hash", 1, 1))
        admin_id = conn.execute("SELECT id FROM utenti WHERE username='admin_crud'").fetchone()["id"]
        conn.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)", (admin_id, "AMMINISTRAZIONE"))
        conn.commit()

    with client.session_transaction() as sess:
        sess["id_utente"] = admin_id
        sess["username"] = "admin_crud"
        sess["is_admin"] = 1
    return admin_id

def test_gestione_prodotti(client):
    """Test completo CRUD prodotti."""
    setup_admin(client)
    
    # 1. Aggiungi Prodotto
    payload_add = {
        "nome": "Nuovo Piatto",
        "categoria_dashboard": "Cucina",
        "categoria_menu": "Primi",
        "prezzo": 12.5,
        "quantita": 10,
        "disponibile": True
    }
    resp = client.post('/api/aggiungi_prodotto', json=payload_add)
    assert resp.status_code == 200
    
    with ottieni_db() as conn:
        prod = conn.execute("SELECT * FROM prodotti WHERE nome='Nuovo Piatto'").fetchone()
        assert prod is not None
        prod_id = prod["id"]
        assert prod["quantita"] == 10
        assert prod["disponibile"] == 1

    # 2. Modifica Prodotto
    payload_mod = {
        "id": prod_id,
        "nome": "Piatto Modificato",
        "categoria_dashboard": "Cucina",
        "quantita": 5
    }
    resp = client.post('/api/modifica_prodotto', json=payload_mod)
    assert resp.status_code == 200
    
    with ottieni_db() as conn:
        prod = conn.execute("SELECT * FROM prodotti WHERE id=?", (prod_id,)).fetchone()
        assert prod["nome"] == "Piatto Modificato"
        assert prod["quantita"] == 5

    # 3. Rifornisci Prodotto
    payload_refill = {
        "id": prod_id,
        "quantita": 20
    }
    resp = client.post('/api/rifornisci_prodotto', json=payload_refill)
    assert resp.status_code == 200
    
    with ottieni_db() as conn:
        qty = conn.execute("SELECT quantita FROM prodotti WHERE id=?", (prod_id,)).fetchone()["quantita"]
        assert qty == 25 # 5 + 20

    # 4. Elimina Prodotto
    resp = client.post('/api/elimina_prodotto', json={"id": prod_id})
    assert resp.status_code == 200
    
    with ottieni_db() as conn:
        prod = conn.execute("SELECT * FROM prodotti WHERE id=?", (prod_id,)).fetchone()
        assert prod is None

def test_gestione_ordini(client):
    """Test modifica ed eliminazione ordini."""
    setup_admin(client)
    
    # Setup ordine esistente
    with ottieni_db() as conn:
        conn.execute("INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (300, 'Pizza', 10, 100, 0, 'Pizze', 'Cucina')")
        conn.execute("INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (300, 'Mario', 5, CURRENT_TIMESTAMP, 0, 0, 'Contanti')")
        conn.execute("INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (300, 300, 2, 'In Attesa')")
        # Decrementa magazzino per simulare ordine reale
        conn.execute("UPDATE prodotti SET quantita=98 WHERE id=300")
        conn.commit()

    # 1. Dettagli Ordine
    resp = client.get('/api/ordine/300/dettagli')
    assert resp.status_code == 200
    assert b"Pizza" in resp.data
    assert b"2" in resp.data # Quantità

    # 2. Modifica Ordine
    payload_mod = {
        "id_ordine": 300,
        "nome_cliente": "Luigi",
        "numero_tavolo": 10,
        "numero_persone": 4,
        "metodo_pagamento": "Carta"
    }
    resp = client.post('/api/modifica_ordine', json=payload_mod)
    assert resp.status_code == 200
    
    with ottieni_db() as conn:
        ord = conn.execute("SELECT * FROM ordini WHERE id=300").fetchone()
        assert ord["nome_cliente"] == "Luigi"
        assert ord["numero_tavolo"] == 10
        assert ord["metodo_pagamento"] == "Carta"

    # 3. Elimina Ordine
    resp = client.post('/api/elimina_ordine', json={"id": 300})
    assert resp.status_code == 200
    
    with ottieni_db() as conn:
        ord = conn.execute("SELECT * FROM ordini WHERE id=300").fetchone()
        assert ord is None
        # Verifica ripristino magazzino
        qty = conn.execute("SELECT quantita FROM prodotti WHERE id=300").fetchone()["quantita"]
        assert qty == 100 # 98 + 2

def test_elimina_utente(client):
    """Test eliminazione utente."""
    my_id = setup_admin(client)
    
    # Setup utente da eliminare
    with ottieni_db() as conn:
        conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
                     ("to_delete", "hash", 0, 1))
        target_id = conn.execute("SELECT id FROM utenti WHERE username='to_delete'").fetchone()["id"]
        conn.commit()

    # Tentativo eliminazione se stessi
    # resp = client.post('/api/elimina_utente', json={"id_utente": my_id})
    # Il backend potrebbe ritornare 400 se c'è controllo (riga 1021 app.py)
    
    resp = client.post('/api/elimina_utente', json={"id_utente": target_id})
    if resp.status_code == 302:
        print(f"Redirected to: {resp.location}")
    assert resp.status_code == 200
    
    with ottieni_db() as conn:
        user = conn.execute("SELECT * FROM utenti WHERE id=?", (target_id,)).fetchone()
        assert user is None

def test_api_extra_admin(client):
    """Test rotte extra admin (HTML rows, JSON order details)."""
    setup_admin(client)

    # 1. Setup dati
    with ottieni_db() as conn:
        conn.execute("INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (400, 'Test Extra', 5, 50, 0, 'Extra', 'Bar')")
        conn.execute("INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (400, 'Extra Client', 9, CURRENT_TIMESTAMP, 0, 0, 'Carta')")
        conn.execute("INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (400, 400, 1, 'Pronto')")
        conn.commit()

    # 2. API JSON Ordine
    resp = client.get('/api/ordine/400')
    assert resp.status_code == 200
    assert resp.json["nome_cliente"] == "Extra Client"
    assert len(resp.json["items"]) == 1

    # 3. HTML Rows Ordini
    resp = client.get('/api/amministrazione/ordini_html')
    assert resp.status_code == 200
    assert b"Extra Client" in resp.data

    # 4. HTML Rows Prodotti
    resp = client.get('/api/amministrazione/prodotti_html')
    assert resp.status_code == 200
    assert b"Test Extra" in resp.data

def test_ricalcola_statistiche_direct(client):
    """Test diretto della funzione ricalcola_statistiche."""
    from app import ricalcola_statistiche
    
    # Setup dati
    with ottieni_db() as conn:
        # Pulisci stats
        conn.execute("DELETE FROM statistiche_totali")
        conn.execute("DELETE FROM statistiche_categorie")
        conn.execute("DELETE FROM statistiche_ore")
        
        # Ordine completato
        conn.execute("INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (500, 'Stat Prod', 10, 100, 0, 'Test', 'Cucina')")
        conn.execute("INSERT INTO ordini (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento) VALUES (500, 'Stat Client', 1, '2025-01-01 12:00:00', 1, 0, 'Contanti')")
        conn.execute("INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (500, 500, 2, 'Completato')")
        conn.commit()
    
    # Esegui funzione (mocked socketio already handles emissione_sicura if it uses it? No, emissione_sicura uses socketio.emit)
    # emissione_sicura is likely using socketio.emit. Mock socketio.emit just in case.
    
    original_emit = socketio.emit
    socketio.emit = lambda *args, **kwargs: None
    
    try:
        ricalcola_statistiche()
    finally:
        socketio.emit = original_emit

    # Verifica DB
    with ottieni_db() as conn:
        tot = conn.execute("SELECT * FROM statistiche_totali").fetchone()
        assert tot["ordini_totali"] >= 1
        assert tot["totale_incasso"] >= 20 # 2 * 10
        
        cat = conn.execute("SELECT * FROM statistiche_categorie WHERE categoria_dashboard='Cucina'").fetchone()
        assert cat["totale"] >= 2
