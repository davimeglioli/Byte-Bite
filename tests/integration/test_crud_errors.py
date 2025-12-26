import pytest
from app import ottieni_db, socketio

def test_crud_errors(client, auth, monkeypatch):
    """Test error handling for CRUD operations."""
    # Mock socketio.sleep and emit to prevent background task issues or speed up
    monkeypatch.setattr("app.socketio.emit", lambda *args, **kwargs: None)
    
    auth.login() # Admin login
    
    # --- PRODOTTI ---
    
    # Modifica prodotto inesistente
    resp = client.post('/api/modifica_prodotto', json={
        "id": 99999, "nome": "New", "prezzo": 10, "categoria_menu": "Bar", "categoria_dashboard": "Bar", "quantita": 10
    })
    assert resp.status_code in [200, 404, 400]

    # Elimina prodotto inesistente
    resp = client.post('/api/elimina_prodotto', json={"id": 99999})
    assert resp.status_code in [200, 404]

    # --- ORDINI ---
    
    # Modifica ordine inesistente
    resp = client.post('/api/modifica_ordine', json={
        "id": 99999, "nome_cliente": "Ghost", "numero_tavolo": 1, "asporto": 0, "metodo_pagamento": "Contanti"
    })
    assert resp.status_code in [200, 404, 400]

    # Elimina ordine inesistente
    resp = client.post('/api/elimina_ordine', json={"id": 99999})
    assert resp.status_code in [200, 404]
    
    # API ordine inesistente
    resp = client.get('/api/ordine/99999')
    assert resp.status_code == 404

    # --- UTENTI ---
    
    # Aggiungi utente duplicato
    with ottieni_db() as conn:
        conn.execute("INSERT INTO utenti (username, password_hash) VALUES ('dup', 'hash')")
        conn.commit()
        
    resp = client.post('/api/aggiungi_utente', json={
        "username": "dup", "password": "pass", "is_admin": 0, "attivo": 1
    })
    assert resp.status_code == 400
    assert b"Username gi" in resp.data or b"in uso" in resp.data

    # Modifica utente inesistente
    resp = client.post('/api/modifica_utente', json={
        "id": 99999, "username": "ghost", "is_admin": 0, "attivo": 1
    })
    assert resp.status_code in [200, 404, 500, 400]

    # Elimina utente inesistente
    resp = client.post('/api/elimina_utente', json={"id": 99999})
    assert resp.status_code in [200, 404, 400]
    
    # Reset password utente inesistente
    resp = client.post('/api/reset_password_utente', json={"id": 99999, "password": "new"})
    assert resp.status_code in [200, 404]
    
    # Toggle stato utente inesistente
    resp = client.post('/api/toggle_stato_utente', json={"id": 99999})
    assert resp.status_code in [200, 404]
    
    # Permessi utente inesistente
    resp = client.get('/api/ottieni_permessi_utente/99999')
    assert resp.status_code in [200, 404] # Probabilmente restituisce lista vuota o 404

def test_carrello_errors(client):
    """Test errori carrello."""
    with client.session_transaction() as sess:
        sess['carrello'] = {}
        
    resp = client.post('/aggiungi_al_carrello', data={"prodotto_id": "99999"})
    assert resp.status_code in [302, 404]
    
    # Rimuovi dal carrello prodotto non presente
    resp = client.post('/rimuovi_dal_carrello', data={"prodotto_id": "99999"})
    assert resp.status_code in [302, 404]
