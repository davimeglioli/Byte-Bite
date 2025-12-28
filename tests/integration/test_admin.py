import pytest
from app import ottieni_db

def test_admin_crea_utente(client):
    """Testa che un admin possa creare nuovi utenti."""
    # Setup Admin
    with ottieni_db() as conn:
        conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
                     ("admin_test", "hash", 1, 1))
        # Recupera ID
        admin_id = conn.execute("SELECT id FROM utenti WHERE username='admin_test'").fetchone()["id"]
        conn.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)", (admin_id, "ADMIN"))
        conn.commit()

    # Login Admin
    with client.session_transaction() as sess:
        sess["id_utente"] = admin_id
        sess["username"] = "admin_test"
        sess["is_admin"] = True

    # Creazione nuovo utente
    payload = {
        "username": "nuovo_utente",
        "password": "password123",
        "ruolo": "staff",
        "permessi": ["CASSA", "CUCINA"]
    }
    resp = client.post('/api/aggiungi_utente', json=payload, follow_redirects=True)
    assert resp.status_code == 200
    
    # Verifica DB
    with ottieni_db() as conn:
        user = conn.execute("SELECT * FROM utenti WHERE username='nuovo_utente'").fetchone()
        assert user is not None
        assert user["is_admin"] == 0
        
        permessi = conn.execute("SELECT pagina FROM permessi_pagine WHERE utente_id=?", (user["id"],)).fetchall()
        pagine = [p["pagina"] for p in permessi]
        assert "CASSA" in pagine
        assert "CUCINA" in pagine

def test_admin_statistiche(client):
    """Testa la visualizzazione delle statistiche."""
    # Setup Admin (riutilizziamo o creiamo nuovo)
    # Per brevità, assumiamo sessione già settata o la rifacciamo
    with ottieni_db() as conn:
        conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
                     ("admin_stats", "hash", 1, 1))
        admin_id = conn.execute("SELECT id FROM utenti WHERE username='admin_stats'").fetchone()["id"]
        conn.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)", (admin_id, "ADMIN"))
        conn.commit()

    with client.session_transaction() as sess:
        sess["id_utente"] = admin_id
        sess["username"] = "admin_stats"
        sess["is_admin"] = True
        
    # La rotta è /api/statistiche/
    resp = client.get('/api/statistiche/')
    assert resp.status_code == 200
    # La risposta è JSON, non HTML
    assert resp.json is not None

def test_admin_toggle_utente(client):
    """Testa attivazione/disattivazione utente."""
    # Setup Admin e Utente Target
    with ottieni_db() as conn:
        conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
                     ("admin_toggle", "hash", 1, 1))
        conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
                     ("target_user", "hash", 0, 1))
        
        admin_id = conn.execute("SELECT id FROM utenti WHERE username='admin_toggle'").fetchone()["id"]
        target_id = conn.execute("SELECT id FROM utenti WHERE username='target_user'").fetchone()["id"]
        
        conn.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)", (admin_id, "ADMIN"))
        conn.commit()

    with client.session_transaction() as sess:
        sess["id_utente"] = admin_id
        sess["username"] = "admin_toggle"
        sess["is_admin"] = True
        
    # Disattiva
    # La rotta è /api/modifica_utente (POST JSON)
    payload = {
        "id_utente": target_id,
        "username": "target_user",
        "attivo": 0,
        "is_admin": 0,
        "permessi": []
    }
    resp = client.post('/api/modifica_utente', json=payload)
    assert resp.status_code == 200
    
    with ottieni_db() as conn:
        stato = conn.execute("SELECT attivo FROM utenti WHERE id=?", (target_id,)).fetchone()["attivo"]
        assert stato == 0
        
    # Riattiva
    payload["attivo"] = 1
    client.post('/api/modifica_utente', json=payload)
    with ottieni_db() as conn:
        stato = conn.execute("SELECT attivo FROM utenti WHERE id=?", (target_id,)).fetchone()["attivo"]
        assert stato == 1

def test_admin_modifica_utente_permessi_duplicati(client):
    with ottieni_db() as conn:
        conn.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("admin_permessi", "hash", 1, 1),
        )
        conn.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("target_permessi", "hash", 0, 1),
        )
        admin_id = conn.execute("SELECT id FROM utenti WHERE username='admin_permessi'").fetchone()["id"]
        target_id = conn.execute("SELECT id FROM utenti WHERE username='target_permessi'").fetchone()["id"]
        conn.commit()

    with client.session_transaction() as sess:
        sess["id_utente"] = admin_id
        sess["username"] = "admin_permessi"
        sess["is_admin"] = True

    payload = {
        "id_utente": target_id,
        "username": "target_permessi",
        "attivo": 1,
        "is_admin": 0,
        "permessi": ["CASSA", "CASSA", "DASHBOARD", ""],
    }
    resp = client.post("/api/modifica_utente", json=payload)
    assert resp.status_code == 200

    with ottieni_db() as conn:
        permessi = conn.execute(
            "SELECT pagina FROM permessi_pagine WHERE utente_id = ? ORDER BY pagina",
            (target_id,),
        ).fetchall()
        pagine = [p["pagina"] for p in permessi]
        assert pagine == ["CASSA", "DASHBOARD"]
