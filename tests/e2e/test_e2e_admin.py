from playwright.sync_api import expect

# ==================== Helper ====================


def _login_admin(pagina, url_base):
    pagina.goto(f"{url_base}/login")
    pagina.fill('input[name="username"]', "admin")
    pagina.fill('input[name="password"]', "admin")
    pagina.click('button[type="submit"]')


def _vai_a_amministrazione(pagina):
    pagina.click("text=Amministrazione")
    # La prima linguetta riceve la classe "attiva" nel setup sincrono del DOMContentLoaded.
    # La sua visibilità garantisce che tutte le window.apriModale* siano già definite.
    expect(pagina.locator("li.linguetta.attiva")).to_be_visible()


# ==================== Amministrazione ====================


def test_amministrazione_crud_prodotto(pagina, url_base):
    _login_admin(pagina, url_base)
    _vai_a_amministrazione(pagina)

    # Apre modale aggiunta prodotto.
    sezione_prodotti = pagina.locator(".sezione-tabella", has_text="Dettaglio prodotti")
    sezione_prodotti.locator(".tasto-aggiungi-header").click()
    expect(pagina.locator("#modaleAggiunta")).to_be_visible()

    # Compila e invia il form.
    pagina.fill("#nomeProdottoAggiunta", "Prodotto E2E")
    pagina.fill("#prezzoProdottoAggiunta", "5.50")
    pagina.fill("#quantitaProdottoAggiunta", "10")
    pagina.select_option("#categoriaMenuAggiunta", "Da Bere")
    pagina.select_option("#categoriaDashboardAggiunta", "Bar")
    pagina.click("#formAggiunta .bottone-conferma")

    # La modale si chiude solo dopo che la fetch è completata: aspettarne la chiusura
    # garantisce che il prodotto sia già nel DB prima di proseguire.
    expect(pagina.locator("#modaleAggiunta")).not_to_be_visible()

    # Il tab "Da Bere" è server-rendered: un reload è necessario per vederlo.
    pagina.reload()
    expect(pagina.locator("li.linguetta.attiva")).to_be_visible()
    pagina.locator('li[data-categoria="Da Bere"]').click()

    # Verifica presenza e dati del prodotto nella tabella.
    riga = pagina.locator("tr", has_text="Prodotto E2E").first
    expect(riga).to_be_visible()
    expect(riga).to_contain_text("5.50 €")
    expect(riga).to_contain_text("10")

    # Rifornimento: aggiunge 5 unità (10 → 15).
    riga.locator("button.bottone-rifornimento").click()
    expect(pagina.locator("#modaleRifornimento")).to_be_visible()
    pagina.fill("#quantitaInput", "5")
    pagina.click("#formRifornimento .bottone-conferma")
    expect(pagina.locator("#modaleRifornimento")).not_to_be_visible()
    # La tabella si aggiorna via evento socket: expect riprova finché non vede "15".
    expect(riga).to_contain_text("15")

    # Eliminazione prodotto.
    riga = pagina.locator("tr", has_text="Prodotto E2E").first
    riga.locator("button.bottone-cancella").click()
    expect(pagina.locator("#modaleElimina")).to_be_visible()
    pagina.click("#btnConfermaElimina")
    expect(pagina.locator("#modaleElimina")).not_to_be_visible()
    # La riga sparisce dopo l'aggiornamento socket della tabella.
    expect(riga).not_to_be_visible()


def test_amministrazione_visualizza_statistiche(pagina, url_base):
    _login_admin(pagina, url_base)
    _vai_a_amministrazione(pagina)

    expect(pagina.locator("#grafico1")).to_be_visible()
    expect(pagina.locator("#grafico2")).to_be_visible()
    expect(pagina.locator(".scheda-statistica").first).to_be_visible()
