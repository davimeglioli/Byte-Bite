import json
from app import ottieni_db

# ==================== Ordini (Cassa) ====================


def _imposta_cassa(cliente):
    """Crea un utente con permesso CASSA e imposta la sessione."""
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("cassa_test", "hash", False, True),
        )
        id_utente = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
            (id_utente, "CASSA"),
        )
        connessione.commit()
    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_utente
        sessione["username"] = "cassa_test"
    return id_utente


def test_aggiungi_ordine_con_prodotti_aggiorna_magazzino(cliente, monkeypatch):
    _imposta_cassa(cliente)
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO prodotti"
            " (id, nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (1, "Pizza Margherita", 8.0, "Pizze", "Cucina", 10, 0),
        )
        connessione.commit()

    monkeypatch.setattr("app.emissione_sicura", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    dati_ordine = {
        "nome_cliente": "Luigi",
        "numero_tavolo": "10",
        "numero_persone": "4",
        "metodo_pagamento": "Contanti",
        "isTakeaway": "",
        "prodotti": json.dumps([{"id": 1, "quantita": 2, "nome": "Pizza Margherita"}]),
    }

    risposta = cliente.post("/aggiungi_ordine/", data=dati_ordine)
    assert risposta.status_code == 303

    with ottieni_db() as connessione:
        cursore = connessione.cursor()

        cursore.execute("SELECT * FROM ordini WHERE nome_cliente = 'Luigi'")
        ordine = cursore.fetchone()
        assert ordine is not None
        assert ordine["numero_tavolo"] == 10

        cursore.execute("SELECT quantita, venduti FROM prodotti WHERE id = 1")
        prodotto = cursore.fetchone()
        assert prodotto["quantita"] == 8
        assert prodotto["venduti"] == 2

        cursore.execute(
            "SELECT * FROM ordini_prodotti WHERE ordine_id = %s",
            (ordine["id"],),
        )
        riga = cursore.fetchone()
        assert riga["prodotto_id"] == 1
        assert riga["quantita"] == 2
        assert riga["stato"] == "In Attesa"


def test_aggiungi_ordine_fallisce_se_prodotto_esaurito(cliente):
    _imposta_cassa(cliente)
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO prodotti"
            " (id, nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (2, "Pizza Speciale", 10.0, "Pizze", "Cucina", 1, 0),
        )
        connessione.commit()

    dati_ordine = {
        "nome_cliente": "Mario",
        "metodo_pagamento": "Carta",
        "prodotti": json.dumps([{"id": 2, "quantita": 2, "nome": "Pizza Speciale"}]),
    }

    risposta = cliente.post("/aggiungi_ordine/", data=dati_ordine)
    assert risposta.status_code == 303
    assert "/cassa/" in risposta.location

    with ottieni_db() as connessione:
        cursore = connessione.cursor()

        cursore.execute("SELECT quantita FROM prodotti WHERE id = 2")
        prodotto = cursore.fetchone()
        assert prodotto["quantita"] == 1

        cursore.execute("SELECT * FROM ordini WHERE nome_cliente = 'Mario'")
        ordine = cursore.fetchone()
        if ordine:
            cursore.execute(
                "SELECT * FROM ordini_prodotti WHERE ordine_id = %s",
                (ordine["id"],),
            )
            assert len(cursore.fetchall()) == 0


def test_ordine_asporto_ignora_tavolo(cliente, monkeypatch):
    _imposta_cassa(cliente)
    monkeypatch.setattr("app.emissione_sicura", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO prodotti"
            " (id, nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (99, "Acqua", 1.0, "Bar", "Bar", 100, 0),
        )
        connessione.commit()

    dati_ordine = {
        "nome_cliente": "Giulia",
        "isTakeaway": "on",
        "numero_tavolo": "99",
        "metodo_pagamento": "Contanti",
        "prodotti": json.dumps([{"id": 99, "quantita": 1, "nome": "Acqua"}]),
    }

    cliente.post("/aggiungi_ordine/", data=dati_ordine)

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "SELECT asporto, numero_tavolo FROM ordini WHERE nome_cliente = 'Giulia'"
        )
        ordine = cursore.fetchone()
        assert ordine["asporto"] == True
        assert ordine["numero_tavolo"] is None
