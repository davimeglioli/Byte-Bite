from app import (
    app,
    emissione_sicura,
    ottieni_db,
    ottieni_utente_loggato,
    ricalcola_statistiche,
    socketio,
)
from services import costruisci_dati_statistiche

# ==================== Copertura ====================


def test_ricalcola_statistiche_calcola_totale_carta(cliente):
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("DELETE FROM ordini_prodotti")
        cursore.execute("DELETE FROM ordini")
        cursore.execute(
            "INSERT INTO prodotti"
            " (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard)"
            " VALUES (700, 'Card Prod', 20, 100, 0, 'Test', 'Bar')"
        )
        cursore.execute(
            "INSERT INTO ordini"
            " (id, nome_cliente, numero_tavolo, data_ordine, completato, asporto, metodo_pagamento)"
            " VALUES (700, 'Card Client', 1, '2025-01-01 12:00:00', TRUE, FALSE, 'Carta')"
        )
        cursore.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)"
            " VALUES (700, 700, 1, 'Completato')"
        )
        connessione.commit()

    original_emit = socketio.emit
    socketio.emit = lambda *args, **kwargs: None
    try:
        ricalcola_statistiche()
    finally:
        socketio.emit = original_emit

    stats = costruisci_dati_statistiche()
    assert stats["totali"]["totale_carta"] == 20
    assert stats["totali"]["totale_contanti"] == 0


def test_ottieni_utente_loggato_senza_sessione(cliente):
    with app.test_request_context():
        assert ottieni_utente_loggato() is None


def test_emissione_sicura_gestisce_eccezioni(cliente):
    original_emit = socketio.emit

    def mock_emit(*args, **kwargs):
        raise Exception("Socket Error")

    socketio.emit = mock_emit
    try:
        emissione_sicura("test_event", {})
    finally:
        socketio.emit = original_emit
