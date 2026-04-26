from app import ottieni_ordini_per_categoria, ottieni_db

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
