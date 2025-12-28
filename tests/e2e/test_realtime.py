import pytest
import time
from playwright.sync_api import Page, Browser, expect

def test_realtime_orders(browser: Browser, base_url):
    """
    Test 2: Real-Time Ordini (Dashboard Cucina/Bar)
    Verifica che un ordine inviato da un client appaia istantaneamente sulla dashboard senza refresh.
    Richiede due contesti browser separati.
    """
    
    # --- CONTESTO 1: DASHBOARD (Admin/Bar) ---
    print("DEBUG: Setting up Dashboard Context")
    context_dashboard = browser.new_context()
    page_dashboard = context_dashboard.new_page()
    
    # Login
    page_dashboard.goto(f"{base_url}/login")
    page_dashboard.fill('input[name="username"]', "admin")
    page_dashboard.fill('input[name="password"]', "admin")
    page_dashboard.click('button[type="submit"]')
    
    # Assicuriamoci che esista un prodotto "Mojito" o creiamolo
    # Per semplicità, creiamo un prodotto "Test Realtime" al volo
    page_dashboard.click('text=Amministrazione')
    
    prod_name = f"Mojito Realtime {int(time.time())}"
    print(f"DEBUG: Creating product {prod_name}")
    
    page_dashboard.locator('.sezione-tabella', has_text="Dettaglio prodotti").locator('.tasto-aggiungi-header').click()
    expect(page_dashboard.locator('#modaleAggiunta')).to_be_visible()
    page_dashboard.fill('#nomeProdottoAggiunta', prod_name)
    page_dashboard.fill('#prezzoProdottoAggiunta', '8.00')
    page_dashboard.fill('#quantitaProdottoAggiunta', '50')
    page_dashboard.select_option('#categoriaMenuAggiunta', 'Da Bere')
    page_dashboard.select_option('#categoriaDashboardAggiunta', 'Bar')
    page_dashboard.click('#formAggiunta .btn-conferma')
    expect(page_dashboard.locator('#modaleAggiunta')).not_to_be_visible()

    # Vai alla Dashboard Bar
    page_dashboard.goto(f"{base_url}/dashboard/Bar")
    # Verifica che siamo sulla dashboard e non ci siano ordini pendenti con questo nome (improbabile dato il timestamp)  
    expect(page_dashboard.locator('h2', has_text="Bar")).to_be_visible()

    # --- CONTESTO 2: CASSA (Cliente) ---
    print("DEBUG: Setting up Client Context")
    context_client = browser.new_context()
    page_client = context_client.new_page()
    
    # Login come Cassa
    print(f"DEBUG: Logging in as Cassa")
    page_client.goto(f"{base_url}/login")
    page_client.fill('input[name="username"]', "cassa")
    page_client.fill('input[name="password"]', "cassa")
    page_client.click('button[type="submit"]')
    # Attendi redirect alla home o cassa
    expect(page_client).not_to_have_url(f"{base_url}/login")

    print(f"DEBUG: Navigating to {base_url}/cassa/")
    page_client.goto(f"{base_url}/cassa/")
    
    # Seleziona categoria Da Bere
    print("DEBUG: Clicking category Da Bere")
    tab = page_client.locator('.linguetta[data-categoria="Da Bere"]')
    expect(tab).to_be_visible()
    tab.click(force=True)
    print("DEBUG: Category clicked")
    
    # Aggiungi Mojito
    print("DEBUG: Adding product to cart")
    prod_card = page_client.locator('.prodotto', has_text=prod_name)
    expect(prod_card).to_be_visible()
    prod_card.locator('.tasto-piu').click()
    print("DEBUG: Product added")
    
    # Compila ordine
    print("DEBUG: Filling order form")
    page_client.fill('input[name="nome_cliente"]', "Cliente Realtime")
    page_client.fill('input[name="numero_tavolo"]', "5")
    page_client.fill('input[name="numero_persone"]', "2")
    page_client.select_option('select[name="metodo_pagamento"]', "Contanti")
    
    # Invia Ordine
    print("DEBUG: Submitting order")
    page_client.click('.tasto-conferma-ordine')
    print("DEBUG: Order submitted")
    
    # --- VERIFICA REAL-TIME SU DASHBOARD ---
    print("DEBUG: Verifying real-time update on Dashboard")
    # Senza fare refresh su page_dashboard, l'ordine dovrebbe apparire
    # Cerchiamo una card ordine che contenga il nome del prodotto
    
    new_order_card = page_dashboard.locator('.scheda-ordine', has_text=prod_name)
    
    # Playwright aspetta automaticamente che l'elemento appaia (default timeout 30s)
    # Se i websocket funzionano, apparirà quasi subito.
    print("DEBUG: Waiting for order card to appear")
    expect(new_order_card).to_be_visible()
    
    # Verifica dettagli
    expect(new_order_card).to_contain_text("Cliente Realtime")
    expect(new_order_card).to_contain_text("Tavolo: 5")
    
    print("DEBUG: Real-time update verified!")
    
    context_client.close()
    context_dashboard.close()
