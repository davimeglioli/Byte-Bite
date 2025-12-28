import pytest
import re
from playwright.sync_api import Page, expect

def test_admin_crud_prodotto(page: Page, base_url):
    """
    Test End-to-End Amministrazione Prodotti:
    1. Login Admin
    2. Creazione Prodotto
    3. Verifica in tabella
    4. Rifornimento Prodotto
    5. Eliminazione Prodotto
    """
    
    # --- 1. LOGIN ---
    print("DEBUG: Starting Login")
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.click('button[type="submit"]')
    page.click('text=Amministrazione')
    print("DEBUG: Login Complete")
    
    # --- 2. CREAZIONE PRODOTTO ---
    print("DEBUG: Creating Product")
    
    # Clicca "Aggiungi" nella sezione Prodotti
    # Cerchiamo la sezione "Dettaglio prodotti" e clicchiamo il tasto +
    section_prodotti = page.locator('.sezione-tabella', has_text="Dettaglio prodotti")
    section_prodotti.locator('.tasto-aggiungi-header').click()
    
    # Compila modale
    expect(page.locator('#modaleAggiunta')).to_be_visible()
    page.fill('#nomeProdottoAggiunta', 'Prodotto E2E')
    page.fill('#prezzoProdottoAggiunta', '5.50')
    page.fill('#quantitaProdottoAggiunta', '10')
    page.select_option('#categoriaMenuAggiunta', 'Da Bere')
    page.select_option('#categoriaDashboardAggiunta', 'Bar')
    
    # Conferma
    page.click('#formAggiunta .btn-conferma')
    
    # --- 3. VERIFICA ---
    
    # Clicca sulla tab corretta per visualizzare il prodotto
    # Dato che "Da Bere" potrebbe non essere visibile se ci sono molte categorie,
    # ci assicuriamo di trovarla
    tab_da_bere = page.locator('li[data-categoria="Da Bere"]')
    
    # Se la tab esiste, clicchiamo
    if tab_da_bere.count() > 0:
        tab_da_bere.click()
    else:
        # Se non c'è la tab "Da Bere", potrebbe essere perché è la prima volta che aggiungiamo questa categoria?
        # In questo caso ricarichiamo la pagina per aggiornare le tab
        page.reload()
        page.locator('li[data-categoria="Da Bere"]').click()
        
    # Forza un attimo di attesa per l'animazione/filtro JS
    page.wait_for_timeout(50)

    # Attendi che la tabella si aggiorni (websocket o reload)
    # Cerchiamo la riga che contiene il nuovo prodotto
    # Usiamo first() perché se il test è fallito prima, potrebbero esserci duplicati nel DB
    row = page.locator('tr', has_text='Prodotto E2E').first
    expect(row).to_be_visible()
    # Il formato è "5.50 €", non "€5.50"
    expect(row).to_contain_text('5.50 €')
    expect(row).to_contain_text('10') # Quantità
    
    # --- 4. RIFORNIMENTO ---
    
    # Clicca pulsante rifornisci (icona +) sulla riga corretta
    btn_rifornisci = row.locator('button.bottone-rifornimento')
    btn_rifornisci.click()
    
    # Compila modale rifornimento
    expect(page.locator('#modaleRifornimento')).to_be_visible()
    page.fill('#quantitaInput', '5')
    page.click('#formRifornimento .btn-conferma')
    
    # Attendi che la modale si chiuda per evitare che copra il bottone elimina
    expect(page.locator('#modaleRifornimento')).not_to_be_visible()

    # Verifica aggiornamento quantità (10 + 5 = 15)
    # Potrebbe servire un piccolo wait per il websocket update
    expect(row).to_contain_text('15')
    
    # --- 5. ELIMINAZIONE ---
    
    # Forza il click usando JS se necessario, o assicurati che sia visibile
    # Ricarichiamo la riga per essere sicuri di avere l'elemento aggiornato dopo il rifornimento
    row = page.locator('tr', has_text='Prodotto E2E').first
    btn_elimina = row.locator('button.bottone-cancella')
    
    # Assicuriamoci che la riga sia visibile (dovrebbe esserlo ora che abbiamo fixato il JS)
    expect(row).to_be_visible()
    
    # Click normale (senza force)
    btn_elimina.click()
    
    # Conferma eliminazione
    expect(page.locator('#modaleElimina')).to_be_visible()
    page.click('#btnConfermaElimina')
    
    # Verifica che la riga sia sparita
    expect(row).not_to_be_visible()

def test_admin_stats_visible(page: Page, base_url):
    """Verifica che le statistiche siano caricate."""
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.click('button[type="submit"]')
    page.click('text=Amministrazione')
    
    # Verifica presenza grafici (Canvas)
    expect(page.locator('#grafico1')).to_be_visible()
    expect(page.locator('#grafico2')).to_be_visible()
    
    # Verifica presenza card statistiche
    expect(page.locator('.scheda-statistica').first).to_be_visible()
