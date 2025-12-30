from app import ottieni_db

# ==================== Gestione Errori ====================


def test_creazione_ordine_con_prodotto_inesistente_reindirizza_con_errore(cliente):
    # Crea un utente cassa e assegna permesso per creare ordini.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("cassiere_err", "hash", 0, 1),
        )
        # Recupera id utente.
        id_utente = connessione.execute(
            "SELECT id FROM utenti WHERE username = 'cassiere_err'"
        ).fetchone()["id"]
        # Assegna permesso CASSA.
        connessione.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)",
            (id_utente, "CASSA"),
        )
        # Commit delle modifiche.
        connessione.commit()

    # Simula sessione autenticata come cassiere.
    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_utente
        sessione["username"] = "cassiere_err"

    # Invia un ordine con prodotto inesistente.
    dati = {
        "prodotti": '[{"id": 99999, "quantita": 1}]',
        "nome_cliente": "Test Error",
        "numero_tavolo": "5",
        "metodo_pagamento": "Contanti",
    }

    # La rotta deve reindirizzare con parametro error.
    risposta = cliente.post("/aggiungi_ordine/", data=dati, follow_redirects=False)
    assert risposta.status_code == 303
    assert "error=" in risposta.location

def test_secondo_ordine_fallisce_se_prodotto_esaurito(cliente):
    # Inserisce un prodotto con quantità 1 e un utente con permesso CASSA.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO prodotti (id, nome, prezzo, quantita, venduti, categoria_menu, categoria_dashboard) VALUES (99, 'Ultimo', 10, 1, 0, 'Test', 'Cucina')"
        )
        connessione.commit()

        # Inserisce utente cassa.
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("user_conc", "hash", 0, 1),
        )
        # Recupera id utente.
        id_utente = connessione.execute(
            "SELECT id FROM utenti WHERE username = 'user_conc'"
        ).fetchone()["id"]
        # Assegna permesso CASSA.
        connessione.execute(
            "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)",
            (id_utente, "CASSA"),
        )
        connessione.commit()

    # Simula sessione autenticata.
    with cliente.session_transaction() as sessione:
        sessione["id_utente"] = id_utente

    # Primo ordine: consuma l'ultimo pezzo.
    dati = {
        "prodotti": '[{"id": 99, "quantita": 1}]',
        "nome_cliente": "Cliente 1",
        "numero_tavolo": "1",
        "metodo_pagamento": "Contanti",
    }

    risposta_1 = cliente.post("/aggiungi_ordine/", data=dati)
    assert risposta_1.status_code == 303
    assert "error" not in risposta_1.location

    # Secondo ordine: deve fallire perché il prodotto è esaurito.
    dati["nome_cliente"] = "Cliente 2"
    risposta_2 = cliente.post("/aggiungi_ordine/", data=dati)
    assert risposta_2.status_code == 303
    assert "error" in risposta_2.location
