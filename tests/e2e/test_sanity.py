from playwright.sync_api import expect

# ==================== Sanity ====================


def test_titolo_google(pagina):
    # Naviga verso Google.
    pagina.goto("https://www.google.com")
    # Verifica il titolo della pagina.
    expect(pagina).to_have_title("Google")
