from app import esegui_query, ottieni_ordini_per_categoria, ottieni_db

# ==================== Database ====================


def test_esegui_query_salva_e_legge(cliente):
    # Crea una tabella di prova.
    esegui_query("CREATE TABLE IF NOT EXISTS tabella_test (id INTEGER PRIMARY KEY, nome TEXT)")
    # Inserisce un record.
    esegui_query("INSERT INTO tabella_test (nome) VALUES (?)", ("Test",), commit=True)

    # Legge il record appena inserito.
    risultato = esegui_query("SELECT nome FROM tabella_test WHERE id = 1", uno=True)
    # Verifica il valore letto.
    assert risultato["nome"] == "Test"


def test_ordini_per_categoria_raggruppa(cliente):
    # Popola il DB temporaneo con un prodotto e un ordine.
    with ottieni_db() as connessione:
        # Ottiene cursore per sequenze di operazioni.
        cursore = connessione.cursor()
        # Inserisce un prodotto associato alla dashboard Cucina.
        cursore.execute(
            "INSERT INTO prodotti (nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti) VALUES (?, ?, ?, ?, ?, ?)",
            ("Panino", 5.0, "Cibo", "Cucina", 100, 0),
        )
        # Recupera l'id auto-generato del prodotto.
        id_prodotto = cursore.lastrowid

        # Inserisce un ordine.
        cursore.execute(
            """
            INSERT INTO ordini (nome_cliente, numero_tavolo, numero_persone, data_ordine, metodo_pagamento, asporto)
            VALUES (?, ?, ?, datetime('now'), ?, ?)
            """,
            ("Mario", 5, 2, "Contanti", 0),
        )
        # Recupera l'id auto-generato dell'ordine.
        id_ordine = cursore.lastrowid

        # Collega il prodotto all'ordine.
        cursore.execute(
            """
            INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)
            VALUES (?, ?, ?, ?)
            """,
            (id_ordine, id_prodotto, 2, "In Attesa"),
        )
        # Applica le modifiche.
        connessione.commit()

    # Esegue la funzione di business e recupera i due gruppi.
    non_completati, completati = ottieni_ordini_per_categoria("Cucina")

    # Verifica che ci sia un ordine non completato.
    assert len(non_completati) == 1
    # Verifica che non ci siano completati.
    assert len(completati) == 0

    # Verifica struttura e contenuti dell'ordine.
    ordine = non_completati[0]
    assert ordine["nome_cliente"] == "Mario"
    assert ordine["numero_tavolo"] == 5
    assert len(ordine["prodotti"]) == 1
    assert ordine["prodotti"][0]["nome"] == "Panino"
    assert ordine["prodotti"][0]["quantita"] == 2
