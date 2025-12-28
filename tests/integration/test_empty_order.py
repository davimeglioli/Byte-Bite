import pytest
import json
from app import ottieni_db

def test_invio_ordine_senza_prodotti(client, monkeypatch):
    """Testa che l'invio di un ordine senza prodotti venga rifiutato."""
    
    # Mock emissione_sicura per evitare errori di socket
    monkeypatch.setattr("app.emissione_sicura", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)

    # Dati ordine senza prodotti
    dati_ordine = {
        "nome_cliente": "TestEmpty",
        "numero_tavolo": "1",
        "numero_persone": "2",
        "metodo_pagamento": "Contanti",
        "prodotti": json.dumps([]) # Lista vuota
    }
    
    # Invio POST
    resp = client.post('/aggiungi_ordine/', data=dati_ordine, follow_redirects=False)
    
    # Dovrebbe fare redirect con errore
    assert resp.status_code == 303
    assert "error=Nessun+prodotto+selezionato" in resp.location or "error=Nessun%20prodotto%20selezionato" in resp.location

    # Verifica che l'ordine non sia stato creato nel DB
    with ottieni_db() as conn:
        ordine = conn.execute("SELECT * FROM ordini WHERE nome_cliente = 'TestEmpty'").fetchone()
        assert ordine is None
