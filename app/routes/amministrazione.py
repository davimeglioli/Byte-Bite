import logging
from datetime import datetime

from flask import Response, jsonify, render_template
from fpdf import FPDF, XPos, YPos

from app.auth import accesso_richiesto, richiedi_permesso
from app import app
from app.db import esegui_query
from app.services import carica_ordini, carica_prodotti, costruisci_dati_statistiche

logger = logging.getLogger(__name__)


def _tronca_testo(testo, max_len):
    testo = str(testo)
    return testo if len(testo) <= max_len else testo[:max_len - 3] + "..."


def _stampa_tabella_pdf(pdf, titolo, headers, righe, col_widths):
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, titolo, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "B", 10)
    for header, w in zip(headers, col_widths):
        pdf.cell(w, 7, str(header), border=1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 10)
    for riga in righe:
        for value, w in zip(riga, col_widths):
            testo = _tronca_testo(str(value), 48)
            pdf.cell(w, 7, testo, border=1)
        pdf.ln()
    pdf.ln(6)


@app.route("/amministrazione/")
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def amministrazione():
    ordini = carica_ordini()
    prodotti, categorie, prima_categoria = carica_prodotti()

    utenti_db = esegui_query("SELECT id, username, is_admin, attivo FROM utenti ORDER BY username")
    utenti = []
    for riga in utenti_db:
        utente = dict(riga)
        righe_permessi = esegui_query(
            "SELECT pagina FROM permessi_pagine WHERE utente_id = %s",
            (utente["id"],),
        )
        utente["permessi"] = [permesso["pagina"] for permesso in righe_permessi]
        utenti.append(utente)

    return render_template(
        "amministrazione.html",
        ordini=ordini,
        prodotti=prodotti,
        utenti=utenti,
        categorie=categorie,
        prima_categoria=prima_categoria,
    )


@app.route("/api/statistiche")
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def api_statistiche():
    return jsonify(costruisci_dati_statistiche())


@app.route("/api/statistiche/report")
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def esporta_statistiche():
    dati_statistiche = costruisci_dati_statistiche()
    generato_il = datetime.now()

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_compression(False)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Byte-Bite - Report Statistiche", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Generato il: {generato_il.strftime('%Y-%m-%d %H:%M:%S')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(4)

    totali = dati_statistiche.get("totali", {})
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Riepilogo", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, f"Ordini totali: {totali.get('ordini_totali', 0)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Ordini completati: {totali.get('ordini_completati', 0)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Incasso totale (EUR): {float(totali.get('totale_incasso', 0)):.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Incasso contanti (EUR): {float(totali.get('totale_contanti', 0)):.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Incasso carta (EUR): {float(totali.get('totale_carta', 0)):.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    categorie = dati_statistiche.get("categorie", [])
    righe_categorie = [(c.get("categoria_dashboard", ""), c.get("totale", 0)) for c in categorie]
    if righe_categorie:
        _stampa_tabella_pdf(pdf, "Ordini per categoria", ["Categoria", "Totale"], righe_categorie, [120, 40])

    ore = dati_statistiche.get("ore", [])
    righe_ore = [(o.get("ora", ""), o.get("totale", 0)) for o in ore]
    if righe_ore:
        _stampa_tabella_pdf(pdf, "Andamento ordini per ora", ["Ora", "Totale"], righe_ore, [40, 40])

    top10 = dati_statistiche.get("top10", [])
    righe_top10 = [(p.get("nome", ""), p.get("venduti", 0)) for p in top10]
    if righe_top10:
        _stampa_tabella_pdf(pdf, "Prodotti piu venduti (Top 10)", ["Prodotto", "Venduti"], righe_top10, [120, 40])

    ordini = esegui_query("""
        SELECT o.id, o.nome_cliente, o.numero_tavolo, o.numero_persone, o.asporto, o.data_ordine, o.metodo_pagamento, o.completato
        FROM ordini o
        ORDER BY o.data_ordine DESC
    """)

    if ordini:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 9, "Dettaglio ordini", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

        for ordine in ordini:
            id_ordine = ordine["id"]
            righe_prodotti = esegui_query(
                """
                SELECT p.nome, p.categoria_menu, op.quantita, p.prezzo,
                       (p.prezzo * op.quantita) AS subtotale, op.stato
                FROM ordini_prodotti op
                JOIN prodotti p ON p.id = op.prodotto_id
                WHERE op.ordine_id = %s
                ORDER BY p.categoria_menu, p.nome
                """,
                (id_ordine,),
            )
            totale_ordine = sum((r["subtotale"] or 0) for r in righe_prodotti) if righe_prodotti else 0

            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 7, f"Ordine #{id_ordine}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 6, f"Data: {ordine['data_ordine']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.cell(0, 6, f"Cliente: {ordine['nome_cliente']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            tipo = "Asporto" if ordine["asporto"] else "Tavolo"
            tavolo = "-" if ordine["numero_tavolo"] is None else ordine["numero_tavolo"]
            persone = "-" if ordine["numero_persone"] is None else ordine["numero_persone"]
            completato = "Si" if ordine["completato"] else "No"
            pdf.cell(
                0, 6,
                f"Tipo: {tipo} | Tavolo: {tavolo} | Persone: {persone} | Pagamento: {ordine['metodo_pagamento']} | Completato: {completato}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
            pdf.cell(0, 6, f"Totale ordine (EUR): {float(totale_ordine):.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)

            if righe_prodotti:
                headers = ["Prodotto", "Qta", "Prezzo", "Subtot.", "Stato"]
                widths = [80, 15, 20, 20, 35]

                pdf.set_font("Helvetica", "B", 10)
                for header, w in zip(headers, widths):
                    pdf.cell(w, 7, header, border=1)
                pdf.ln()

                pdf.set_font("Helvetica", "", 10)
                for riga in righe_prodotti:
                    nome_prodotto = f"{riga['categoria_menu']} - {riga['nome']}"
                    valori = [
                        _tronca_testo(nome_prodotto, 44),
                        riga["quantita"],
                        f"{float(riga['prezzo']):.2f}",
                        f"{float(riga['subtotale'] or 0):.2f}",
                        _tronca_testo(riga["stato"], 18),
                    ]
                    for val, w in zip(valori, widths):
                        pdf.cell(w, 7, str(val), border=1)
                    pdf.ln()

            pdf.ln(6)

    pdf_bytes = bytes(pdf.output())
    filename = f"statistiche_{generato_il.strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
