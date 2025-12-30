import json
from app import ottieni_db

# ==================== Ordini (Validazione) ====================


def test_invio_ordine_senza_prodotti_reindirizza_con_errore(cliente, monkeypatch):
    # Disabilita emissioni SocketIO per isolare il test.
    monkeypatch.setattr("app.emissione_sicura", lambda *args, **kwargs: None)
    # Disabilita background task che potrebbero partire durante la request.
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    # Costruisce payload con lista prodotti vuota.
    dati_ordine = {
        "nome_cliente": "TestEmpty",
        "numero_tavolo": "1",
        "numero_persone": "2",
        "metodo_pagamento": "Contanti",
        "prodotti": json.dumps([]),
    }

    # Invia richiesta e verifica redirect con errore.
    risposta = cliente.post("/aggiungi_ordine/", data=dati_ordine, follow_redirects=False)
    assert risposta.status_code == 303
    assert "error=Nessun+prodotto+selezionato" in risposta.location or "error=Nessun%20prodotto%20selezionato" in risposta.location

    # Verifica che l'ordine non sia stato creato.
    with ottieni_db() as connessione:
        ordine = connessione.execute(
            "SELECT * FROM ordini WHERE nome_cliente = 'TestEmpty'"
        ).fetchone()
        assert ordine is None
