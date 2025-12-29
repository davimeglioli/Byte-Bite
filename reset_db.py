import sqlite3 as sq
import os

def reset_db():
    print("Inizio reset del database...")
    
    db_path = 'db.sqlite3'
    if not os.path.exists(db_path):
        print(f"Errore: Il file {db_path} non esiste.")
        return

    try:
        conn = sq.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Elimina tutti i dati esistenti
        print("Eliminazione dati ordini e statistiche...")
        tables_to_clear = [
            'ordini', 
            'ordini_prodotti', 
            'statistiche_totali', 
            'statistiche_categorie', 
            'statistiche_ore',
            'prodotti'
        ]
        
        for table in tables_to_clear:
            cursor.execute(f"DELETE FROM {table}")
            
        # Reset delle sequenze di autoincrement
        print("Reset sequenze autoincrement...")
        cursor.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name IN ('ordini', 'prodotti')")
        
        # 2. Inserimento prodotti di default
        print("Inserimento prodotti di default...")
        
        products_sql = """
        -- APERITIVI 
        INSERT INTO prodotti (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti) 
        VALUES 
        ('Spritz Aperol', 4, 'Aperitivi', 'Bar', 1, 100, 0), 
        ('Spritz Campari', 4, 'Aperitivi', 'Bar', 1, 100, 0), 
        ('Spritz Hugo', 4, 'Aperitivi', 'Bar', 1, 100, 0), 
        ('Analcolico', 4, 'Aperitivi', 'Bar', 1, 100, 0); 
        
        -- PAELLA 
        INSERT INTO prodotti (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti) 
        VALUES 
        ('Menu Completo: Antipasto - Paella - Dolce', 25, 'Paella', 'Cucina', 1, 100, 0); 
        
        -- PRIMI 
        INSERT INTO prodotti (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti) 
        VALUES 
        ('Tortelli Verdi Vecchia Modena', 9.5, 'Primi', 'Cucina', 1, 100, 0), 
        ('Tortelli Verdi Burro e Salvia', 9, 'Primi', 'Cucina', 1, 100, 0), 
        ("Riso Venere dell'Orto", 8, 'Primi', 'Cucina', 1, 100, 0), 
        ('Garganelli al Ragù di Carne', 8, 'Primi', 'Cucina', 1, 100, 0); 
        
        -- SECONDI 
        INSERT INTO prodotti (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti) 
        VALUES 
        ('Picanha ai Ferri', 16.5, 'Secondi', 'Griglia', 1, 100, 0), 
        ('Grigliata Mista di Carne', 12, 'Secondi', 'Griglia', 1, 100, 0), 
        ('Salsiccia, Wurstel e Patatine', 8.5, 'Secondi', 'Griglia', 1, 100, 0), 
        ('Caprese', 8, 'Secondi', 'Griglia', 1, 100, 0), 
        ('Fritto Misto di Pesce', 12.5, 'Secondi', 'Griglia', 1, 100, 0), 
        ('Patatine Fritte', 3, 'Secondi', 'Gnoccheria', 1, 100, 0), 
        ('Misticanza', 3, 'Secondi', 'Gnoccheria', 1, 100, 0); 
        
        -- GNOCCO E TIGELLE 
        INSERT INTO prodotti (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti) 
        VALUES 
        ('Gnocco Fritto Vuoto', 0.6, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Gnocco Fritto con Prosciutto Cotto', 3.5, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Gnocco Fritto con Prosciutto Crudo', 3.5, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Gnocco Fritto con Salame', 3.5, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Gnocco Fritto con Coppa', 3.5, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Tigella Semplice', 0.6, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Tigella con Prosciutto Cotto', 2.5, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Tigella con Prosciutto Crudo', 2.5, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Tigella con Salame', 2.5, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Tigella con Coppa', 2.5, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Piatto Affettato Misto', 7, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Piatto Prosciutto Crudo', 8, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Stracchino e Rucola', 2.5, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Nutella', 1, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Lardo', 1.5, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Parmigiano', 1.5, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Lardo e Parmigiano', 2.5, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0), 
        ('Maionese/ Ketchup', 0.5, 'Gnocco e Tigelle', 'Gnoccheria', 1, 100, 0); 
        
        -- DA BERE 
        INSERT INTO prodotti (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti) 
        VALUES 
        ('Acqua Naturale 0,5L', 1.0, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Acqua Naturale 1,5L', 2.0, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Acqua Frizzante 0,5L', 1.0, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Acqua Frizzante 1,5L', 1.0, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Birra Spina Piccola', 2, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Birra Spina Media', 3.5, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Birra Spina Weiss Piccola', 3, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Birra Spina Weiss Media', 4.5, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Coca Cola Spina Piccola', 2, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Coca Cola Spina Media', 3.5, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Coca Cola in lattina', 2.5, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Fanta in lattina', 2.5, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Lambrusco Bottiglia 0,75L', 6, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Vino Bianco Bicchiere', 1.5, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Vino Bianco Caraffa 0,50L', 4, 'Da Bere', 'Bar', 1, 100, 0), 
        ('Vino Bianco Caraffa 1L', 6.5, 'Da Bere', 'Bar', 1, 100, 0); 
        
        -- DOLCI 
        INSERT INTO prodotti (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti) 
        VALUES 
        ('Tiramisù', 4, 'Dolci', 'Bar', 1, 100, 0), 
        ('Zuppa Inglese', 4, 'Dolci', 'Bar', 1, 100, 0), 
        ('Cheescake ai Frutti di Bosco', 4, 'Dolci', 'Bar', 1, 100, 0), 
        ('Sorbetto al Limone', 3, 'Dolci', 'Bar', 1, 100, 0), 
        ('Caffè', 1, 'Dolci', 'Bar', 1, 100, 0), 
        ('Caffè Corretto', 2, 'Dolci', 'Bar', 1, 100, 0), 
        ('Limoncino', 3, 'Dolci', 'Bar', 1, 100, 0), 
        ('Nocino', 3, 'Dolci', 'Bar', 1, 100, 0), 
        ('Amaro del Capo', 3, 'Dolci', 'Bar', 1, 100, 0), 
        ('Montenegro', 3, 'Dolci', 'Bar', 1, 100, 0), 
        ('Grappa', 3, 'Dolci', 'Bar', 1, 100, 0); 
        
        -- LONG DRINK 
        INSERT INTO prodotti (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti) 
        VALUES 
        ('Gin Tonic', 5, 'Long Drink', 'Bar', 1, 100, 0), 
        ('Gin Tonic Premium', 8, 'Long Drink', 'Bar', 1, 100, 0), 
        ('Gin Lemon', 5, 'Long Drink', 'Bar', 1, 100, 0), 
        ('Vodka Tonic', 5, 'Long Drink', 'Bar', 1, 100, 0), 
        ('Vodka Lemon', 5, 'Long Drink', 'Bar', 1, 100, 0), 
        ('Vodka & Fruit', 5, 'Long Drink', 'Bar', 1, 100, 0), 
        ('Rum e Cola', 5, 'Long Drink', 'Bar', 1, 100, 0), 
        ('Malibu e Cola', 5, 'Long Drink', 'Bar', 1, 100, 0), 
        ('Mojito', 6, 'Long Drink', 'Bar', 1, 100, 0), 
        ('Barbie Mojito', 6, 'Long Drink', 'Bar', 1, 100, 0), 
        ('Cuba Libre', 6, 'Long Drink', 'Bar', 1, 100, 0), 
        ('Caipiroska Fragola', 6, 'Long Drink', 'Bar', 1, 100, 0); 
        
        -- SHORT DRINK 
        INSERT INTO prodotti (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti) 
        VALUES 
        ('Negroni', 4, 'Short Drink', 'Bar', 1, 100, 0), 
        ('Americano', 4, 'Short Drink', 'Bar', 1, 100, 0);
        """
        
        cursor.executescript(products_sql)
        
        conn.commit()
        print("Reset completato con successo.")
        
    except sq.Error as e:
        print(f"Errore SQLite: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    reset_db()