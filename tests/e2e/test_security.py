import pytest
from playwright.sync_api import Page, expect

def test_security_access_control(page: Page, base_url):
    """
    Test 4: Sicurezza (Access Control)
    Verifica che le pagine protette e le API sensibili non siano accessibili senza login.
    """
    
    # 1. Accesso a /amministrazione senza login
    print("DEBUG: Testing /amministrazione access without login")
    page.goto(f"{base_url}/amministrazione")
    # Dovrebbe reindirizzare al login
    expect(page).to_have_url(f"{base_url}/login/")
    # Il form potrebbe non avere action esplicita se posta sulla stessa pagina
    expect(page.locator('form.modulo-login')).to_be_visible()
    
    # 2. Accesso a una Dashboard senza login
    print("DEBUG: Testing /dashboard/Bar access without login")
    page.goto(f"{base_url}/dashboard/Bar/")
    # Dovrebbe reindirizzare al login
    expect(page).to_have_url(f"{base_url}/login/")
    
    # 3. Accesso a API protetta senza login (es. statistiche)
    print("DEBUG: Testing /api/statistiche/ access without login")
    response = page.request.get(f"{base_url}/api/statistiche/")
    # Se reindirizza, lo status potrebbe essere 200 (pagina login) o 302/303.
    # Se è un'API JSON pura, dovrebbe dare 401/403.
    # Flask Login manager di solito reindirizza.
    # Controlliamo che l'URL finale sia login o che lo status sia 403 se gestito così.
    
    # Nel codice app.py: @accesso_richiesto fa redirect a 'accesso' (login)
    print(f"DEBUG: API Response URL: {response.url}")
    assert "/login/" in response.url, f"API access did not redirect to login. URL: {response.url}"
    
    # 4. Accesso come utente non-admin a /amministrazione
    # Creiamo un utente base se non esiste, o usiamo credenziali errate per simulare?
    # No, dobbiamo simulare un utente loggato ma senza permessi admin.
    # Poiché non abbiamo una registrazione pubblica, questo test richiederebbe di creare un utente via DB.
    # Per ora ci limitiamo al controllo "Anonymous vs Protected".
    
    print("DEBUG: Security test passed")
