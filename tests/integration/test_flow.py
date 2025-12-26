import pytest
import json
import time
from app import ottieni_db, socketio

def test_flusso_completo_ordine(client, monkeypatch):
    """
    Testa un intero ciclo di vita di un ordine:
    1. Login Staff
    2. Creazione Ordine (Cassa)
    3. Visualizzazione in Dashboard (Cucina)
    4. Avanzamento di stato (In Attesa -> In Preparazione -> Pronto -> Completato)
    """

    # --- 0. SETUP: Dati iniziali ---
    with ottieni_db() as conn:
        # Utente Staff
        conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
                     ("cassiere", "hash_finto", 0, 1))
        # Permesso Cassa
        id_staff = conn.execute("SELECT id FROM utenti WHERE username='cassiere'").fetchone()["id"]
        conn.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)", (id_staff, "CASSA"))
        
        # Prodotto
        conn.execute(
            "INSERT INTO prodotti (id, nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (10, "Carbonara", 12.0, "Primi", "Cucina", 50, 0)
        )
        conn.commit()

    # Mock SocketIO per evitare errori di connessione reale
    monkeypatch.setattr("app.emissione_sicura", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    # --- 1. LOGIN (Staff) ---
    with client.session_transaction() as sess:
        sess["id_utente"] = id_staff
        sess["username"] = "cassiere"

    # --- 2. CREAZIONE ORDINE (Cassa) ---
    dati_ordine = {
        "nome_cliente": "FlussoTest",
        "numero_tavolo": "5",
        "numero_persone": "2",
        "metodo_pagamento": "Contanti",
        "prodotti": json.dumps([{"id": 10, "quantita": 2, "nome": "Carbonara"}])
    }
    resp = client.post('/aggiungi_ordine/', data=dati_ordine, follow_redirects=True)
    assert resp.status_code == 200
    
    # Recupera ID ordine creato
    with ottieni_db() as conn:
        ordine = conn.execute("SELECT id FROM ordini WHERE nome_cliente = 'FlussoTest'").fetchone()
        assert ordine is not None
        id_ordine = ordine["id"]

    # --- 3. VERIFICA DASHBOARD (API parziale) ---
    with ottieni_db() as conn:
        conn.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)", (id_staff, "DASHBOARD"))
        conn.commit()

    resp = client.get('/dashboard/cucina/partial')
    assert resp.status_code == 200
    dati = resp.get_json()
    assert "Carbonara" in dati["html_non_completati"]
    assert "FlussoTest" in dati["html_non_completati"]

    # --- 4. AVANZAMENTO STATO ---
    # Simuliamo il click su "Avanza Stato" nella dashboard
    
    # A. In Attesa -> In Preparazione
    payload = {"ordine_id": id_ordine, "categoria": "Cucina"}
    resp = client.post('/cambia_stato/', json=payload)
    assert resp.status_code == 200
    assert resp.get_json()["nuovo_stato"] == "In Preparazione"

    # Verifica DB
    with ottieni_db() as conn:
        stato = conn.execute("SELECT stato FROM ordini_prodotti WHERE ordine_id=? AND prodotto_id=10", (id_ordine,)).fetchone()["stato"]
        assert stato == "In Preparazione"

    # B. In Preparazione -> Pronto
    resp = client.post('/cambia_stato/', json=payload)
    assert resp.get_json()["nuovo_stato"] == "Pronto"
    
    from app import cambia_stato_automatico
    
    assert resp.get_json()["nuovo_stato"] == "Pronto"
    
    resp = client.post('/cambia_stato/', json=payload)
    assert resp.get_json()["nuovo_stato"] == "In Preparazione"
    
    # Ora riportiamolo a Pronto
    resp = client.post('/cambia_stato/', json=payload)
    assert resp.get_json()["nuovo_stato"] == "Pronto"
    
    # E simuliamo il completamento forzato (come se il timer scadesse)
    with ottieni_db() as conn:
        conn.execute("UPDATE ordini_prodotti SET stato='Completato' WHERE ordine_id=? AND prodotto_id=10", (id_ordine,))
        conn.commit()

    # Verifica che l'ordine sia sparito dalla lista "non completati"
    resp = client.get('/dashboard/cucina/partial')
    dati = resp.get_json()
    assert "FlussoTest" not in dati["html_non_completati"]