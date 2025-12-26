import json
import pytest
from app import ottieni_db

def test_aggiungi_ordine_successo(client, monkeypatch):
    """Testa la creazione corretta di un ordine."""
    
    # 1. Setup Dati nel DB
    with ottieni_db() as conn:
        # Creiamo un prodotto con quantità 10
        conn.execute(
            "INSERT INTO prodotti (id, nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "Pizza Margherita", 8.0, "Pizze", "Cucina", 10, 0)
        )
        conn.commit()

    # 2. Mock di SocketIO per evitare errori durante l'emissione
    monkeypatch.setattr("app.emissione_sicura", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    # 3. Payload della richiesta
    dati_ordine = {
        "nome_cliente": "Luigi",
        "numero_tavolo": "10",
        "numero_persone": "4",
        "metodo_pagamento": "Contanti",
        "isTakeaway": "", # Checkbox non checkata
        "prodotti": json.dumps([
            {"id": 1, "quantita": 2, "nome": "Pizza Margherita"}
        ])
    }

    # 4. Esegui richiesta POST
    response = client.post('/aggiungi_ordine/', data=dati_ordine)

    # 5. Verifiche
    assert response.status_code == 303  # Redirect dopo successo
    
    with ottieni_db() as conn:
        # Verifica creazione ordine
        ordine = conn.execute("SELECT * FROM ordini WHERE nome_cliente = 'Luigi'").fetchone()
        assert ordine is not None
        assert ordine["numero_tavolo"] == 10
        
        # Verifica decremento magazzino (10 - 2 = 8)
        prodotto = conn.execute("SELECT quantita, venduti FROM prodotti WHERE id = 1").fetchone()
        assert prodotto["quantita"] == 8
        assert prodotto["venduti"] == 2
        
        # Verifica riga ordini_prodotti
        op = conn.execute("SELECT * FROM ordini_prodotti WHERE ordine_id = ?", (ordine["id"],)).fetchone()
        assert op["prodotto_id"] == 1
        assert op["quantita"] == 2
        assert op["stato"] == "In Attesa"

def test_aggiungi_ordine_prodotto_esaurito(client):
    """Testa che l'ordine fallisca se non c'è abbastanza quantità."""
    
    # Setup: Prodotto con quantità 1
    with ottieni_db() as conn:
        conn.execute(
            "INSERT INTO prodotti (id, nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (2, "Pizza Speciale", 10.0, "Pizze", "Cucina", 1, 0)
        )
        conn.commit()

    # Tenta di ordinarne 2
    dati_ordine = {
        "nome_cliente": "Mario",
        "metodo_pagamento": "Carta",
        "prodotti": json.dumps([
            {"id": 2, "quantita": 2, "nome": "Pizza Speciale"}
        ])
    }

    response = client.post('/aggiungi_ordine/', data=dati_ordine)
    
    # Verifica redirect con errore (o gestione errore)
    # L'app fa redirect con ?error=...
    assert response.status_code == 303
    assert "error" in response.location
    
    # Verifica che la quantità non sia cambiata
    with ottieni_db() as conn:
        prodotto = conn.execute("SELECT quantita FROM prodotti WHERE id = 2").fetchone()
        assert prodotto["quantita"] == 1
        
        # Verifica che l'ordine sia coerente (esiste ma senza prodotti o gestito)
        ordine = conn.execute("SELECT * FROM ordini WHERE nome_cliente = 'Mario'").fetchone()
        if ordine:
            prodotti_ordine = conn.execute("SELECT * FROM ordini_prodotti WHERE ordine_id = ?", (ordine["id"],)).fetchall()
            assert len(prodotti_ordine) == 0

def test_ordine_asporto(client, monkeypatch):
    """Testa che un ordine da asporto ignori tavolo e persone."""
    monkeypatch.setattr("app.emissione_sicura", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    dati_ordine = {
        "nome_cliente": "Giulia",
        "isTakeaway": "on", # Checkbox attiva
        "numero_tavolo": "99", # Dovrebbe essere ignorato
        "metodo_pagamento": "Contanti",
        "prodotti": json.dumps([]) # Nessun prodotto, solo per testare header
    }
    
    client.post('/aggiungi_ordine/', data=dati_ordine)
    
    with ottieni_db() as conn:
        ordine = conn.execute("SELECT asporto, numero_tavolo FROM ordini WHERE nome_cliente = 'Giulia'").fetchone()
        assert ordine["asporto"] == 1
        assert ordine["numero_tavolo"] is None
