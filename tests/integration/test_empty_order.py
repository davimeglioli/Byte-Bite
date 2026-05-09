import json
from app import ottieni_db

# ==================== Ordini (Validazione) ====================


def _imposta_cassa(cliente):
    """Crea un utente con permesso CASSA e imposta la sessione."""
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            ("cassa_empty", "hash", False, True),
        )
        id_utente = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
            (id_utente, "CASSA"),
        )
        connessione.commit()
    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_utente
        sessione["username"] = "cassa_empty"
    return id_utente


def test_invio_ordine_senza_prodotti_reindirizza_con_errore(cliente, monkeypatch):
    _imposta_cassa(cliente)
    monkeypatch.setattr("app.emissione_sicura", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    dati_ordine = {
        "nome_cliente": "TestEmpty",
        "numero_tavolo": "1",
        "numero_persone": "2",
        "metodo_pagamento": "Contanti",
        "prodotti": json.dumps([]),
    }

    risposta = cliente.post("/aggiungi_ordine/", data=dati_ordine, follow_redirects=False)
    assert risposta.status_code == 303
    assert "/cassa/" in risposta.location

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT * FROM ordini WHERE nome_cliente = 'TestEmpty'")
        assert cursore.fetchone() is None
