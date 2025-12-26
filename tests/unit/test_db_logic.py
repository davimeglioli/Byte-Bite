import sqlite3
from app import esegui_query, ottieni_ordini_per_categoria, ottieni_db

def test_esegui_query(client):
    """Testa che esegui_query funzioni con il DB temporaneo."""
    # Inserisci un dato di prova
    esegui_query("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, nome TEXT)")
    esegui_query("INSERT INTO test_table (nome) VALUES (?)", ("Test",), commit=True)
    
    # Leggi il dato
    risultato = esegui_query("SELECT nome FROM test_table WHERE id=1", uno=True)
    assert risultato["nome"] == "Test"

def test_ottieni_ordini_per_categoria(client):
    """Testa la logica di raggruppamento degli ordini."""
    # Setup dati nel DB temporaneo
    with ottieni_db() as conn:
        cursor = conn.cursor()
        
        # 1. Crea prodotti
        cursor.execute("INSERT INTO prodotti (nome, prezzo, categoria_menu, categoria_dashboard, quantita, venduti) VALUES (?, ?, ?, ?, ?, ?)", 
                       ("Panino", 5.0, "Cibo", "Cucina", 100, 0))
        id_prodotto = cursor.lastrowid
        
        # 2. Crea un ordine
        cursor.execute("""
            INSERT INTO ordini (nome_cliente, numero_tavolo, numero_persone, data_ordine, metodo_pagamento, asporto) 
            VALUES (?, ?, ?, datetime('now'), ?, ?)
        """, ("Mario", 5, 2, "Contanti", 0))
        id_ordine = cursor.lastrowid
        
        # 3. Collega prodotto all'ordine
        cursor.execute("""
            INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)
            VALUES (?, ?, ?, ?)
        """, (id_ordine, id_prodotto, 2, "In Attesa"))
        
        conn.commit()
        
    # Esegui la funzione da testare
    non_completati, completati = ottieni_ordini_per_categoria("Cucina")
    
    # Asserzioni
    assert len(non_completati) == 1
    assert len(completati) == 0
    
    ordine = non_completati[0]
    assert ordine["nome_cliente"] == "Mario"
    assert ordine["numero_tavolo"] == 5
    assert len(ordine["prodotti"]) == 1
    assert ordine["prodotti"][0]["nome"] == "Panino"
    assert ordine["prodotti"][0]["quantita"] == 2
