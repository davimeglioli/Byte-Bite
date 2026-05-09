import logging
import uuid
from datetime import datetime

import bcrypt
from flask import (
    Response,
    abort,
    json,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from fpdf import FPDF, XPos, YPos

from auth import accesso_richiesto, ottieni_utente_loggato, richiedi_permesso
from core import app, socketio, timer_attivi
from db import esegui_query, ottieni_db
from services import (
    cambia_stato_automatico,
    costruisci_dati_statistiche,
    emissione_sicura,
    ottieni_ordini_per_categoria,
    ricalcola_statistiche,
)

logger = logging.getLogger(__name__)


def _normalizza_permessi(permessi):
    if not isinstance(permessi, list):
        permessi = []
    return list(dict.fromkeys(p.strip() for p in permessi if isinstance(p, str) and p.strip()))


# ==================== Route: autenticazione ====================

@app.route("/login/", methods=["GET", "POST"])
def accesso():
    if request.method == "POST":
        # Legge credenziali dal form.
        username = request.form.get("username")
        password = request.form.get("password").encode()

        # Recupera utente e controlla stato account.
        utente = esegui_query("""
            SELECT id, username, password_hash, is_admin, attivo
            FROM utenti WHERE username = %s
        """, (username,), uno=True)

        if not utente:
            # Risposta generica per non rivelare quale campo è sbagliato.
            logger.warning("Tentativo di login con username inesistente: '%s' (IP: %s)", username, request.remote_addr)
            return render_template("login.html", error="Username o password errata")

        if not utente["attivo"]:
            # Blocca account disattivati a livello amministrativo.
            logger.warning("Login negato - account disattivato: '%s' (IP: %s)", username, request.remote_addr)
            return render_template("login.html", error="Account disattivato")

        # Verifica la password con hash bcrypt.
        if not bcrypt.checkpw(password, utente["password_hash"].encode()):
            logger.warning("Login fallito - password errata per utente: '%s' (IP: %s)", username, request.remote_addr)
            return render_template("login.html", error="Username o password errata")

        # Salva i dati minimi in sessione.
        session["id_utente"] = utente["id"]
        session["username"] = utente["username"]

        logger.info("Login riuscito - utente: '%s' (ID: %s, admin: %s, IP: %s)",
                    utente["username"], utente["id"], bool(utente["is_admin"]), request.remote_addr)

        # Redirect verso la home dopo login.
        return redirect(url_for("home"))

    return render_template("login.html")


# ==================== Route: generali ====================

@app.route("/")
def home():
    utente = ottieni_utente_loggato()
    return render_template("index.html", utente=utente)


@app.route("/logout/")
def logout():
    username = session.get("username", "sconosciuto")
    session.clear()
    logger.info("Logout - utente: '%s'", username)
    return redirect(url_for("accesso"))


# ==================== Route: cassa ====================

@app.route("/cassa/")
@accesso_richiesto
@richiedi_permesso("CASSA")
def cassa():
    # Carica tutti i prodotti e li raggruppa per categoria di menu.
    tutti_prodotti = esegui_query("SELECT * FROM prodotti ORDER BY id")

    # Mantiene una lista categorie per l'ordine di visualizzazione.
    categorie = []
    prodotti_per_categoria = {}

    for prodotto in tutti_prodotti:
        # Ogni prodotto viene associato alla sua categoria menu.
        categoria = prodotto["categoria_menu"]
        if categoria not in prodotti_per_categoria:
            # Prima occorrenza: inizializza categoria e lista prodotti.
            categorie.append(categoria)
            prodotti_per_categoria[categoria] = []
        prodotti_per_categoria[categoria].append(prodotto)

    # Permette al frontend di evidenziare l'ultimo ordine creato.
    id_ultimo_ordine = request.args.get("id_ultimo_ordine")

    return render_template(
        "cassa.html",
        categorie=categorie,
        prodotti_per_categoria=prodotti_per_categoria,
        id_ultimo_ordine=id_ultimo_ordine
    )


@app.route("/aggiungi_ordine/", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("CASSA")
def aggiungi_ordine():
    # Converte i campi del form nel formato atteso dal DB.
    asporto = request.form.get("isTakeaway") == "on"
    nome_cliente = request.form.get("nome_cliente")
    numero_tavolo = request.form.get("numero_tavolo")
    numero_persone = request.form.get("numero_persone")
    metodo_pagamento = request.form.get("metodo_pagamento")
    prodotti_json = request.form.get("prodotti")

    if asporto:
        # Per asporto non si memorizzano tavolo e persone.
        numero_tavolo = None
        numero_persone = None

    # Decodifica la lista prodotti dal payload JSON del frontend.
    try:
        prodotti = json.loads(prodotti_json) if prodotti_json else []
    except json.JSONDecodeError:
        # Se arriva JSON invalido, tratta come ordine vuoto.
        prodotti = []

    if not prodotti:
        # Evita la creazione di ordini senza righe.
        logger.warning("Tentativo di creare ordine senza prodotti - utente: '%s'", session.get("username"))
        return redirect(url_for("cassa"), code=303)

    try:
        # Inserisce l'ordine e le righe prodotto in un'unica transazione.
        with ottieni_db() as connessione:
            cursore = connessione.cursor()
            # Inserisce l'intestazione ordine.
            cursore.execute("""
                INSERT INTO ordini (asporto, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (asporto, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento))
            id_ordine = cursore.fetchone()["id"]

            for prodotto in prodotti:
                # Scala la quantità solo se c'è disponibilità sufficiente.
                cursore.execute("""
                    UPDATE prodotti
                    SET quantita = quantita - %s, venduti = venduti + %s
                    WHERE id = %s AND quantita >= %s
                """, (prodotto["quantita"], prodotto["quantita"], prodotto["id"], prodotto["quantita"]))

                if cursore.rowcount == 0:
                    # Se non aggiorna righe, lo stock non basta: abort della transazione.
                    nome_prodotto = prodotto.get("nome", "Sconosciuto")
                    logger.warning("Stock insufficiente per prodotto '%s' (ID: %s) - ordine annullato",
                                   nome_prodotto, prodotto.get("id"))
                    raise Exception(f"Prodotto {nome_prodotto} esaurito o insufficiente.")

                # Registra la riga ordine-prodotti con stato iniziale.
                cursore.execute("""
                    INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)
                    VALUES (%s, %s, %s, %s)
                """, (id_ordine, prodotto["id"], prodotto["quantita"], "In Attesa"))

            # Individua le dashboard da aggiornare in tempo reale.
            cursore.execute("""
                SELECT DISTINCT prodotti.categoria_dashboard
                FROM ordini_prodotti
                JOIN prodotti ON prodotti.id = ordini_prodotti.prodotto_id
                WHERE ordini_prodotti.ordine_id = %s
            """, (id_ordine,))
            categorie_dashboard = [riga["categoria_dashboard"] for riga in cursore.fetchall()]
            # Conferma atomica: o tutto scritto o nulla.
            connessione.commit()

        logger.info("Nuovo ordine #%s creato - cliente: '%s', prodotti: %s, asporto: %s, pagamento: %s, utente: '%s'",
                    id_ordine, nome_cliente, len(prodotti), asporto, metodo_pagamento, session.get("username"))

        # Notifica le dashboard e aggiorna le statistiche in background.
        for categoria in categorie_dashboard:
            emissione_sicura("aggiorna_dashboard", {"categoria": categoria}, stanza=categoria)
        socketio.start_background_task(ricalcola_statistiche)

        return redirect(url_for("cassa") + f"?id_ultimo_ordine={id_ordine}", code=303)

    except Exception as errore:
        logger.error("Errore durante la creazione dell'ordine - utente: '%s': %s", session.get("username"), errore)
        return redirect(url_for("cassa"), code=303)


# ==================== Route: dashboard ====================

@app.route("/dashboard/<category>/")
@accesso_richiesto
@richiedi_permesso("DASHBOARD")
def dashboard(category):
    # Carica gli ordini e mostra la pagina della categoria richiesta.
    ordini_non_completati, ordini_completati = ottieni_ordini_per_categoria(category)
    return render_template(
        "dashboard.html",
        category=category.capitalize(),
        ordini_non_completati=ordini_non_completati,
        ordini_completati=ordini_completati
    )


@app.route("/dashboard/<category>/partial")
@accesso_richiesto
@richiedi_permesso("DASHBOARD")
def dashboard_parziale(category):
    # Restituisce frammenti HTML per refresh parziale via AJAX.
    ordini_non_completati, ordini_completati = ottieni_ordini_per_categoria(category)

    # Renderizza separatamente la lista "in corso" e la lista "completati".
    html_non_completati = render_template(
        "partials/_ordini.html",
        ordini=ordini_non_completati,
        category=category
    )
    html_completati = render_template(
        "partials/_ordini.html",
        ordini=ordini_completati,
        category=category,
        completati=True
    )

    # Restituisce HTML pronto da inserire nel DOM via JS.
    return jsonify({
        "html_non_completati": html_non_completati,
        "html_completati": html_completati
    })


@app.route("/cambia_stato/", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("DASHBOARD")
def cambia_stato():
    # Riceve ordine e categoria, quindi calcola il prossimo stato.
    dati = request.get_json()
    id_ordine = dati.get("ordine_id")
    categoria = dati.get("categoria")

    # Legge lo stato attuale per la categoria.
    riga_stato = esegui_query("""
        SELECT stato
        FROM ordini_prodotti
        JOIN prodotti ON prodotti.id = ordini_prodotti.prodotto_id
        WHERE ordine_id = %s AND prodotti.categoria_dashboard = %s
        LIMIT 1;
    """, (id_ordine, categoria), uno=True)

    if not riga_stato:
        logger.warning("Cambio stato fallito - ordine #%s o categoria '%s' non trovata", id_ordine, categoria)
        return jsonify({"errore": "Ordine o categoria non trovata"}), 404

    stato_attuale = riga_stato["stato"]

    # Lista degli stati in sequenza (usata per avanzare).
    stati = ["In Attesa", "In Preparazione", "Pronto", "Completato"]

    chiave_timer = (id_ordine, categoria)

    if stato_attuale == "Completato":
        logger.warning("Cambio stato rifiutato - ordine #%s [%s] già completato", id_ordine, categoria)
        return jsonify({"errore": "Ordine già completato"}), 400

    if stato_attuale == "Pronto":
        # Se si torna indietro da "Pronto", annulla eventuale completamento automatico.
        if chiave_timer in timer_attivi:
            timer_attivi[chiave_timer]["annulla"] = True
            del timer_attivi[chiave_timer]

        nuovo_stato = "In Preparazione"

    else:
        # Avanza di uno stato rispetto a quello corrente.
        nuovo_stato = stati[stati.index(stato_attuale) + 1]

    # Applica lo stato a tutti i prodotti della categoria per quell'ordine.
    esegui_query("""
        UPDATE ordini_prodotti
        SET stato = %s
        WHERE ordine_id = %s
        AND prodotto_id IN (
            SELECT id FROM prodotti WHERE categoria_dashboard = %s
        );
    """, (nuovo_stato, id_ordine, categoria), commit=True)

    logger.info("Stato ordine #%s [%s]: '%s' → '%s'", id_ordine, categoria, stato_attuale, nuovo_stato)

    # Aggiorna il flag completato dell'ordine in base ai residui.
    residui = esegui_query(
        "SELECT COUNT(*) AS c FROM ordini_prodotti WHERE ordine_id = %s AND stato != 'Completato'",
        (id_ordine,),
        uno=True
    )["c"]
    # Un ordine è completato solo se tutte le righe sono "Completato".
    esegui_query(
        "UPDATE ordini SET completato = %s WHERE id = %s",
        (residui == 0, id_ordine),
        commit=True
    )

    # Notifica la dashboard e ricalcola statistiche in background.
    emissione_sicura("aggiorna_dashboard", {"categoria": categoria}, stanza=categoria)
    socketio.start_background_task(ricalcola_statistiche)

    if nuovo_stato == "Pronto":
        # Avvia un timer che completa automaticamente dopo il timeout.
        if chiave_timer in timer_attivi:
            timer_attivi[chiave_timer]["annulla"] = True
            timer_attivi.pop(chiave_timer, None)

        # Registra il timer così può essere annullato su click successivo.
        id_timer = str(uuid.uuid4())
        timer_attivi[chiave_timer] = {"annulla": False, "id": id_timer}
        socketio.start_background_task(cambia_stato_automatico, id_ordine, categoria, id_timer)

    return jsonify({
        "nuovo_stato": nuovo_stato
    })


# ==================== Route: amministrazione ====================

@app.route("/amministrazione/")
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def amministrazione():
    # Carica dati principali per la pagina amministrazione.
    # Tabella ordini: include totale per riga calcolato via SUM.
    ordini = esegui_query("""
        SELECT o.id, o.nome_cliente, o.numero_tavolo, o.numero_persone, o.data_ordine, o.metodo_pagamento,
               COALESCE(SUM(p.prezzo * op.quantita), 0) as totale
        FROM ordini o
        LEFT JOIN ordini_prodotti op ON o.id = op.ordine_id
        LEFT JOIN prodotti p ON op.prodotto_id = p.id
        GROUP BY o.id
        ORDER BY o.data_ordine DESC
    """)
    # Tabella prodotti: usata per gestione catalogo e magazzino.
    prodotti = esegui_query("""
        SELECT
            id,
            nome,
            categoria_dashboard,
            categoria_menu,
            prezzo,
            disponibile,
            quantita,
            venduti
        FROM prodotti
        ORDER BY MIN(id) OVER (PARTITION BY categoria_menu), id;
    """)

    # Liste categorie per filtro/selector lato UI.
    categorie_db = esegui_query("SELECT categoria_menu FROM prodotti GROUP BY categoria_menu ORDER BY MIN(id)")
    categorie = [riga["categoria_menu"] for riga in categorie_db]
    prima_categoria = categorie[0] if categorie else None

    # Costruisce elenco utenti con i permessi associati.
    utenti_db = esegui_query("SELECT id, username, is_admin, attivo FROM utenti ORDER BY username")
    utenti = []
    for riga in utenti_db:
        # Converte la riga DB in dict serializzabile/iterabile.
        utente = dict(riga)
        righe_permessi = esegui_query(
            "SELECT pagina FROM permessi_pagine WHERE utente_id = %s",
            (utente["id"],),
        )
        # Espone solo la lista di stringhe pagina.
        utente["permessi"] = [permesso["pagina"] for permesso in righe_permessi]
        utenti.append(utente)

    return render_template(
        "amministrazione.html",
        ordini=ordini,
        prodotti=prodotti,
        utenti=utenti,
        categorie=categorie,
        prima_categoria=prima_categoria
    )


@app.route("/api/statistiche/")
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def api_statistiche():
    # Endpoint JSON per alimentare grafici e widget.
    return jsonify(costruisci_dati_statistiche())


@app.route("/amministrazione/esporta_statistiche")
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def esporta_statistiche():
    # Genera un PDF con riepilogo e dettaglio ordini.
    dati_statistiche = costruisci_dati_statistiche()
    generato_il = datetime.now()

    # Inizializza PDF e layout base.
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_compression(False)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Intestazione documento.
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Byte-Bite - Report Statistiche", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    # Data/ora generazione.
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Generato il: {generato_il.strftime('%Y-%m-%d %H:%M:%S')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(4)

    # Riepilogo totali.
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

    def stampa_tabella(titolo, headers, righe, col_widths):
        # Stampa una tabella semplice con intestazioni e righe.
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, titolo, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("Helvetica", "B", 10)
        for header, w in zip(headers, col_widths):
            pdf.cell(w, 7, str(header), border=1)
        pdf.ln()

        pdf.set_font("Helvetica", "", 10)
        for riga in righe:
            for value, w in zip(riga, col_widths):
                testo = str(value)
                if len(testo) > 48:
                    testo = testo[:45] + "..."
                pdf.cell(w, 7, testo, border=1)
            pdf.ln()
        pdf.ln(6)

    categorie = dati_statistiche.get("categorie", [])
    righe_categorie = [(c.get("categoria_dashboard", ""), c.get("totale", 0)) for c in categorie]
    if righe_categorie:
        # Tabella: quantità vendute per categoria.
        stampa_tabella(
            "Ordini per categoria",
            ["Categoria", "Totale"],
            righe_categorie,
            [120, 40]
        )

    ore = dati_statistiche.get("ore", [])
    righe_ore = [(o.get("ora", ""), o.get("totale", 0)) for o in ore]
    if righe_ore:
        # Tabella: numero ordini per ora (0-23).
        stampa_tabella(
            "Andamento ordini per ora",
            ["Ora", "Totale"],
            righe_ore,
            [40, 40]
        )

    top10 = dati_statistiche.get("top10", [])
    righe_top10 = [(p.get("nome", ""), p.get("venduti", 0)) for p in top10]
    if righe_top10:
        # Tabella: top 10 prodotti per venduti.
        stampa_tabella(
            "Prodotti piu venduti (Top 10)",
            ["Prodotto", "Venduti"],
            righe_top10,
            [120, 40]
        )

    ordini = esegui_query("""
        SELECT o.id, o.nome_cliente, o.numero_tavolo, o.numero_persone, o.asporto, o.data_ordine, o.metodo_pagamento, o.completato
        FROM ordini o
        ORDER BY o.data_ordine DESC
    """)

    if ordini:
        # Sezione dettaglio: una pagina dedicata con i singoli ordini.
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 9, "Dettaglio ordini", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

        def tronca_testo(testo, max_len):
            # Evita celle troppo lunghe nel PDF.
            testo = str(testo)
            return testo if len(testo) <= max_len else (testo[: max_len - 3] + "...")

        for ordine in ordini:
            # Per ogni ordine, carica le righe prodotto e stampa un blocco.
            id_ordine = ordine["id"]
            righe_prodotti = esegui_query(
                """
                SELECT
                    p.nome,
                    p.categoria_menu,
                    op.quantita,
                    p.prezzo,
                    (p.prezzo * op.quantita) as subtotale,
                    op.stato
                FROM ordini_prodotti op
                JOIN prodotti p ON p.id = op.prodotto_id
                WHERE op.ordine_id = %s
                ORDER BY p.categoria_menu, p.nome
                """,
                (id_ordine,)
            )

            # Calcola il totale dell'ordine per stampare un riepilogo.
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
            # Riga compatta con metadati ordine.
            pdf.cell(
                0,
                6,
                f"Tipo: {tipo} | Tavolo: {tavolo} | Persone: {persone} | Pagamento: {ordine['metodo_pagamento']} | Completato: {completato}",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT
            )
            pdf.cell(0, 6, f"Totale ordine (EUR): {float(totale_ordine):.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)

            if righe_prodotti:
                # Intestazioni tabella righe ordine.
                headers = ["Prodotto", "Qta", "Prezzo", "Subtot.", "Stato"]
                widths = [80, 15, 20, 20, 35]

                pdf.set_font("Helvetica", "B", 10)
                for header, w in zip(headers, widths):
                    pdf.cell(w, 7, header, border=1)
                pdf.ln()

                pdf.set_font("Helvetica", "", 10)
                for riga in righe_prodotti:
                    # Unisce categoria e nome per compattezza.
                    nome_prodotto = f"{riga['categoria_menu']} - {riga['nome']}"
                    valori = [
                        tronca_testo(nome_prodotto, 44),
                        riga["quantita"],
                        f"{float(riga['prezzo']):.2f}",
                        f"{float(riga['subtotale'] or 0):.2f}",
                        tronca_testo(riga["stato"], 18)
                    ]
                    for val, w in zip(valori, widths):
                        pdf.cell(w, 7, str(val), border=1)
                    pdf.ln()

            pdf.ln(6)

    pdf_bytes = bytes(pdf.output())
    filename = f"statistiche_{generato_il.strftime('%Y%m%d_%H%M%S')}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(pdf_bytes, mimetype="application/pdf", headers=headers)


# ==================== API: prodotti ====================

@app.route("/api/aggiungi_prodotto", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def aggiungi_prodotto():
    dati = request.get_json()

    try:
        # Legge e normalizza i campi in ingresso.
        nome = dati.get("nome")
        categoria_dashboard = dati.get("categoria_dashboard")
        categoria_menu = dati.get("categoria_menu")
        prezzo = float(dati.get("prezzo", 0))
        quantita = int(dati.get("quantita", 0))
        disponibile = bool(dati.get("disponibile"))

        # Validazione minima dei campi obbligatori.
        if not nome or not categoria_dashboard or not categoria_menu:
            logger.warning("Tentativo di aggiunta prodotto con dati mancanti - utente: '%s'", session.get("username"))
            return jsonify({"errore": "Dati mancanti"}), 400

        if quantita > 0:
            # Se c'è stock, il prodotto deve risultare disponibile.
            disponibile = True

        # Inserisce il prodotto con venduti iniziali a 0.
        esegui_query(
            """
            INSERT INTO prodotti (nome, categoria_dashboard, categoria_menu, prezzo, quantita, disponibile, venduti)
            VALUES (%s, %s, %s, %s, %s, %s, 0)
            """,
            (nome, categoria_dashboard, categoria_menu, prezzo, quantita, disponibile),
            commit=True,
        )

        logger.info("Prodotto aggiunto: '%s' (€%.2f, categoria: %s/%s, quantita: %s) - utente: '%s'",
                    nome, prezzo, categoria_menu, categoria_dashboard, quantita, session.get("username"))

        # Aggiorna statistiche dopo modifica catalogo.
        socketio.start_background_task(ricalcola_statistiche)

        return jsonify({"messaggio": "Prodotto aggiunto con successo"})
    except Exception as e:
        logger.error("Errore durante l'aggiunta del prodotto - utente: '%s': %s", session.get("username"), e)
        return jsonify({"errore": "Errore durante l'aggiunta"}), 500


@app.route("/api/modifica_prodotto", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def modifica_prodotto():
    dati = request.get_json()

    try:
        # Converte quantità e calcola disponibile in modo automatico.
        quantita = int(dati["quantita"])
        prezzo = float(dati["prezzo"])
        disponibile = quantita > 0

        # Aggiorna nome, categoria, prezzo e stock.
        esegui_query(
            """
            UPDATE prodotti
            SET nome = %s, categoria_dashboard = %s, prezzo = %s, quantita = %s, disponibile = %s
            WHERE id = %s
            """,
            (
                dati["nome"],
                dati["categoria_dashboard"],
                prezzo,
                quantita,
                disponibile,
                dati["id"],
            ),
            commit=True,
        )

        logger.info("Prodotto #%s modificato: '%s' (€%.2f, quantita: %s) - utente: '%s'",
                    dati["id"], dati["nome"], prezzo, quantita, session.get("username"))

        # Aggiorna statistiche dopo variazione stock.
        socketio.start_background_task(ricalcola_statistiche)

        return jsonify({"messaggio": "Prodotto modificato con successo"})
    except Exception as e:
        logger.error("Errore durante la modifica del prodotto #%s - utente: '%s': %s",
                     dati.get("id"), session.get("username"), e)
        return jsonify({"errore": "Errore durante la modifica"}), 500


@app.route("/api/rifornisci_prodotto", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def rifornisci_prodotto():
    dati = request.get_json()
    id_prodotto = dati.get("id")
    try:
        # Converte quantità in int e valida.
        quantita = int(dati.get("quantita"))
    except (ValueError, TypeError):
        return jsonify({"errore": "Quantità non valida"}), 400

    if not id_prodotto or quantita <= 0:
        logger.warning("Rifornimento prodotto con dati non validi - utente: '%s'", session.get("username"))
        return jsonify({"errore": "Dati mancanti o non validi"}), 400

    # Aumenta lo stock.
    esegui_query(
        "UPDATE prodotti SET quantita = quantita + %s WHERE id = %s",
        (quantita, id_prodotto),
        commit=True,
    )

    # Se lo stock torna > 0, forza disponibile.
    esegui_query(
        "UPDATE prodotti SET disponibile = TRUE WHERE id = %s AND quantita > 0",
        (id_prodotto,),
        commit=True,
    )

    logger.info("Prodotto #%s rifornito di %s unità - utente: '%s'", id_prodotto, quantita, session.get("username"))

    socketio.start_background_task(ricalcola_statistiche)

    return jsonify({"messaggio": "Prodotto rifornito con successo"})


@app.route("/api/elimina_prodotto", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def elimina_prodotto():
    dati = request.get_json()

    try:
        # Eliminazione diretta per id.
        esegui_query("DELETE FROM prodotti WHERE id = %s", (dati["id"],), commit=True)

        logger.info("Prodotto #%s eliminato - utente: '%s'", dati["id"], session.get("username"))

        # Aggiorna statistiche dopo modifica catalogo.
        socketio.start_background_task(ricalcola_statistiche)

        return jsonify({"messaggio": "Prodotto eliminato con successo"})
    except Exception as e:
        logger.error("Errore durante l'eliminazione del prodotto #%s - utente: '%s': %s",
                     dati.get("id"), session.get("username"), e)
        return jsonify({"errore": "Errore durante l'eliminazione"}), 500


# ==================== API: ordini ====================

@app.route("/api/modifica_ordine", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def modifica_ordine():
    dati = request.get_json()
    id_ordine = dati.get("id_ordine")

    if not id_ordine:
        return jsonify({"errore": "ID ordine mancante"}), 400

    try:
        # Legge campi modificabili dall'interfaccia admin.
        nome_cliente = dati.get("nome_cliente")
        numero_tavolo = dati.get("numero_tavolo")
        numero_persone = dati.get("numero_persone")
        metodo_pagamento = dati.get("metodo_pagamento")

        # Converte stringhe vuote in NULL (campi opzionali).
        if numero_tavolo == "":
            numero_tavolo = None
        if numero_persone == "":
            numero_persone = None

        # Aggiorna intestazione ordine.
        esegui_query(
            """
            UPDATE ordini
            SET nome_cliente = %s, numero_tavolo = %s, numero_persone = %s, metodo_pagamento = %s
            WHERE id = %s
            """,
            (nome_cliente, numero_tavolo, numero_persone, metodo_pagamento, id_ordine),
            commit=True,
        )

        logger.info("Ordine #%s aggiornato - cliente: '%s', utente: '%s'",
                    id_ordine, nome_cliente, session.get("username"))

        # Aggiorna statistiche dopo modifica ordine.
        socketio.start_background_task(ricalcola_statistiche)

        return jsonify({"messaggio": "Ordine aggiornato con successo"})
    except Exception as e:
        logger.error("Errore durante l'aggiornamento dell'ordine #%s - utente: '%s': %s",
                     id_ordine, session.get("username"), e)
        return jsonify({"errore": "Errore durante l'aggiornamento"}), 500


@app.route("/api/elimina_ordine", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def elimina_ordine():
    dati = request.get_json()
    id_ordine = dati.get("id")

    if not id_ordine:
        return jsonify({"errore": "ID ordine mancante"}), 400

    try:
        # Transazione esplicita: ripristino stock + delete righe + delete ordine.
        with ottieni_db() as connessione:
            cursore = connessione.cursor()

            # Recupera le righe dell'ordine per ricostruire le quantità.
            cursore.execute(
                """
                SELECT prodotto_id, quantita
                FROM ordini_prodotti
                WHERE ordine_id = %s
                """,
                (id_ordine,),
            )
            prodotti_ordine = cursore.fetchall()

            for prodotto in prodotti_ordine:
                # Ripristina magazzino e riduce venduti per ogni prodotto.
                prodotto_id = prodotto["prodotto_id"]
                quantita = prodotto["quantita"]

                cursore.execute(
                    """
                    UPDATE prodotti
                    SET quantita = quantita + %s, venduti = venduti - %s
                    WHERE id = %s
                    """,
                    (quantita, quantita, prodotto_id),
                )

                # Se torna disponibile, la UI può renderlo selezionabile.
                cursore.execute(
                    """
                    UPDATE prodotti
                    SET disponibile = TRUE
                    WHERE id = %s AND quantita > 0
                    """,
                    (prodotto_id,),
                )

            # Rimuove prima le righe e poi l'intestazione ordine.
            cursore.execute("DELETE FROM ordini_prodotti WHERE ordine_id = %s", (id_ordine,))
            cursore.execute("DELETE FROM ordini WHERE id = %s", (id_ordine,))
            connessione.commit()

        logger.info("Ordine #%s eliminato con ripristino magazzino - utente: '%s'",
                    id_ordine, session.get("username"))

        # Aggiorna statistiche dopo eliminazione.
        socketio.start_background_task(ricalcola_statistiche)

        return jsonify({"messaggio": "Ordine eliminato con successo"})
    except Exception as e:
        logger.error("Errore durante l'eliminazione dell'ordine #%s - utente: '%s': %s",
                     id_ordine, session.get("username"), e)
        return jsonify({"errore": "Errore durante l'eliminazione"}), 500


@app.route("/api/ordine/<int:id_ordine>/dettagli")
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def ordine_dettagli(id_ordine):
    dettagli = esegui_query(
        """
        SELECT
            p.nome,
            p.categoria_menu,
            op.quantita,
            p.prezzo,
            (p.prezzo * op.quantita) as subtotale,
            op.stato
        FROM ordini_prodotti op
        JOIN prodotti p ON op.prodotto_id = p.id
        WHERE op.ordine_id = %s
        """,
        (id_ordine,),
    )

    totale = sum((riga["subtotale"] or 0) for riga in dettagli)
    return render_template(
        "partials/_ordine_dettagli.html",
        dettagli=dettagli,
        totale=totale,
        ordine_id=id_ordine,
    )


@app.route("/api/ordine/<int:id_ordine>")
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def api_ordine(id_ordine):
    intestazione = esegui_query(
        """
        SELECT id, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento, data_ordine
        FROM ordini
        WHERE id = %s
        """,
        (id_ordine,),
        uno=True,
    )
    if not intestazione:
        abort(404)

    righe_articoli = esegui_query(
        """
        SELECT p.nome AS nome, op.quantita AS quantita, p.prezzo AS prezzo
        FROM ordini_prodotti op
        JOIN prodotti p ON p.id = op.prodotto_id
        WHERE op.ordine_id = %s
        """,
        (id_ordine,),
    )
    articoli = [{"nome": riga["nome"], "quantita": riga["quantita"], "prezzo": riga["prezzo"]} for riga in righe_articoli]
    return jsonify(
        {
            "id": intestazione["id"],
            "nome_cliente": intestazione["nome_cliente"],
            "numero_tavolo": intestazione["numero_tavolo"],
            "numero_persone": intestazione["numero_persone"],
            "metodo_pagamento": intestazione["metodo_pagamento"],
            "data_ordine": intestazione["data_ordine"],
            "items": articoli,
        }
    )


# ==================== API: utenti ====================

@app.route("/api/aggiungi_utente", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def aggiungi_utente():
    # Crea un utente e salva i permessi selezionati.
    dati = request.get_json()

    # Campi base utente.
    username = dati.get("username")
    password = dati.get("password")
    is_admin = bool(dati.get("is_admin"))
    attivo = bool(dati.get("attivo"))
    permessi = dati.get("permessi", [])

    if not username or not password:
        return jsonify({"errore": "Username e password obbligatori"}), 400

    permessi = _normalizza_permessi(permessi)

    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()

            # Evita duplicati username.
            cursore.execute("SELECT id FROM utenti WHERE username = %s", (username,))
            if cursore.fetchone():
                logger.warning("Tentativo di creare utente con username già in uso: '%s' - operatore: '%s'",
                               username, session.get("username"))
                return jsonify({"errore": "Username già in uso"}), 400

            # Genera hash password (rounds bassi per ambienti limitati).
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()

            # Inserisce utente.
            cursore.execute("""
                INSERT INTO utenti (username, password_hash, is_admin, attivo)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (username, password_hash, is_admin, attivo))

            id_utente = cursore.fetchone()["id"]

            # Inserisce permessi associati.
            for pagina in permessi:
                cursore.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)", (id_utente, pagina))

            connessione.commit()

        logger.info("Nuovo utente creato: '%s' (ID: %s, admin: %s, permessi: %s) - operatore: '%s'",
                    username, id_utente, is_admin, permessi, session.get("username"))

        return jsonify({"messaggio": "Utente creato con successo"})
    except Exception as e:
        logger.error("Errore durante la creazione dell'utente '%s' - operatore: '%s': %s",
                     username, session.get("username"), e)
        return jsonify({"errore": "Errore durante la creazione"}), 500


@app.route("/api/modifica_utente", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def modifica_utente():
    # Aggiorna dati utente e sostituisce la lista permessi.
    dati = request.get_json()
    id_utente = dati.get("id_utente")

    if not id_utente:
        return jsonify({"errore": "ID utente mancante"}), 400

    try:
        # Legge campi aggiornabili.
        username = dati.get("username")
        password = dati.get("password")
        is_admin = bool(dati.get("is_admin"))
        attivo = bool(dati.get("attivo"))
        permessi = dati.get("permessi", [])

        permessi = _normalizza_permessi(permessi)

        with ottieni_db() as connessione:
            cursore = connessione.cursor()

            if password:
                # Se presente, aggiorna anche la password.
                password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
                cursore.execute("""
                    UPDATE utenti
                    SET username = %s, password_hash = %s, is_admin = %s, attivo = %s
                    WHERE id = %s
                """, (username, password_hash, is_admin, attivo, id_utente))
            else:
                cursore.execute("""
                    UPDATE utenti
                    SET username = %s, is_admin = %s, attivo = %s
                    WHERE id = %s
                """, (username, is_admin, attivo, id_utente))

            # Sostituisce l'insieme permessi.
            cursore.execute("DELETE FROM permessi_pagine WHERE utente_id = %s", (id_utente,))

            for pagina in permessi:
                cursore.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)", (id_utente, pagina))

            connessione.commit()

        logger.info("Utente #%s modificato: '%s' (admin: %s, attivo: %s) - operatore: '%s'",
                    id_utente, username, is_admin, attivo, session.get("username"))

        return jsonify({"messaggio": "Utente modificato con successo"})
    except Exception as e:
        logger.error("Errore durante la modifica dell'utente #%s - operatore: '%s': %s",
                     id_utente, session.get("username"), e)
        return jsonify({"errore": "Errore durante la modifica"}), 500


@app.route("/api/elimina_utente", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def elimina_utente():
    # Elimina un utente e i relativi permessi.
    dati = request.get_json()
    id_utente = dati.get("id_utente")

    if not id_utente:
        return jsonify({"errore": "ID utente mancante"}), 400

    # Protegge da cancellazione dell'utente corrente.
    if str(session.get("id_utente")) == str(id_utente):
        logger.warning("Tentativo di eliminare il proprio account (ID: %s) - utente: '%s'",
                       id_utente, session.get("username"))
        return jsonify({"errore": "Non puoi eliminare il tuo stesso account"}), 400

    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()

            # Verifica che l'utente esista.
            cursore.execute("SELECT id, username FROM utenti WHERE id = %s", (id_utente,))
            riga = cursore.fetchone()
            if not riga:
                logger.warning("Eliminazione utente fallita - ID #%s non trovato - operatore: '%s'",
                               id_utente, session.get("username"))
                return jsonify({"errore": "Utente non trovato"}), 404

            username_eliminato = riga["username"]

            # Elimina permessi e poi utente.
            cursore.execute("DELETE FROM permessi_pagine WHERE utente_id = %s", (id_utente,))
            cursore.execute("DELETE FROM utenti WHERE id = %s", (id_utente,))

            connessione.commit()

        logger.info("Utente #%s ('%s') eliminato - operatore: '%s'",
                    id_utente, username_eliminato, session.get("username"))

        return jsonify({"messaggio": "Utente eliminato con successo"})
    except Exception as e:
        logger.error("Errore durante l'eliminazione dell'utente #%s - operatore: '%s': %s",
                     id_utente, session.get("username"), e)
        return jsonify({"errore": "Errore durante l'eliminazione"}), 500


# ==================== API: frammenti HTML amministrazione ====================

@app.route("/api/amministrazione/ordini_html")
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def api_amministrazione_ordini_html():
    # Ritorna le righe HTML della tabella ordini (refresh parziale).
    # Query identica a quella della pagina admin, senza layout completo.
    ordini = esegui_query("""
        SELECT o.id, o.nome_cliente, o.numero_tavolo, o.numero_persone, o.data_ordine, o.metodo_pagamento,
               COALESCE(SUM(p.prezzo * op.quantita), 0) as totale
        FROM ordini o
        LEFT JOIN ordini_prodotti op ON o.id = op.ordine_id
        LEFT JOIN prodotti p ON op.prodotto_id = p.id
        GROUP BY o.id
        ORDER BY o.data_ordine DESC
    """)
    return render_template("partials/_amministrazione_ordini_rows.html", ordini=ordini)


@app.route("/api/amministrazione/prodotti_html")
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def api_amministrazione_prodotti_html():
    # Ritorna le righe HTML della tabella prodotti (refresh parziale).
    # Query identica a quella della pagina admin, ordinata per categoria.
    prodotti = esegui_query("""
        SELECT
            id,
            nome,
            categoria_dashboard,
            categoria_menu,
            prezzo,
            disponibile,
            quantita,
            venduti
        FROM prodotti
        ORDER BY MIN(id) OVER (PARTITION BY categoria_menu), id;
    """)

    # Calcola la prima categoria per inizializzare il pannello UI.
    categorie_db = esegui_query("SELECT categoria_menu FROM prodotti GROUP BY categoria_menu ORDER BY MIN(id)")
    categorie = [riga["categoria_menu"] for riga in categorie_db]
    prima_categoria = categorie[0] if categorie else None

    return render_template(
        "partials/_amministrazione_prodotti_rows.html",
        prodotti=prodotti,
        prima_categoria=prima_categoria,
    )


