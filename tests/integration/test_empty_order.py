import json
from app import ottieni_db

# ==================== Ordini (Validazione) ====================


def test_invio_ordine_senza_prodotti_reindirizza_con_errore(cliente, monkeypatch):
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
    assert (
        "error=Nessun+prodotto+selezionato" in risposta.location
        or "error=Nessun%20prodotto%20selezionato" in risposta.location
    )

    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("SELECT * FROM ordini WHERE nome_cliente = 'TestEmpty'")
        assert cursore.fetchone() is None
