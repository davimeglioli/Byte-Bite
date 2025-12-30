import re
from playwright.sync_api import expect

# ==================== Accesso ====================


def test_accesso_fallisce_con_password_errata(pagina, url_base):
    # Apre la pagina di login.
    pagina.goto(f"{url_base}/login")
    # Compila credenziali con password errata.
    pagina.fill('input[name="username"]', "admin")
    pagina.fill('input[name="password"]', "sbagliata")
    # Invia il form.
    pagina.click('button[type="submit"]')

    # Verifica messaggio e URL di login.
    expect(pagina.locator(".messaggio-errore")).to_contain_text("Username o password errata")
    expect(pagina).to_have_url(re.compile(r"/login"))

def test_accesso_admin_consente_area_amministrazione(pagina, url_base):
    # Apre login e inserisce credenziali admin.
    pagina.goto(f"{url_base}/login")
    pagina.fill('input[name="username"]', "admin")
    pagina.fill('input[name="password"]', "admin")
    # Invia il form.
    pagina.click('button[type="submit"]')

    # Verifica redirect alla home.
    expect(pagina).to_have_url(re.compile(r"/$"))
    # Verifica che il link amministrazione sia visibile.
    expect(pagina.get_by_role("link", name="Amministrazione")).to_be_visible()

    # Accede alla sezione amministrazione.
    pagina.click("text=Amministrazione")
    # Verifica URL della sezione.
    expect(pagina).to_have_url(re.compile(r"/amministrazione/$"))

def test_accesso_cassa_non_consente_area_amministrazione(pagina, url_base):
    # Apre login e inserisce credenziali cassa.
    pagina.goto(f"{url_base}/login")
    pagina.fill('input[name="username"]', "cassa")
    pagina.fill('input[name="password"]', "cassa")
    # Invia il form.
    pagina.click('button[type="submit"]')

    # Verifica redirect alla home.
    expect(pagina).to_have_url(re.compile(r"/$"))
    # Entra nella cassa.
    pagina.click("text=Cassa")
    # Verifica URL cassa.
    expect(pagina).to_have_url(re.compile(r"/cassa/$"))

    # Prova ad accedere ad amministrazione: deve rispondere 403.
    risposta = pagina.goto(f"{url_base}/amministrazione/")
    assert risposta.status == 403
