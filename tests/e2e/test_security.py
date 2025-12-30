from playwright.sync_api import expect

# ==================== Sicurezza ====================


def test_controllo_accessi_senza_login(pagina, url_base):
    # Prova accesso ad amministrazione senza login.
    pagina.goto(f"{url_base}/amministrazione")
    # Deve reindirizzare al login.
    expect(pagina).to_have_url(f"{url_base}/login/")
    # Verifica presenza form di login.
    expect(pagina.locator("form.modulo-login")).to_be_visible()

    # Prova accesso a una dashboard senza login.
    pagina.goto(f"{url_base}/dashboard/Bar/")
    # Deve reindirizzare al login.
    expect(pagina).to_have_url(f"{url_base}/login/")

    # Prova accesso a endpoint statistiche senza login.
    risposta = pagina.request.get(f"{url_base}/api/statistiche/")
    # Deve finire su login (redirect seguito dalla request).
    assert "/login/" in risposta.url
