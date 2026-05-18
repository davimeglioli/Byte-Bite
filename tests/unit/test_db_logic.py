from app.services import ottieni_ordini_per_categoria
from app.db import ottieni_db
from app.routes.utenti import _normalizza_permessi

# ==================== Database ====================


def test_ordini_per_categoria_raggruppa(cliente):
    with ottieni_db() as connessione:
        cursore = connessione.cursor()

        # Inserisce un prodotto e recupera l'id generato.
        cursore.execute(
            "INSERT INTO prodotti"
            " (nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti)"
            " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            ("Panino", 5.0, "Cibo", "Cucina", 100, 0),
        )
        id_prodotto = cursore.fetchone()["id"]

        # Inserisce un ordine (data_ordine usa il DEFAULT CURRENT_TIMESTAMP).
        cursore.execute(
            "INSERT INTO ordini"
            " (nome_cliente, numero_tavolo, numero_persone, metodo_pagamento, asporto)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id",
            ("Mario", 5, 2, "Contanti", False),
        )
        id_ordine = cursore.fetchone()["id"]

        cursore.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)"
            " VALUES (%s, %s, %s, %s)",
            (id_ordine, id_prodotto, 2, "In Attesa"),
        )
        connessione.commit()

    non_completati, completati = ottieni_ordini_per_categoria("Cucina")

    assert len(non_completati) == 1
    assert len(completati) == 0

    ordine = non_completati[0]
    assert ordine["nome_cliente"] == "Mario"
    assert ordine["numero_tavolo"] == 5
    assert len(ordine["prodotti"]) == 1
    assert ordine["prodotti"][0]["nome"] == "Panino"
    assert ordine["prodotti"][0]["quantita"] == 2


def test_ordini_per_categoria_separa_completati(cliente):
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(
            "INSERT INTO prodotti"
            " (nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti)"
            " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            ("Tagliatelle", 9.0, "Primi", "Cucina", 100, 0),
        )
        id_prodotto = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO ordini"
            " (nome_cliente, numero_tavolo, numero_persone, metodo_pagamento, asporto)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id",
            ("Alice", 3, 1, "Carta", False),
        )
        id_ordine = cursore.fetchone()["id"]
        cursore.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)"
            " VALUES (%s, %s, %s, %s)",
            (id_ordine, id_prodotto, 1, "Completato"),
        )
        connessione.commit()

    non_completati, completati = ottieni_ordini_per_categoria("Cucina")
    assert len(completati) == 1
    assert len(non_completati) == 0
    assert completati[0]["nome_cliente"] == "Alice"


def test_normalizza_permessi_deduplica():
    risultato = _normalizza_permessi(["CASSA", "CASSA", "DASHBOARD"])
    assert risultato == ["CASSA", "DASHBOARD"]


def test_normalizza_permessi_input_non_lista_restituisce_vuoto():
    assert _normalizza_permessi("CASSA") == []
    assert _normalizza_permessi(None) == []
    assert _normalizza_permessi(42) == []


def test_normalizza_permessi_rimuove_vuoti_e_spazi():
    risultato = _normalizza_permessi(["  CASSA  ", "", "DASHBOARD"])
    assert "CASSA" in risultato
    assert "DASHBOARD" in risultato
    assert "" not in risultato
    assert len(risultato) == 2
