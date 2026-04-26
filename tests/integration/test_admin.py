from app import ottieni_db

# ==================== Amministrazione ====================


def test_admin_crea_utente(cliente):
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("admin_test", "hash", True, True),
        )
        id_admin = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
            (id_admin, "ADMIN"),
        )
        connessione.commit()

    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_admin
        sessione["username"] = "admin_test"
        sessione["is_admin"] = True

    payload = {
        "username": "nuovo_utente",
        "password": "password123",
        "ruolo": "staff",
        "permessi": ["CASSA", "CUCINA"],
    }
    risposta = cliente.post("/api/aggiungi_utente", json=payload, follow_redirects=True)
    assert risposta.status_code == 200

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT * FROM utenti WHERE username = 'nuovo_utente'")
        utente = cursore.fetchone()
        assert utente is not None
        assert utente["is_admin"] == False

        cursore.execute(
            "SELECT pagina FROM permessi_pagine WHERE utente_id = %s",
            (utente["id"],),
        )
        pagine = [p["pagina"] for p in cursore.fetchall()]
        assert "CASSA" in pagine
        assert "CUCINA" in pagine


def test_admin_attiva_e_disattiva_utente(cliente):
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("admin_toggle", "hash", True, True),
        )
        id_admin = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("utente_target", "hash", False, True),
        )
        id_target = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
            (id_admin, "ADMIN"),
        )
        connessione.commit()

    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_admin
        sessione["username"] = "admin_toggle"
        sessione["is_admin"] = True

    payload = {
        "id_utente": id_target,
        "username": "utente_target",
        "attivo": 0,
        "is_admin": 0,
        "permessi": [],
    }
    risposta = cliente.post("/api/modifica_utente", json=payload)
    assert risposta.status_code == 200

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "SELECT attivo FROM utenti WHERE id = %s", (id_target,)
        )
        assert cursore.fetchone()["attivo"] == False

    payload["attivo"] = 1
    cliente.post("/api/modifica_utente", json=payload)
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "SELECT attivo FROM utenti WHERE id = %s", (id_target,)
        )
        assert cursore.fetchone()["attivo"] == True


def test_admin_modifica_utente_rimuove_permessi_duplicati(cliente):
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("admin_permessi", "hash", True, True),
        )
        id_admin = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("target_permessi", "hash", False, True),
        )
        id_target = cursore.fetchone()["id"]
        connessione.commit()

    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_admin
        sessione["username"] = "admin_permessi"
        sessione["is_admin"] = True

    payload = {
        "id_utente": id_target,
        "username": "target_permessi",
        "attivo": 1,
        "is_admin": 0,
        "permessi": ["CASSA", "CASSA", "DASHBOARD", ""],
    }
    risposta = cliente.post("/api/modifica_utente", json=payload)
    assert risposta.status_code == 200

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "SELECT pagina FROM permessi_pagine WHERE utente_id = %s ORDER BY pagina",
            (id_target,),
        )
        pagine = [p["pagina"] for p in cursore.fetchall()]
        assert pagine == ["CASSA", "DASHBOARD"]


def test_admin_modifica_utente_aggiorna_password(cliente):
    import bcrypt

    password_vecchia = "vecchia123"
    hash_vecchio = bcrypt.hashpw(password_vecchia.encode(), bcrypt.gensalt()).decode()

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("admin_pwchange", "hash", True, True),
        )
        id_admin = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("utente_pwchange", hash_vecchio, False, True),
        )
        id_target = cursore.fetchone()["id"]
        connessione.commit()

    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_admin
        sessione["username"] = "admin_pwchange"

    password_nuova = "nuova_password_456"
    payload = {
        "id_utente": id_target,
        "username": "utente_pwchange",
        "password": password_nuova,
        "is_admin": False,
        "attivo": True,
        "permessi": [],
    }
    risposta = cliente.post("/api/modifica_utente", json=payload)
    assert risposta.status_code == 200

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT password_hash FROM utenti WHERE id = %s", (id_target,))
        hash_nuovo = cursore.fetchone()["password_hash"]

    assert bcrypt.checkpw(password_nuova.encode(), hash_nuovo.encode())
    assert not bcrypt.checkpw(password_vecchia.encode(), hash_nuovo.encode())


def test_admin_statistiche_restituisce_json(cliente):
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("admin_stats", "hash", True, True),
        )
        id_admin = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
            (id_admin, "ADMIN"),
        )
        connessione.commit()

    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_admin
        sessione["username"] = "admin_stats"
        sessione["is_admin"] = True

    risposta = cliente.get("/api/statistiche/")
    assert risposta.status_code == 200
    assert risposta.json is not None
