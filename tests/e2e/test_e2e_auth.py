import re
from playwright.sync_api import Page, expect

def test_login_failure(page: Page, base_url):
    """Test login con credenziali errate."""
    page.goto(f"{base_url}/login")
    
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "sbagliata")
    page.click('button[type="submit"]')
    
    # Verifica messaggio errore
    expect(page.locator(".messaggio-errore")).to_contain_text("Username o password errata")
    expect(page).to_have_url(re.compile(r"/login"))

def test_login_success_admin(page: Page, base_url):
    """Test login amministratore."""
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.click('button[type="submit"]')
    
    # Redirect alla home
    expect(page).to_have_url(re.compile(r"/$"))
    
    # Verifica presenza tasti
    expect(page.get_by_role("link", name="Amministrazione")).to_be_visible()
    
    # Accesso ad area amministrazione
    page.click('text=Amministrazione')
    expect(page).to_have_url(re.compile(r"/amministrazione/$"))

def test_login_success_cassa(page: Page, base_url):
    """Test login cassiere e restrizioni."""
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', "cassa")
    page.fill('input[name="password"]', "cassa")
    page.click('button[type="submit"]')
    
    expect(page).to_have_url(re.compile(r"/$"))
    
    # Accesso a Cassa OK
    page.click('text=Cassa')
    expect(page).to_have_url(re.compile(r"/cassa/$"))
    
    # Torna indietro e prova Amministrazione (Dovrebbe essere vietato)
    page.goto(f"{base_url}/")
    
    # Playwright non gestisce automaticamente il 403 come eccezione durante la navigazione,
    # ma la pagina mostrerà il contenuto dell'errore.
    # Se app.py ritorna "403 Forbidden", verifichiamo il testo.
    response = page.goto(f"{base_url}/amministrazione/")
    assert response.status == 403
