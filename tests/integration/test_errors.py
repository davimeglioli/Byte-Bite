import pytest
from app import ottieni_db
import sqlite3

def test_errore_db_creazione_ordine(client, monkeypatch):
    """Testa comportamento quando il DB fallisce durante creazione ordine."""
    
    # Setup login
    with ottieni_db() as conn:
        conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
                     ("cassiere_err", "hash", 0, 1))
        uid = conn.execute("SELECT id FROM utenti WHERE username='cassiere_err'").fetchone()["id"]
        conn.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)", (uid, "CASSA"))
        conn.commit()
        
    with client.session_transaction() as sess:
        sess["id_utente"] = uid
        sess["username"] = "cassiere_err"
        
    # Tentativo con ID inesistente
    # La rotta si aspetta 'prodotti' come stringa JSON
    data = {
        "prodotti": '[{"id": 99999, "quantita": 1}]',
        "nome_cliente": "Test Error",
        "numero_tavolo": "5",
        "metodo_pagamento": "Contanti"
    }

    # La rotta è /aggiungi_ordine/ (senza prefisso cassa)
    resp = client.post('/aggiungi_ordine/', data=data, follow_redirects=False)
    assert resp.status_code == 303 # Redirect
    assert "error=" in resp.location

def test_prodotto_esaurito_concorrente(client):
    """Testa concorrenza: due ordini simultanei per l'ultimo prodotto."""
    # Setup: 1 prodotto con qta=1
    with ottieni_db() as conn:
        conn.execute("INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (99, 'Ultimo', 10, 1, 0, 'Test', 'Cucina')")
        conn.commit()
        
        # Login
        conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
                     ("user_conc", "hash", 0, 1))
        uid = conn.execute("SELECT id FROM utenti WHERE username='user_conc'").fetchone()["id"]
        conn.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)", (uid, "CASSA"))
        conn.commit()

    with client.session_transaction() as sess:
        sess["id_utente"] = uid
    
    # Ordine 1: Prende l'ultimo
    data = {
        "prodotti": '[{"id": 99, "quantita": 1}]',
        "nome_cliente": "Cliente 1",
        "numero_tavolo": "1",
        "metodo_pagamento": "Contanti"
    }
    # La rotta è /aggiungi_ordine/ (senza prefisso cassa)
    resp1 = client.post('/aggiungi_ordine/', data=data)
    assert resp1.status_code == 303
    assert "error" not in resp1.location
    
    # Ordine 2: Dovrebbe fallire
    data["nome_cliente"] = "Cliente 2"
    resp2 = client.post('/aggiungi_ordine/', data=data)
    assert resp2.status_code == 303
    assert "error" in resp2.location # Deve contenere errore prodotto esaurito
