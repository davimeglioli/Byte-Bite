import re
from playwright.sync_api import expect

# ==================== Flusso Ordine ====================


def test_flusso_completo_ordine(navigatore, url_base):
    # Crea due contesti browser separati.
    contesto_cassa = navigatore.new_context()
    pagina_cassa = contesto_cassa.new_page()

    contesto_cucina = navigatore.new_context()
    pagina_cucina = contesto_cucina.new_page()

    # Login cassa.
    pagina_cassa.goto(f"{url_base}/login")
    pagina_cassa.fill('input[name="username"]', "cassa")
    pagina_cassa.fill('input[name="password"]', "cassa")
    pagina_cassa.click('button[type="submit"]')
    pagina_cassa.click("text=Cassa")
    # Verifica URL cassa.
    expect(pagina_cassa).to_have_url(re.compile(r"/cassa/$"))

    # Login admin e accesso dashboard cucina.
    pagina_cucina.goto(f"{url_base}/login")
    pagina_cucina.fill('input[name="username"]', "admin")
    pagina_cucina.fill('input[name="password"]', "admin")
    pagina_cucina.click('button[type="submit"]')
    pagina_cucina.goto(f"{url_base}/dashboard/cucina/")
    # Verifica titolo dashboard.
    expect(pagina_cucina.locator("h2").first).to_contain_text("Dashboard Cucina")

    # Seleziona categoria e aggiunge un prodotto al carrello.
    pagina_cassa.click('li[data-categoria="Primi"]')
    scheda_prodotto = pagina_cassa.locator(".prodotto", has_text="Pasta Test")
    expect(scheda_prodotto).to_be_visible()
    scheda_prodotto.locator(".tasto-piu").click()

    # Compila form ordine.
    pagina_cassa.fill("#nome-cliente", "Mario Rossi")
    pagina_cassa.fill("#numero-tavolo", "5")
    pagina_cassa.fill("#numero-persone", "2")
    # Invia ordine.
    pagina_cassa.click(".tasto-conferma-ordine")

    # Attende che l'ordine appaia nella dashboard.
    griglia_attivi = pagina_cucina.locator(".griglia-ordini").first
    scheda_ordine = griglia_attivi.locator(".scheda-ordine", has_text="Mario Rossi")
    expect(scheda_ordine).to_be_visible(timeout=10000)
    # Verifica dettagli ordine.
    expect(scheda_ordine).to_contain_text("Tavolo: 5")
    expect(scheda_ordine).to_contain_text("Persone: 2")
    expect(scheda_ordine).to_contain_text("Pasta Test")

    # Avanza stato: In Attesa -> In Preparazione.
    pulsante_stato = scheda_ordine.locator(".tasto-azione-ordine")
    expect(pulsante_stato).to_have_text("In Attesa")

    pulsante_stato.click()
    expect(pulsante_stato).to_have_text("In Preparazione")
    expect(scheda_ordine).to_have_attribute("data-status", "In Preparazione")

    # Avanza stato: In Preparazione -> Pronto.
    pulsante_stato.click()
    expect(pulsante_stato).to_have_text("Pronto")
    expect(scheda_ordine).to_have_attribute("data-status", "Pronto")

    # Attende auto-completamento.
    expect(scheda_ordine).not_to_be_visible(timeout=15000)

    # Verifica che la scheda sia tra i completati.
    griglia_completati = pagina_cucina.locator(".griglia-ordini").nth(1)
    scheda_completata = griglia_completati.locator(".scheda-ordine", has_text="Mario Rossi")
    expect(scheda_completata).to_be_visible()

    # Chiude i contesti.
    contesto_cassa.close()
    contesto_cucina.close()
