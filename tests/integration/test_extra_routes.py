import bcrypt
from app import ottieni_db

# ==================== Rotte Extra ====================


def test_pagina_amministrazione_risponde(cliente, autenticazione):
    # Esegue login come admin.
    autenticazione.accedi()
    # Richiede pagina amministrazione.
    risposta = cliente.get("/amministrazione/")
    # Verifica status e contenuto.
    assert risposta.status_code == 200
    assert b"Amministrazione" in risposta.data
    

def test_errore_403_senza_permessi_amministrazione(cliente, autenticazione):
    # Crea un utente non admin con password nota.
    password = "pass"
    hash_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # Inserisce utente senza permessi amministrazione.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES ('utente', ?, 0, 1)",
            (hash_password,),
        )
        connessione.commit()

    # Esegue login come utente base.
    autenticazione.accedi(username="utente", password="pass")
    # Prova ad accedere ad amministrazione.
    risposta = cliente.get("/amministrazione/")
    # Verifica accesso negato.
    assert risposta.status_code == 403
    assert b"Accesso Negato" in risposta.data or b"403" in risposta.data

def test_utente_disattivo_viene_reindirizzato_al_login(cliente, autenticazione):
    # Crea un utente disattivo con password nota.
    password = "pass"
    hash_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # Inserisce utente disattivo nel DB.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES ('disattivo', ?, 0, 0)",
            (hash_password,),
        )
        connessione.commit()

    # Esegue login (l'app dovrebbe poi negare l'accesso).
    autenticazione.accedi(username="disattivo", password="pass")
    # Prova ad accedere ad amministrazione.
    risposta = cliente.get("/amministrazione/")
    # Verifica redirect a login.
    assert risposta.status_code == 302
    assert "/login/" in risposta.location

def test_esporta_statistiche_scarica_pdf(cliente, autenticazione):
    # Esegue login come admin.
    autenticazione.accedi()

    # Inserisce dati minimi per esportazione PDF.
    with ottieni_db() as connessione:
        connessione.execute(
            "INSERT INTO prodotti (id, nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1000, "ProdTest", 3.5, "TestCat", "Bar", 1, 10, 0),
        )
        connessione.execute(
            "INSERT INTO ordini (id, asporto, data_ordine, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento, completato) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1000, 0, "2025-01-01 12:34:56", "Mario", 5, 2, "Contanti", 1),
        )
        connessione.execute(
            "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (?, ?, ?, ?)",
            (1000, 1000, 2, "Completato"),
        )
        connessione.commit()

    # Richiede endpoint di esportazione.
    risposta = cliente.get("/amministrazione/esporta_statistiche")
    # Verifica headers e magic bytes PDF.
    assert risposta.status_code == 200
    assert risposta.mimetype == "application/pdf"
    assert "attachment;" in risposta.headers.get("Content-Disposition", "")
    assert risposta.data[:4] == b"%PDF"
    # Verifica che nel PDF siano presenti dati attesi.
    assert b"Ordine #1000" in risposta.data
    assert b"Mario" in risposta.data
    assert b"ProdTest" in risposta.data
