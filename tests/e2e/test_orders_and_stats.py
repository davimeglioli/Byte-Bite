import time
from playwright.sync_api import expect

# ==================== Ordini e Statistiche ====================


def test_routing_ordini_e_incremento_incasso(pagina, url_base):
    # Helper per convertire stringa valuta in float.
    def estrai_valuta(testo):
        pulito = testo.replace("€", "").replace(",", ".").strip()
        return float(pulito) if pulito else 0.0

    # Login admin e accesso amministrazione.
    pagina.goto(f"{url_base}/login")
    pagina.fill('input[name="username"]', "admin")
    pagina.fill('input[name="password"]', "admin")
    pagina.click('button[type="submit"]')
    pagina.click("text=Amministrazione")

    # Legge incasso iniziale dalle card statistiche.
    pagina.wait_for_selector(".scheda-statistica .valore-statistica")
    valori_statistiche = pagina.locator(".scheda-statistica .valore-statistica")
    expect(valori_statistiche.first).to_be_visible()
    incasso_iniziale = estrai_valuta(valori_statistiche.nth(2).inner_text())

    # Crea un prodotto per ciascuna dashboard.
    categorie = ["Bar", "Cucina", "Griglia", "Gnoccheria"]
    prodotti_per_categoria = {}

    for categoria in categorie:
        # Nome unico per evitare collisioni.
        nome_prodotto = f"Test {categoria} {int(time.time())}"
        prodotti_per_categoria[categoria] = nome_prodotto

        # Apre modale aggiunta prodotto.
        pagina.locator(".sezione-tabella", has_text="Dettaglio prodotti").locator(
            ".tasto-aggiungi-header"
        ).click()
        expect(pagina.locator("#modaleAggiunta")).to_be_visible()

        # Compila form prodotto e conferma.
        pagina.fill("#nomeProdottoAggiunta", nome_prodotto)
        pagina.fill("#prezzoProdottoAggiunta", "10.00")
        pagina.fill("#quantitaProdottoAggiunta", "100")
        pagina.select_option("#categoriaMenuAggiunta", "Da Bere" if categoria == "Bar" else "Primi")
        pagina.select_option("#categoriaDashboardAggiunta", categoria)
        pagina.click("#formAggiunta .bottone-conferma")

        # Attende chiusura modale e aggiornamento.
        expect(pagina.locator("#modaleAggiunta")).not_to_be_visible()
        pagina.wait_for_timeout(200)

    # Passa alla cassa per creare un ordine con tutti i prodotti.
    pagina.goto(f"{url_base}/cassa/")

    for categoria, nome_prodotto in prodotti_per_categoria.items():
        # Seleziona linguetta corretta in base alla categoria.
        linguetta = "Da Bere" if categoria == "Bar" else "Primi"
        pagina.locator(f'.linguetta[data-categoria="{linguetta}"]').click()

        # Aggiunge prodotto al carrello.
        scheda_prodotto = pagina.locator(".prodotto", has_text=nome_prodotto)
        expect(scheda_prodotto).to_be_visible()
        scheda_prodotto.locator(".tasto-piu").click()

    # Compila form ordine.
    pagina.fill('input[name="nome_cliente"]', "Cliente Test")
    pagina.fill('input[name="numero_tavolo"]', "1")
    pagina.fill('input[name="numero_persone"]', "4")
    pagina.select_option('select[name="metodo_pagamento"]', "Contanti")

    # Verifica totale carrello (4 * 10.00).
    totale_visibile = pagina.locator(".totale-carrello h2").nth(1).inner_text()
    assert "40.00" in totale_visibile

    # Invia ordine e attende elaborazione.
    pagina.click(".tasto-conferma-ordine")
    pagina.wait_for_timeout(1000)

    # Verifica routing: su Bar deve apparire solo prodotto Bar.
    pagina.goto(f"{url_base}/dashboard/Bar")
    expect(pagina.locator(".scheda-ordine", has_text=prodotti_per_categoria["Bar"])).to_be_visible()
    expect(pagina.locator(".scheda-ordine", has_text=prodotti_per_categoria["Cucina"])).not_to_be_visible()

    # Verifica routing: su Cucina deve apparire solo prodotto Cucina.
    pagina.goto(f"{url_base}/dashboard/Cucina")
    expect(pagina.locator(".scheda-ordine", has_text=prodotti_per_categoria["Cucina"])).to_be_visible()
    expect(pagina.locator(".scheda-ordine", has_text=prodotti_per_categoria["Bar"])).not_to_be_visible()

    # Verifica routing: dashboard Griglia.
    pagina.goto(f"{url_base}/dashboard/Griglia")
    expect(pagina.locator(".scheda-ordine", has_text=prodotti_per_categoria["Griglia"])).to_be_visible()

    # Verifica routing: dashboard Gnoccheria.
    pagina.goto(f"{url_base}/dashboard/Gnoccheria")
    expect(pagina.locator(".scheda-ordine", has_text=prodotti_per_categoria["Gnoccheria"])).to_be_visible()

    # Torna in amministrazione e rilegge incasso finale.
    pagina.goto(f"{url_base}/amministrazione")
    pagina.wait_for_selector(".scheda-statistica .valore-statistica")
    incasso_finale = estrai_valuta(pagina.locator(".scheda-statistica .valore-statistica").nth(2).inner_text())

    # Verifica incremento incasso atteso.
    aumento_atteso = 40.00
    assert abs(incasso_finale - (incasso_iniziale + aumento_atteso)) < 0.01
