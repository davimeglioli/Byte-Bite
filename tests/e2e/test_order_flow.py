import pytest
import re
from playwright.sync_api import Browser, expect

def test_full_order_flow(browser: Browser, base_url):
    """
    Test End-to-End completo:
    1. Login Cassa
    2. Login Cucina (Admin)
    3. Creazione Ordine (Cassa)
    4. Verifica e Avanzamento Ordine (Cucina)
    """
    
    # --- 1. SETUP CONTESTI ---
    # Contesto Cassa
    context_cassa = browser.new_context()
    page_cassa = context_cassa.new_page()
    
    # Contesto Cucina
    context_cucina = browser.new_context()
    page_cucina = context_cucina.new_page()
    
    # --- 2. LOGIN ---
    
    # Login Cassa
    page_cassa.goto(f"{base_url}/login")
    page_cassa.fill('input[name="username"]', "cassa")
    page_cassa.fill('input[name="password"]', "cassa")
    page_cassa.click('button[type="submit"]')
    page_cassa.click('text=Cassa')
    expect(page_cassa).to_have_url(re.compile(r"/cassa/$"))
    
    # Login Cucina (come Admin)
    page_cucina.goto(f"{base_url}/login")
    page_cucina.fill('input[name="username"]', "admin")
    page_cucina.fill('input[name="password"]', "admin")
    page_cucina.click('button[type="submit"]')
    # Naviga alla dashboard cucina
    page_cucina.goto(f"{base_url}/dashboard/cucina/")
    expect(page_cucina.locator("h2").first).to_contain_text("Dashboard Cucina")
    
    # --- 3. CREAZIONE ORDINE (CASSA) ---
    
    # Seleziona categoria 'Primi'
    page_cassa.click('li[data-categoria="Primi"]')
    
    # Aggiungi 'Pasta Test'
    prodotto = page_cassa.locator('.prodotto', has_text='Pasta Test')
    # Assicuriamoci che sia visibile
    expect(prodotto).to_be_visible()
    
    # Clicca +
    prodotto.locator('.tasto-piu').click()
    
    # Compila form
    page_cassa.fill('#nome-cliente', 'Mario Rossi')
    page_cassa.fill('#numero-tavolo', '5')
    page_cassa.fill('#numero-persone', '2')
    
    # Invia Ordine
    # Cerca il bottone di conferma nel form (usando la classe specifica)
    page_cassa.click('.tasto-conferma-ordine')
    
    # --- 4. VERIFICA LATO CUCINA ---
    
    # L'ordine dovrebbe apparire automaticamente (WebSocket)
    # Definiamo la griglia degli ordini attivi (la prima)
    griglia_attivi = page_cucina.locator('.griglia-ordini').first
    card = griglia_attivi.locator('.scheda-ordine', has_text='Mario Rossi')
    
    expect(card).to_be_visible(timeout=10000) # Dai tempo al websocket
    
    # Verifica dettagli
    expect(card).to_contain_text("Tavolo: 5")
    expect(card).to_contain_text("Persone: 2")
    expect(card).to_contain_text("Pasta Test")
    
    # --- 5. AVANZAMENTO STATO ---
    
    btn_azione = card.locator('.tasto-azione-ordine')
    
    # Stato iniziale: In Attesa
    expect(btn_azione).to_have_text("In Attesa")
    
    # Click -> In Preparazione
    btn_azione.click()
    # Attendi che il testo cambi (può richiedere roundtrip server)
    expect(btn_azione).to_have_text("In Preparazione")
    # Attendi che anche la card rifletta lo stato (evita race condition)
    expect(card).to_have_attribute("data-status", "In Preparazione")
    
    # Click -> Pronto
    btn_azione.click()
    expect(btn_azione).to_have_text("Pronto")
    expect(card).to_have_attribute("data-status", "Pronto")
    
    # --- AUTO-COMPLETAMENTO ---
    # Invece di cliccare, attendiamo che il timer (10s) sposti l'ordine in completato
    # Usiamo un timeout > 10s per sicurezza (es. 15s)
    expect(card).not_to_be_visible(timeout=15000)
    
    # Verifica nella lista completati
    # La lista completati è il secondo .griglia-ordini
    griglia_completati = page_cucina.locator('.griglia-ordini').nth(1)
    card_completata = griglia_completati.locator('.scheda-ordine', has_text='Mario Rossi')
    expect(card_completata).to_be_visible()
    
    # Cleanup contesti
    context_cassa.close()
    context_cucina.close()
