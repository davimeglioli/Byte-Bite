from playwright.sync_api import expect

# ==================== Amministrazione ====================


def test_amministrazione_crud_prodotto(pagina, url_base):
    # Login come admin.
    pagina.goto(f"{url_base}/login")
    pagina.fill('input[name="username"]', "admin")
    pagina.fill('input[name="password"]', "admin")
    pagina.click('button[type="submit"]')
    # Apre sezione amministrazione.
    pagina.click("text=Amministrazione")

    # Apre modale aggiunta prodotto.
    sezione_prodotti = pagina.locator(".sezione-tabella", has_text="Dettaglio prodotti")
    sezione_prodotti.locator(".tasto-aggiungi-header").click()

    # Compila form aggiunta prodotto e conferma.
    expect(pagina.locator("#modaleAggiunta")).to_be_visible()
    pagina.fill("#nomeProdottoAggiunta", "Prodotto E2E")
    pagina.fill("#prezzoProdottoAggiunta", "5.50")
    pagina.fill("#quantitaProdottoAggiunta", "10")
    pagina.select_option("#categoriaMenuAggiunta", "Da Bere")
    pagina.select_option("#categoriaDashboardAggiunta", "Bar")
    pagina.click("#formAggiunta .bottone-conferma")

    # Seleziona la linguetta corretta per visualizzare il prodotto.
    linguetta_da_bere = pagina.locator('li[data-categoria="Da Bere"]')
    if linguetta_da_bere.count() > 0:
        linguetta_da_bere.click()
    else:
        # In alcuni casi la linguetta compare dopo refresh.
        pagina.reload()
        pagina.locator('li[data-categoria="Da Bere"]').click()

    # Attende che l'interfaccia aggiorni la tabella.
    pagina.wait_for_timeout(50)

    # Verifica che la riga del prodotto sia presente.
    riga = pagina.locator("tr", has_text="Prodotto E2E").first
    expect(riga).to_be_visible()
    expect(riga).to_contain_text("5.50 €")
    expect(riga).to_contain_text("10")

    # Esegue rifornimento prodotto.
    riga.locator("button.bottone-rifornimento").click()
    expect(pagina.locator("#modaleRifornimento")).to_be_visible()
    pagina.fill("#quantitaInput", "5")
    pagina.click("#formRifornimento .bottone-conferma")
    expect(pagina.locator("#modaleRifornimento")).not_to_be_visible()

    # Verifica quantità aggiornata (10 + 5).
    expect(riga).to_contain_text("15")

    # Elimina prodotto e conferma.
    riga = pagina.locator("tr", has_text="Prodotto E2E").first
    riga.locator("button.bottone-cancella").click()
    expect(pagina.locator("#modaleElimina")).to_be_visible()
    pagina.click("#btnConfermaElimina")
    # Verifica che la riga scompaia.
    expect(riga).not_to_be_visible()

def test_amministrazione_visualizza_statistiche(pagina, url_base):
    # Login come admin.
    pagina.goto(f"{url_base}/login")
    pagina.fill('input[name="username"]', "admin")
    pagina.fill('input[name="password"]', "admin")
    pagina.click('button[type="submit"]')
    # Apre sezione amministrazione.
    pagina.click("text=Amministrazione")

    # Verifica presenza grafici e card statistiche.
    expect(pagina.locator("#grafico1")).to_be_visible()
    expect(pagina.locator("#grafico2")).to_be_visible()
    expect(pagina.locator(".scheda-statistica").first).to_be_visible()
