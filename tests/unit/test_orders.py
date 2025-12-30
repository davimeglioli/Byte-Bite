import json
from app import ottieni_db

# ==================== Ordini (Cassa) ====================


def test_aggiungi_ordine_con_prodotti_aggiorna_magazzino(cliente, monkeypatch):
    # Inserisce un prodotto con quantità iniziale nota.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO prodotti (id, nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "Pizza Margherita", 8.0, "Pizze", "Cucina", 10, 0),
        )
        connessione.commit()

    # Disabilita emissioni SocketIO per evitare effetti collaterali.
    monkeypatch.setattr("app.emissione_sicura", lambda *args, **kwargs: None)
    # Disabilita background task nel contesto test.
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    # Compone payload dell'ordine (2 pizze).
    dati_ordine = {
        "nome_cliente": "Luigi",
        "numero_tavolo": "10",
        "numero_persone": "4",
        "metodo_pagamento": "Contanti",
        "isTakeaway": "",
        "prodotti": json.dumps([{"id": 1, "quantita": 2, "nome": "Pizza Margherita"}]),
    }

    # Invoca la rotta di creazione ordine.
    risposta = cliente.post("/aggiungi_ordine/", data=dati_ordine)

    # Verifica redirect di successo.
    assert risposta.status_code == 303

    # Rilegge dal DB per verificare persistenza e aggiornamenti.
    with ottieni_db() as connessione:
        # Verifica creazione ordine.
        ordine = connessione.execute(
            "SELECT * FROM ordini WHERE nome_cliente = 'Luigi'"
        ).fetchone()
        assert ordine is not None
        assert ordine["numero_tavolo"] == 10

        # Verifica decremento magazzino e incremento venduti.
        prodotto = connessione.execute(
            "SELECT quantita, venduti FROM prodotti WHERE id = 1"
        ).fetchone()
        assert prodotto["quantita"] == 8
        assert prodotto["venduti"] == 2

        # Verifica riga di collegamento ordine/prodotto.
        riga = connessione.execute(
            "SELECT * FROM ordini_prodotti WHERE ordine_id = ?",
            (ordine["id"],),
        ).fetchone()
        assert riga["prodotto_id"] == 1
        assert riga["quantita"] == 2
        assert riga["stato"] == "In Attesa"


def test_aggiungi_ordine_fallisce_se_prodotto_esaurito(cliente):
    # Inserisce un prodotto con quantità insufficiente (1).
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO prodotti (id, nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (2, "Pizza Speciale", 10.0, "Pizze", "Cucina", 1, 0),
        )
        connessione.commit()

    # Richiede quantità 2 per forzare errore.
    dati_ordine = {
        "nome_cliente": "Mario",
        "metodo_pagamento": "Carta",
        "prodotti": json.dumps([{"id": 2, "quantita": 2, "nome": "Pizza Speciale"}]),
    }

    # Invoca la creazione ordine.
    risposta = cliente.post("/aggiungi_ordine/", data=dati_ordine)

    # Verifica redirect con querystring error.
    assert risposta.status_code == 303
    assert "error" in risposta.location

    # Verifica che la quantità in magazzino sia rimasta invariata.
    with ottieni_db() as connessione:
        prodotto = connessione.execute(
            "SELECT quantita FROM prodotti WHERE id = 2"
        ).fetchone()
        assert prodotto["quantita"] == 1

        # Se l'ordine è stato creato, non deve avere righe prodotto associate.
        ordine = connessione.execute(
            "SELECT * FROM ordini WHERE nome_cliente = 'Mario'"
        ).fetchone()
        if ordine:
            prodotti_ordine = connessione.execute(
                "SELECT * FROM ordini_prodotti WHERE ordine_id = ?",
                (ordine["id"],),
            ).fetchall()
            assert len(prodotti_ordine) == 0


def test_ordine_asporto_ignora_tavolo(cliente, monkeypatch):
    # Disabilita emissioni SocketIO per isolare il test.
    monkeypatch.setattr("app.emissione_sicura", lambda *args, **kwargs: None)
    # Disabilita background task nel contesto test.
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    # Inserisce un prodotto di test.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO prodotti (id, nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (99, "Acqua", 1.0, "Bar", "Bar", 100, 0),
        )
        connessione.commit()

    # Invia ordine come asporto con tavolo presente (da ignorare).
    dati_ordine = {
        "nome_cliente": "Giulia",
        "isTakeaway": "on",
        "numero_tavolo": "99",
        "metodo_pagamento": "Contanti",
        "prodotti": json.dumps([{"id": 99, "quantita": 1, "nome": "Acqua"}]),
    }

    # Esegue la richiesta.
    cliente.post("/aggiungi_ordine/", data=dati_ordine)

    # Verifica che asporto sia impostato e tavolo nullo.
    with ottieni_db() as connessione:
        ordine = connessione.execute(
            "SELECT asporto, numero_tavolo FROM ordini WHERE nome_cliente = 'Giulia'"
        ).fetchone()
        assert ordine["asporto"] == 1
        assert ordine["numero_tavolo"] is None
