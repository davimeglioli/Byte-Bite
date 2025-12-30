from playwright.sync_api import expect

# ==================== Navigazione ====================


def test_home_risponde(pagina, url_base):
    # Naviga alla home dell'app.
    pagina.goto(f"{url_base}/")
    # Verifica che il body sia visibile.
    expect(pagina.locator("body")).to_be_visible()
