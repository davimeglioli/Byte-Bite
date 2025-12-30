import time
from playwright.sync_api import expect

# ==================== Real Time ====================


def test_ordini_in_tempo_reale(navigatore, url_base):
    # Apre contesto dashboard.
    contesto_dashboard = navigatore.new_context()
    pagina_dashboard = contesto_dashboard.new_page()

    # Login admin e accesso amministrazione.
    pagina_dashboard.goto(f"{url_base}/login")
    pagina_dashboard.fill('input[name="username"]', "admin")
    pagina_dashboard.fill('input[name="password"]', "admin")
    pagina_dashboard.click('button[type="submit"]')
    pagina_dashboard.click("text=Amministrazione")

    # Crea un prodotto con nome unico.
    nome_prodotto = f"Mojito Realtime {int(time.time())}"
    # Apre modale aggiunta prodotto.
    pagina_dashboard.locator(".sezione-tabella", has_text="Dettaglio prodotti").locator(
        ".tasto-aggiungi-header"
    ).click()

    # Compila modale e conferma.
    expect(pagina_dashboard.locator("#modaleAggiunta")).to_be_visible()
    pagina_dashboard.fill("#nomeProdottoAggiunta", nome_prodotto)
    pagina_dashboard.fill("#prezzoProdottoAggiunta", "8.00")
    pagina_dashboard.fill("#quantitaProdottoAggiunta", "50")
    pagina_dashboard.select_option("#categoriaMenuAggiunta", "Da Bere")
    pagina_dashboard.select_option("#categoriaDashboardAggiunta", "Bar")
    pagina_dashboard.click("#formAggiunta .bottone-conferma")
    expect(pagina_dashboard.locator("#modaleAggiunta")).not_to_be_visible()

    # Apre dashboard Bar.
    pagina_dashboard.goto(f"{url_base}/dashboard/Bar")
    expect(pagina_dashboard.locator("h2", has_text="Bar")).to_be_visible()

    # Apre contesto cassa.
    contesto_cassa = navigatore.new_context()
    pagina_cassa = contesto_cassa.new_page()

    # Login cassa.
    pagina_cassa.goto(f"{url_base}/login")
    pagina_cassa.fill('input[name="username"]', "cassa")
    pagina_cassa.fill('input[name="password"]', "cassa")
    pagina_cassa.click('button[type="submit"]')
    expect(pagina_cassa).not_to_have_url(f"{url_base}/login")

    # Entra in cassa e seleziona categoria.
    pagina_cassa.goto(f"{url_base}/cassa/")
    linguetta = pagina_cassa.locator('.linguetta[data-categoria="Da Bere"]')
    expect(linguetta).to_be_visible()
    linguetta.click(force=True)

    # Aggiunge il prodotto al carrello.
    scheda_prodotto = pagina_cassa.locator(".prodotto", has_text=nome_prodotto)
    expect(scheda_prodotto).to_be_visible()
    scheda_prodotto.locator(".tasto-piu").click()

    # Compila form ordine e invia.
    pagina_cassa.fill('input[name="nome_cliente"]', "Cliente Realtime")
    pagina_cassa.fill('input[name="numero_tavolo"]', "5")
    pagina_cassa.fill('input[name="numero_persone"]', "2")
    pagina_cassa.select_option('select[name="metodo_pagamento"]', "Contanti")
    pagina_cassa.click(".tasto-conferma-ordine")

    # Verifica che la scheda ordine appaia sulla dashboard senza refresh.
    scheda_ordine = pagina_dashboard.locator(".scheda-ordine", has_text=nome_prodotto)
    expect(scheda_ordine).to_be_visible()
    expect(scheda_ordine).to_contain_text("Cliente Realtime")
    expect(scheda_ordine).to_contain_text("Tavolo: 5")

    # Chiude i contesti.
    contesto_cassa.close()
    contesto_dashboard.close()
