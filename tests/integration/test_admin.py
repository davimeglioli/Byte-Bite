from app import ottieni_db

# ==================== Amministrazione ====================


def test_admin_crea_utente(cliente):
    # Crea un admin nel DB temporaneo e assegna permessi.
    with ottieni_db() as connessione:
        # Inserisce utente admin.
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("admin_test", "hash", 1, 1),
        )
        # Recupera id admin appena creato.
        id_admin = connessione.execute(
            "SELECT id FROM utenti WHERE username = 'admin_test'"
        ).fetchone()["id"]
        # Assegna permesso per pagina admin.
        connessione.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)",
            (id_admin, "ADMIN"),
        )
        # Commit delle modifiche.
        connessione.commit()

    # Simula sessione autenticata come admin.
    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_admin
        sessione["username"] = "admin_test"
        sessione["is_admin"] = True

    # Prepara payload per creazione utente staff.
    payload = {
        "username": "nuovo_utente",
        "password": "password123",
        "ruolo": "staff",
        "permessi": ["CASSA", "CUCINA"],
    }
    # Esegue chiamata API e segue eventuali redirect.
    risposta = cliente.post("/api/aggiungi_utente", json=payload, follow_redirects=True)
    # Verifica esito OK.
    assert risposta.status_code == 200

    # Verifica che utente e permessi siano stati creati.
    with ottieni_db() as connessione:
        utente = connessione.execute(
            "SELECT * FROM utenti WHERE username = 'nuovo_utente'"
        ).fetchone()
        assert utente is not None
        assert utente["is_admin"] == 0

        # Legge i permessi associati all'utente appena creato.
        permessi = connessione.execute(
            "SELECT pagina FROM permessi_pagine WHERE utente_id = ?",
            (utente["id"],),
        ).fetchall()
        pagine = [p["pagina"] for p in permessi]
        # Verifica che i permessi attesi siano presenti.
        assert "CASSA" in pagine
        assert "CUCINA" in pagine

def test_admin_attiva_e_disattiva_utente(cliente):
    # Crea admin e utente target nel DB temporaneo.
    with ottieni_db() as connessione:
        # Inserisce admin.
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("admin_toggle", "hash", 1, 1),
        )
        # Inserisce utente target attivo.
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("utente_target", "hash", 0, 1),
        )

        # Recupera id admin e id target.
        id_admin = connessione.execute(
            "SELECT id FROM utenti WHERE username = 'admin_toggle'"
        ).fetchone()["id"]
        id_target = connessione.execute(
            "SELECT id FROM utenti WHERE username = 'utente_target'"
        ).fetchone()["id"]

        # Assegna permesso admin per accedere alle API.
        connessione.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)",
            (id_admin, "ADMIN"),
        )
        # Commit delle modifiche.
        connessione.commit()

    # Simula login admin via sessione.
    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_admin
        sessione["username"] = "admin_toggle"
        sessione["is_admin"] = True

    # Payload per disattivare utente target.
    payload = {
        "id_utente": id_target,
        "username": "utente_target",
        "attivo": 0,
        "is_admin": 0,
        "permessi": [],
    }
    # Chiama API di modifica utente.
    risposta = cliente.post("/api/modifica_utente", json=payload)
    # Verifica risposta OK.
    assert risposta.status_code == 200

    # Verifica che lo stato sia stato aggiornato a 0.
    with ottieni_db() as connessione:
        stato = connessione.execute(
            "SELECT attivo FROM utenti WHERE id = ?",
            (id_target,),
        ).fetchone()["attivo"]
        assert stato == 0

    # Riattiva utente target e verifica lo stato.
    payload["attivo"] = 1
    cliente.post("/api/modifica_utente", json=payload)
    with ottieni_db() as connessione:
        stato = connessione.execute(
            "SELECT attivo FROM utenti WHERE id = ?",
            (id_target,),
        ).fetchone()["attivo"]
        assert stato == 1

def test_admin_modifica_utente_rimuove_permessi_duplicati(cliente):
    # Crea admin e utente target senza permessi.
    with ottieni_db() as connessione:
        # Inserisce admin.
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("admin_permessi", "hash", 1, 1),
        )
        # Inserisce utente target.
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("target_permessi", "hash", 0, 1),
        )
        # Recupera id dei due utenti.
        id_admin = connessione.execute(
            "SELECT id FROM utenti WHERE username = 'admin_permessi'"
        ).fetchone()["id"]
        id_target = connessione.execute(
            "SELECT id FROM utenti WHERE username = 'target_permessi'"
        ).fetchone()["id"]
        # Commit delle modifiche.
        connessione.commit()

    # Simula login admin via sessione.
    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_admin
        sessione["username"] = "admin_permessi"
        sessione["is_admin"] = True

    # Invia permessi duplicati per verificare deduplica lato backend.
    payload = {
        "id_utente": id_target,
        "username": "target_permessi",
        "attivo": 1,
        "is_admin": 0,
        "permessi": ["CASSA", "CASSA", "DASHBOARD", ""],
    }
    # Chiama endpoint di modifica.
    risposta = cliente.post("/api/modifica_utente", json=payload)
    # Verifica esito OK.
    assert risposta.status_code == 200

    # Verifica che i permessi salvati siano deduplicati.
    with ottieni_db() as connessione:
        permessi = connessione.execute(
            "SELECT pagina FROM permessi_pagine WHERE utente_id = ? ORDER BY pagina",
            (id_target,),
        ).fetchall()
        pagine = [p["pagina"] for p in permessi]
        assert pagine == ["CASSA", "DASHBOARD"]


def test_admin_statistiche_restituisce_json(cliente):
    # Crea un admin abilitato per accesso statistiche.
    with ottieni_db() as connessione:
        # Inserisce admin.
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("admin_stats", "hash", 1, 1),
        )
        # Recupera id admin.
        id_admin = connessione.execute(
            "SELECT id FROM utenti WHERE username = 'admin_stats'"
        ).fetchone()["id"]
        # Assegna permesso admin.
        connessione.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)",
            (id_admin, "ADMIN"),
        )
        # Commit delle modifiche.
        connessione.commit()

    # Simula sessione autenticata.
    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_admin
        sessione["username"] = "admin_stats"
        sessione["is_admin"] = True

    # Richiede le statistiche.
    risposta = cliente.get("/api/statistiche/")
    # Verifica status e payload JSON.
    assert risposta.status_code == 200
    assert risposta.json is not None
