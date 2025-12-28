import pytest
import time
from playwright.sync_api import Page, expect

def test_routing_ordini_e_statistiche(page: Page, base_url):
    """
    Test 3 & 5:
    3. Routing Categorie: Verifica che ogni prodotto finisca nella dashboard corretta.
    5. Accuratezza Statistiche: Verifica che l'incasso totale aumenti correttamente.
    """
    
    # --- 0. PREPARAZIONE DATI (Admin) ---
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.click('button[type="submit"]')
    page.click('text=Amministrazione')
    
    # Recupera statistiche iniziali (Totale Incasso)
    # La card dell'incasso è la 3^ (indice 2) -> "Totale Incasso"
    # Struttura: .scheda-statistica .valore-statistica
    # Attesa che i dati siano caricati
    page.wait_for_selector('.scheda-statistica .valore-statistica')
    
    # Helper per pulire la stringa valuta (es. "120.50 €" -> 120.50)
    def parse_currency(text):
        clean = text.replace('€', '').replace(',', '.').strip()
        return float(clean) if clean else 0.0

    stats_cards = page.locator('.scheda-statistica .valore-statistica')
    # Assicuriamoci che ci siano le card (Totale Ordini, Completati, Incasso, Carta, Contanti)
    expect(stats_cards.first).to_be_visible()
    
    # L'incasso è solitamente la terza card (index 2)
    initial_revenue_text = stats_cards.nth(2).inner_text()
    initial_revenue = parse_currency(initial_revenue_text)

    # Creazione prodotti per ogni categoria
    categories = ["Bar", "Cucina", "Griglia", "Gnoccheria"]
    product_map = {} # nome -> categoria
    
    for cat in categories:
        prod_name = f"Test {cat} {int(time.time())}" # Timestamp per unicità
        product_map[cat] = prod_name
        
        # Apri modale
        page.locator('.sezione-tabella', has_text="Dettaglio prodotti").locator('.tasto-aggiungi-header').click()
        expect(page.locator('#modaleAggiunta')).to_be_visible()
        
        page.fill('#nomeProdottoAggiunta', prod_name)
        page.fill('#prezzoProdottoAggiunta', '10.00') # Prezzo fisso per calcoli facili
        page.fill('#quantitaProdottoAggiunta', '100')
        page.select_option('#categoriaMenuAggiunta', 'Da Bere' if cat == 'Bar' else 'Primi')
        page.select_option('#categoriaDashboardAggiunta', cat)
        
        page.click('#formAggiunta .btn-conferma')
        
        # Attendi chiusura modale e refresh
        expect(page.locator('#modaleAggiunta')).not_to_be_visible()
        page.wait_for_timeout(200) # Piccolo wait per sicurezza socket
        
    # --- 1. ORDINAZIONE (Cliente) ---
    page.goto(f"{base_url}/cassa/")
    
    # Aggiungi 1 di ogni prodotto al carrello
    for cat, prod_name in product_map.items():
        target_tab = 'Da Bere' if cat == 'Bar' else 'Primi'
        page.locator(f'.linguetta[data-categoria="{target_tab}"]').click()
        
        prod_card = page.locator('.prodotto', has_text=prod_name)
        expect(prod_card).to_be_visible()
        prod_card.locator('.tasto-piu').click()

    page.fill('input[name="nome_cliente"]', "Cliente Test")
    page.fill('input[name="numero_tavolo"]', "1")
    page.fill('input[name="numero_persone"]', "4")
    page.select_option('select[name="metodo_pagamento"]', "Contanti")
    
    # --- VERIFICA TOTALE CARRELLO (Completamento Test 1) ---
    # Verifica che il totale visualizzato sia corretto (4 prodotti * 10.00€ = 40.00€)
    totale_visibile = page.locator('.totale-carrello h2').nth(1).inner_text()
    assert "40.00" in totale_visibile, f"Errore Totale Carrello: Atteso 40.00, Trovato {totale_visibile}"
    print(f"DEBUG: Totale carrello verificato: {totale_visibile}")

    # Invia Ordine
    page.click('.tasto-conferma-ordine')
    
    # Aspettiamo un attimo per il redirect/conferma
    page.wait_for_timeout(1000)
    
    # --- 2. VERIFICA DASHBOARD (Test 3) ---
    
    # Dashboard BAR
    page.goto(f"{base_url}/dashboard/Bar")
    expect(page.locator('.scheda-ordine', has_text=product_map['Bar'])).to_be_visible()
    expect(page.locator('.scheda-ordine', has_text=product_map['Cucina'])).not_to_be_visible()
    
    # Dashboard CUCINA
    page.goto(f"{base_url}/dashboard/Cucina")
    expect(page.locator('.scheda-ordine', has_text=product_map['Cucina'])).to_be_visible()
    expect(page.locator('.scheda-ordine', has_text=product_map['Bar'])).not_to_be_visible()
    
    # Dashboard GRIGLIA
    page.goto(f"{base_url}/dashboard/Griglia")
    expect(page.locator('.scheda-ordine', has_text=product_map['Griglia'])).to_be_visible()
    
    # Dashboard GNOCCHERIA
    page.goto(f"{base_url}/dashboard/Gnoccheria")
    expect(page.locator('.scheda-ordine', has_text=product_map['Gnoccheria'])).to_be_visible()
    
    # --- 3. VERIFICA STATISTICHE (Test 5) ---
    page.goto(f"{base_url}/amministrazione")
    page.wait_for_selector('.scheda-statistica .valore-statistica')
    
    final_revenue_text = page.locator('.scheda-statistica .valore-statistica').nth(2).inner_text()
    final_revenue = parse_currency(final_revenue_text)
    
    expected_increase = 40.00
    
    # Tolleranza floating point
    assert abs(final_revenue - (initial_revenue + expected_increase)) < 0.01, \
        f"Errore statistiche: Iniziale {initial_revenue}, Aggiunto {expected_increase}, Finale {final_revenue}"

