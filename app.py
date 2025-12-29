from flask import Flask, json, jsonify, redirect, render_template, request, session, abort, url_for, Response
import sqlite3 as sq
import socket
import bcrypt
import secrets
import os
from dotenv import load_dotenv
from flask_socketio import SocketIO, join_room
import uuid
from functools import wraps
import contextlib
from datetime import datetime
from fpdf import FPDF, XPos, YPos

load_dotenv()

# Dizionario per tracciare i timer attivi per gli ordini
timer_attivi = {}

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

with app.app_context():
    try:
        with sq.connect('db.sqlite3', timeout=30) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
    except Exception as e:
        print(f"Attenzione: Impossibile abilitare WAL mode: {e}")

@app.errorhandler(403)
def forbidden_error(error):
    return "403 Forbidden", 403

socketio = SocketIO(app, async_mode='gevent', cors_allowed_origins="*", logger=False, engineio_logger=False)

# --- UTILITY DATABASE ---

@contextlib.contextmanager
def ottieni_db():
    """Stabilisce una connessione al database e la chiude automaticamente."""
    connessione = sq.connect('db.sqlite3', timeout=30)
    connessione.row_factory = sq.Row
    try:
        yield connessione
    finally:
        connessione.close()

def esegui_query(query, argomenti=(), uno=False, commit=False):
    """Esegue una query SQL e gestisce la connessione."""
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute(query, argomenti)
        righe = None
        if not commit:
            righe = cursore.fetchall()
        if commit:
            connessione.commit()
    return (righe[0] if righe else None) if uno else (righe or [])

# --- UTILITY AUTENTICAZIONE ---

def ottieni_utente_loggato():
    """Recupera i dati dell'utente attualmente loggato dalla sessione (cache) o dal DB."""
    id_utente = session.get("id_utente")
    if not id_utente:
        return None

    # CACHE IN SESSIONE: Se abbiamo già i dati utente validi in sessione, usali!
    # Questo evita una query al DB per ogni singola richiesta HTTP.
    if session.get("user_cache_id") == id_utente:
        return {
            "id": session["user_cache_id"],
            "username": session["user_cache_username"],
            "is_admin": session["user_cache_is_admin"],
            "attivo": session["user_cache_attivo"]
        }

    # Se non sono in cache (primo accesso o sessione scaduta), leggili dal DB
    utente = esegui_query(
        "SELECT id, username, is_admin, attivo FROM utenti WHERE id = ?",
        (id_utente,),
        uno=True
    )

    # Aggiorna la cache in sessione
    if utente:
        session["user_cache_id"] = utente["id"]
        session["user_cache_username"] = utente["username"]
        session["user_cache_is_admin"] = utente["is_admin"]
        session["user_cache_attivo"] = utente["attivo"]

    return utente

def accesso_richiesto(f):
    """Decoratore per richiedere il login per accedere a una route."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "id_utente" not in session:
            return redirect(url_for('accesso'))
        return f(*args, **kwargs)
    return wrapper

def richiedi_permesso(pagina):
    """Decoratore per verificare i permessi di accesso a una pagina specifica."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Utente NON loggato
            if "id_utente" not in session:
                return redirect(url_for('accesso'))

            utente = ottieni_utente_loggato()

            # Utente disattivo → espellilo
            if not utente or utente["attivo"] != 1:
                session.clear()
                return redirect(url_for('accesso'))

            # Admin → ha accesso totale
            if utente["is_admin"] == 1:
                return f(*args, **kwargs)

            # Controlla se ha il permesso richiesto
            permesso = esegui_query("""
                SELECT 1 FROM permessi_pagine
                WHERE utente_id = ? AND pagina = ?
            """, (utente["id"], pagina), uno=True)

            if permesso:
                return f(*args, **kwargs)

            # Altrimenti → accesso negato
            abort(403)

        return wrapper
    return decorator

# --- UTILITY SOCKETIO ---

def emissione_sicura(evento, dati, stanza=None):
    """Invia un messaggio SocketIO gestendo eventuali errori."""
    try:
        socketio.emit(evento, dati, room=stanza)
        if stanza and stanza != 'amministrazione' and evento == 'aggiorna_dashboard':
            socketio.emit(evento, dati, room='amministrazione')
    except Exception as e:
        app.logger.warning(f"[SocketIO] Errore durante emissione: {e}")

@socketio.on('join')
def gestisci_join(dati):
    """Gestisce l'ingresso di un client in una stanza SocketIO."""
    categoria = dati.get('categoria')
    if categoria:
        # Es: "Cucina", "Bar", "Griglia"...
        join_room(categoria)
        print(f"[WS] Dashboard entrata nella stanza: {categoria}")

# --- LOGICA DI BUSINESS ---

def ottieni_ordini_per_categoria(categoria):
    """Recupera gli ordini (completati e non) per una specifica categoria."""
    categoria = categoria.capitalize()
    
    ordini_db = esegui_query("""
        SELECT 
            o.id AS ordine_id,
            o.nome_cliente,
            o.numero_tavolo,
            o.numero_persone,
            o.data_ordine,
            op.stato,
            p.nome AS prodotto_nome,
            op.quantita
        FROM ordini AS o
        JOIN ordini_prodotti AS op ON o.id = op.ordine_id
        JOIN prodotti AS p ON p.id = op.prodotto_id
        WHERE p.categoria_dashboard = ?
        ORDER BY o.data_ordine ASC;
    """, (categoria,))

    # Raggruppa per ordine
    ordini = {}
    for riga in ordini_db:
        oid = riga["ordine_id"]
        ordini.setdefault(oid, {
            "id": oid,
            "nome_cliente": riga["nome_cliente"],
            "numero_tavolo": riga["numero_tavolo"],
            "numero_persone": riga["numero_persone"],
            "data_ordine": riga["data_ordine"],
            "stato": riga["stato"],
            "prodotti": []
        })["prodotti"].append({
            "nome": riga["prodotto_nome"],
            "quantita": riga["quantita"]
        })

    # Divide ordini completati e non completati
    ordini_non_completati = []
    ordini_completati = []

    for ordine in ordini.values():
        if ordine["stato"] == "Completato":
            ordini_completati.append(ordine)
        else:
            ordini_non_completati.append(ordine)

    # Ordina i completati dal più recente
    ordini_completati.sort(key=lambda o: o["data_ordine"], reverse=True)

    return ordini_non_completati, ordini_completati

def ricalcola_statistiche():
    """Ricalcola tutte le statistiche e le salva nel database."""
    
    # 1. Calcola Totali Generali
    stats_totali = esegui_query("""
        SELECT
            (SELECT COUNT(*) FROM ordini) as ordini_totali,
            (SELECT COUNT(*) FROM ordini WHERE completato = 1) as ordini_completati,
            COALESCE(SUM(p.prezzo * op.quantita), 0) as totale_incasso,
            COALESCE(SUM(CASE WHEN o.metodo_pagamento = 'Contanti' THEN p.prezzo * op.quantita ELSE 0 END), 0) as totale_contanti,
            COALESCE(SUM(CASE WHEN o.metodo_pagamento != 'Contanti' THEN p.prezzo * op.quantita ELSE 0 END), 0) as totale_carta
        FROM ordini o
        JOIN ordini_prodotti op ON o.id = op.ordine_id
        JOIN prodotti p ON op.prodotto_id = p.id
    """, uno=True)

    # 2. Calcola Totali per Categoria
    stats_categorie = esegui_query("""
        SELECT p.categoria_dashboard, SUM(op.quantita) as totale
        FROM ordini_prodotti op
        JOIN prodotti p ON op.prodotto_id = p.id
        GROUP BY p.categoria_dashboard
    """)

    # 3. Calcola Totali per Ora
    stats_ore = esegui_query("""
        SELECT CAST(strftime('%H', data_ordine) AS INT) as ora, COUNT(*) as totale
        FROM ordini
        GROUP BY ora
    """)

    # --- AGGIORNAMENTO DB ---
    with ottieni_db() as conn:
        cursor = conn.cursor()
        
        # Reset tabelle
        cursor.execute("DELETE FROM statistiche_totali")
        cursor.execute("DELETE FROM statistiche_categorie")
        cursor.execute("DELETE FROM statistiche_ore")

        # Inserisci totali
        cursor.execute("""
            INSERT INTO statistiche_totali 
            (id, ordini_totali, ordini_completati, totale_incasso, totale_contanti, totale_carta)
            VALUES (1, ?, ?, ?, ?, ?)
        """, (
            stats_totali["ordini_totali"] or 0,
            stats_totali["ordini_completati"] or 0,
            stats_totali["totale_incasso"],
            stats_totali["totale_contanti"],
            stats_totali["totale_carta"]
        ))

        # Inserisci categorie (Bar, Cucina, Griglia, Gnoccheria)
        categorie_fisse = ["Bar", "Cucina", "Griglia", "Gnoccheria"]
        dati_cat = {row["categoria_dashboard"]: row["totale"] for row in stats_categorie}
        
        for cat in categorie_fisse:
            valore = dati_cat.get(cat, 0)
            cursor.execute("INSERT INTO statistiche_categorie (categoria_dashboard, totale) VALUES (?, ?)", (cat, valore))

        # Inserisci ore (0-23)
        dati_ore = {row["ora"]: row["totale"] for row in stats_ore}
        for h in range(24):
            valore = dati_ore.get(h, 0)
            cursor.execute("INSERT INTO statistiche_ore (ora, totale) VALUES (?, ?)", (h, valore))
            
        conn.commit()
    
    # Notifica aggiornamento globale
    emissione_sicura('aggiorna_dashboard', {})

def cambia_stato_automatico(ordine_id, categoria, timer_id):
    """Gestisce il passaggio automatico allo stato 'Completato' dopo un timeout."""
    chiave_timer = (ordine_id, categoria)
    
    for i in range(10):
        socketio.sleep(1)
        # Se è stato richiesto di annullare, interrompi
        if (
            chiave_timer not in timer_attivi
            or timer_attivi[chiave_timer]["id"] != timer_id
            or timer_attivi[chiave_timer]["annulla"]
        ):
            return

    # Controlla che non sia stato annullato nel frattempo
    if chiave_timer not in timer_attivi or timer_attivi[chiave_timer]["annulla"]:
        return

    # Aggiorna stato a completato
    esegui_query("""
        UPDATE ordini_prodotti
        SET stato = 'Completato'
        WHERE ordine_id = ?
        AND prodotto_id IN (
            SELECT id FROM prodotti WHERE categoria_dashboard = ?
        );
    """, (ordine_id, categoria), commit=True)

    residui = esegui_query(
        "SELECT COUNT(*) AS c FROM ordini_prodotti WHERE ordine_id = ? AND stato != 'Completato'",
        (ordine_id,),
        uno=True
    )["c"]
    esegui_query(
        "UPDATE ordini SET completato = ? WHERE id = ?",
        (1 if residui == 0 else 0, ordine_id),
        commit=True
    )

    # Rimuovi il timer dalla lista
    timer_attivi.pop(chiave_timer, None)

    emissione_sicura('aggiorna_dashboard', {'categoria': categoria}, stanza=categoria)
    socketio.start_background_task(ricalcola_statistiche)

# --- ROUTES: AUTENTICAZIONE ---

@app.route('/login/', methods=['GET', 'POST'])
def accesso():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password").encode()

        utente = esegui_query("""
            SELECT id, username, password_hash, is_admin, attivo
            FROM utenti WHERE username = ?
        """, (username,), uno=True)

        if not utente:
            return render_template("login.html", error="Username o password errata")

        if utente["attivo"] != 1:
            return render_template("login.html", error="Account disattivato")

        # Verifica password
        if not bcrypt.checkpw(password, utente["password_hash"].encode()):
            return render_template("login.html", error="Username o password errata")

        # Login riuscito
        session["id_utente"] = utente["id"]
        session["username"] = utente["username"]

        return redirect(url_for('home'))

    return render_template("login.html")

# --- ROUTES: GENERALI ---

@app.route('/')
def home():
    return render_template('index.html')

# --- ROUTES: CASSA ---

@app.route('/cassa/')
@accesso_richiesto
@richiedi_permesso("CASSA")
def cassa():
    # Ottimizzazione: Recupera tutti i prodotti in un'unica query invece di N+1 query
    # L'ordinamento per ID garantisce che l'ordine delle categorie rispetti la logica originale (MIN(id))
    tutti_prodotti = esegui_query('SELECT * FROM prodotti ORDER BY id')
    
    categorie = []
    prodotti_per_categoria = {}
    
    for p in tutti_prodotti:
        cat = p['categoria_menu']
        if cat not in prodotti_per_categoria:
            categorie.append(cat)
            prodotti_per_categoria[cat] = []
        prodotti_per_categoria[cat].append(p)

    return render_template(
        'cassa.html',
        categorie=categorie,
        prodotti_per_categoria=prodotti_per_categoria
    )

@app.route('/aggiungi_ordine/', methods=['POST'])
def aggiungi_ordine():
    # Recupera i dati dal form
    asporto = 1 if request.form.get('isTakeaway') == 'on' else 0
    nome_cliente = request.form.get('nome_cliente')
    numero_tavolo = request.form.get('numero_tavolo')
    numero_persone = request.form.get('numero_persone')
    metodo_pagamento = request.form.get('metodo_pagamento')
    prodotti_json = request.form.get('prodotti')

    if asporto:
        numero_tavolo = None
        numero_persone = None

    # Converte la stringa JSON in una lista di dizionari
    try:
        prodotti = json.loads(prodotti_json) if prodotti_json else []
    except json.JSONDecodeError:
        prodotti = []

    if not prodotti:
        return redirect(url_for('cassa') + '?error=Nessun prodotto selezionato', code=303)

    # Inserisce il nuovo ordine
    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()
            cursore.execute("""
                INSERT INTO ordini (asporto, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento)
                VALUES (?, ?, ?, ?, ?)
            """, (asporto, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento))
            id_ordine = cursore.lastrowid  # ID dell'ordine appena creato

            # Inserisci i prodotti e aggiorna il magazzino
            for p in prodotti:
                # 1. Tenta di scalare la quantità (Atomico)
                cursore.execute("""
                    UPDATE prodotti
                    SET quantita = quantita - ?, venduti = venduti + ?
                    WHERE id = ? AND quantita >= ?
                """, (p["quantita"], p["quantita"], p["id"], p["quantita"]))

                if cursore.rowcount == 0:
                    # Rollback automatico uscendo dal contesto con eccezione
                    raise Exception(f"Prodotto {p.get('nome', 'Sconosciuto')} esaurito o insufficiente.")

                # 2. Se andato a buon fine, registra la riga ordine
                cursore.execute("""
                    INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)
                    VALUES (?, ?, ?, ?)
                """, (id_ordine, p["id"], p["quantita"], "In Attesa"))

            # Ottieni tutte le categorie dashboard coinvolte in questo ordine
            cursore.execute("""
                SELECT DISTINCT prodotti.categoria_dashboard
                FROM ordini_prodotti
                JOIN prodotti ON prodotti.id = ordini_prodotti.prodotto_id
                WHERE ordini_prodotti.ordine_id = ?
            """, (id_ordine,))
            categorie_dashboard = [riga[0] for riga in cursore.fetchall()]
            connessione.commit()

        # Avvisa le dashboard in tempo reale
        for cat in categorie_dashboard:
            emissione_sicura('aggiorna_dashboard', {'categoria': cat}, stanza=cat)
        socketio.start_background_task(ricalcola_statistiche)

        return redirect(url_for('cassa') + f'?last_order_id={id_ordine}', code=303)

    except Exception as e:
        print(f"[ERRORE ORDINE] {e}")
        # Redirect con errore (gestito idealmente dal frontend)
        return redirect(url_for('cassa') + f'?error={e}', code=303)

# --- ROUTES: DASHBOARD ---

@app.route('/dashboard/<category>/')
@accesso_richiesto
def dashboard(category):
    permesso = "DASHBOARD"

    richiedi_permesso(permesso)(lambda: None)()

    ordini_non_completati, ordini_completati = ottieni_ordini_per_categoria(category)
    return render_template(
        'dashboard.html',
        category=category.capitalize(),
        ordini_non_completati=ordini_non_completati,
        ordini_completati=ordini_completati
    )

@app.route('/dashboard/<category>/partial')
def dashboard_parziale(category):
    ordini_non_completati, ordini_completati = ottieni_ordini_per_categoria(category)

    html_non_completati = render_template(
        'partials/_ordini.html',
        ordini=ordini_non_completati,
        category=category
    )
    html_completati = render_template(
        'partials/_ordini.html',
        ordini=ordini_completati,
        category=category,
        completati=True
    )

    return jsonify({
        "html_non_completati": html_non_completati,
        "html_completati": html_completati
    })

@app.route('/cambia_stato/', methods=['POST'])
def cambia_stato():
    dati = request.get_json()
    id_ordine = dati.get('ordine_id')
    categoria = dati.get('categoria')

    # Leggi stato attuale
    riga_stato = esegui_query("""
        SELECT stato 
        FROM ordini_prodotti
        JOIN prodotti ON prodotti.id = ordini_prodotti.prodotto_id
        WHERE ordine_id = ? AND prodotti.categoria_dashboard = ?
        LIMIT 1;
    """, (id_ordine, categoria), uno=True)

    stato_attuale = riga_stato["stato"]

    # Calcola nuovo stato
    stati = ["In Attesa", "In Preparazione", "Pronto", "Completato"]

    chiave_timer = (id_ordine, categoria)

    if stato_attuale == "Pronto":
        # Se esiste un timer, annullalo
        if chiave_timer in timer_attivi:
            timer_attivi[chiave_timer]["annulla"] = True
            del timer_attivi[chiave_timer]
            print(f"[AUTO] Timer annullato per ordine {id_ordine} ({categoria})")

        nuovo_stato = "In Preparazione"

    # Altrimenti avanza di stato normalmente
    else:
        nuovo_stato = stati[stati.index(stato_attuale) + 1]

    # Aggiorna lo stato nel DB
    esegui_query("""
        UPDATE ordini_prodotti
        SET stato = ?
        WHERE ordine_id = ?
        AND prodotto_id IN (
            SELECT id FROM prodotti WHERE categoria_dashboard = ?
        );
    """, (nuovo_stato, id_ordine, categoria), commit=True)

    residui = esegui_query(
        "SELECT COUNT(*) AS c FROM ordini_prodotti WHERE ordine_id = ? AND stato != 'Completato'",
        (id_ordine,),
        uno=True
    )["c"]
    esegui_query(
        "UPDATE ordini SET completato = ? WHERE id = ?",
        (1 if residui == 0 else 0, id_ordine),
        commit=True
    )

    # Avvisa subito la dashboard
    emissione_sicura('aggiorna_dashboard', {'categoria': categoria}, stanza=categoria)
    socketio.start_background_task(ricalcola_statistiche)

    if nuovo_stato == "Pronto":
        # Invalida qualsiasi vecchio timer
        if chiave_timer in timer_attivi:
            timer_attivi[chiave_timer]["annulla"] = True
            timer_attivi.pop(chiave_timer, None)

        id_timer = str(uuid.uuid4())  # ID univoco per questo timer
        timer_attivi[chiave_timer] = {"annulla": False, "id": id_timer}
        socketio.start_background_task(cambia_stato_automatico, id_ordine, categoria, id_timer)
        print(f"[AUTO] Timer avviato per ordine {id_ordine} ({categoria}) → {id_timer}")

    # Ricarica ordini aggiornati per quella categoria
    ordini_non_completati, ordini_completati = ottieni_ordini_per_categoria(categoria)
    html_non_completati = render_template(
        'partials/_ordini.html', ordini=ordini_non_completati, category=categoria
    )
    html_completati = render_template(
        'partials/_ordini.html', ordini=ordini_completati, category=categoria, completati=True
    )

    return jsonify({
        "nuovo_stato": nuovo_stato,
        "html_non_completati": html_non_completati,
        "html_completati": html_completati
    })

# --- ROUTES: AMMINISTRAZIONE ---

@app.route('/amministrazione/')
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def amministrazione():
    ordini = esegui_query("""
        SELECT o.id, o.nome_cliente, o.numero_tavolo, o.numero_persone, o.data_ordine, o.metodo_pagamento,
               COALESCE(SUM(p.prezzo * op.quantita), 0) as totale
        FROM ordini o
        LEFT JOIN ordini_prodotti op ON o.id = op.ordine_id
        LEFT JOIN prodotti p ON op.prodotto_id = p.id
        GROUP BY o.id
        ORDER BY o.data_ordine DESC
    """)
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
        ORDER BY categoria_menu;
    """)

    categorie_db = esegui_query("SELECT DISTINCT categoria_menu FROM prodotti")
    categorie = [riga["categoria_menu"] for riga in categorie_db]
    prima_categoria = categorie[0] if categorie else None

    # Recupero utenti e permessi
    utenti_db = esegui_query("SELECT id, username, is_admin, attivo FROM utenti ORDER BY username")
    utenti = []
    for riga in utenti_db:
        u = dict(riga)
        permessi_db = esegui_query("SELECT pagina FROM permessi_pagine WHERE utente_id = ?", (u["id"],))
        u["permessi"] = [p["pagina"] for p in permessi_db]
        utenti.append(u)

    return render_template(
        "amministrazione.html",
        ordini=ordini,
        prodotti=prodotti,
        utenti=utenti,
        categorie=categorie,
        prima_categoria=prima_categoria
    )

@app.route('/api/statistiche/')
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def api_statistiche():
    return jsonify(costruisci_dati_statistiche())

def costruisci_dati_statistiche():
    ordini_totali = esegui_query("SELECT COUNT(*) AS c FROM ordini", uno=True)["c"]
    ordini_completati = esegui_query("SELECT COUNT(*) AS c FROM ordini WHERE completato = 1", uno=True)["c"]

    riga_totale_incasso = esegui_query(
        """
        SELECT SUM(p.prezzo * op.quantita) AS totale
        FROM ordini_prodotti op
        JOIN prodotti p ON p.id = op.prodotto_id
        """,
        uno=True
    )
    totale_incasso = riga_totale_incasso["totale"] or 0

    riga_totale_contanti = esegui_query(
        """
        SELECT SUM(p.prezzo * op.quantita) AS totale
        FROM ordini_prodotti op
        JOIN prodotti p ON p.id = op.prodotto_id
        JOIN ordini o ON o.id = op.ordine_id
        WHERE o.metodo_pagamento = 'Contanti'
        """,
        uno=True
    )
    totale_contanti = (riga_totale_contanti["totale"] or 0)

    riga_totale_carta = esegui_query(
        """
        SELECT SUM(p.prezzo * op.quantita) AS totale
        FROM ordini_prodotti op
        JOIN prodotti p ON p.id = op.prodotto_id
        JOIN ordini o ON o.id = op.ordine_id
        WHERE o.metodo_pagamento = 'Carta'
        """,
        uno=True
    )
    totale_carta = (riga_totale_carta["totale"] or 0)

    righe_ore = esegui_query(
        """
        SELECT CAST(strftime('%H', data_ordine) AS INT) AS ora, COUNT(*) AS totale
        FROM ordini
        GROUP BY ora
        ORDER BY ora ASC
        """
    )
    ore = [dict(r) for r in righe_ore] if righe_ore else []

    righe_cat = esegui_query(
        """
        SELECT p.categoria_dashboard, SUM(op.quantita) AS totale
        FROM ordini_prodotti op
        JOIN prodotti p ON p.id = op.prodotto_id
        GROUP BY p.categoria_dashboard
        """
    )
    categorie = [dict(r) for r in righe_cat] if righe_cat else []

    righe_top10 = esegui_query(
        """
        SELECT nome, venduti
        FROM prodotti
        ORDER BY venduti DESC
        LIMIT 10
        """
    )
    top10 = [dict(r) for r in righe_top10] if righe_top10 else []

    return {
        "totali": {
            "ordini_totali": ordini_totali,
            "ordini_completati": ordini_completati,
            "totale_incasso": totale_incasso,
            "totale_contanti": totale_contanti,
            "totale_carta": totale_carta
        },
        "categorie": categorie,
        "ore": ore,
        "top10": top10
    }

@app.route('/amministrazione/esporta_statistiche')
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

    def stampa_tabella(titolo, headers, righe, col_widths):
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
        stampa_tabella(
            "Ordini per categoria",
            ["Categoria", "Totale"],
            righe_categorie,
            [120, 40]
        )

    ore = dati_statistiche.get("ore", [])
    righe_ore = [(o.get("ora", ""), o.get("totale", 0)) for o in ore]
    if righe_ore:
        stampa_tabella(
            "Andamento ordini per ora",
            ["Ora", "Totale"],
            righe_ore,
            [40, 40]
        )

    top10 = dati_statistiche.get("top10", [])
    righe_top10 = [(p.get("nome", ""), p.get("venduti", 0)) for p in top10]
    if righe_top10:
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
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 9, "Dettaglio ordini", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

        def tronca_testo(testo, max_len):
            testo = str(testo)
            return testo if len(testo) <= max_len else (testo[: max_len - 3] + "...")

        for ordine in ordini:
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
                WHERE op.ordine_id = ?
                ORDER BY p.categoria_menu, p.nome
                """,
                (id_ordine,)
            )

            totale_ordine = sum((r["subtotale"] or 0) for r in righe_prodotti) if righe_prodotti else 0

            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 7, f"Ordine #{id_ordine}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 6, f"Data: {ordine['data_ordine']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.cell(0, 6, f"Cliente: {ordine['nome_cliente']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            tipo = "Asporto" if ordine["asporto"] == 1 else "Tavolo"
            tavolo = "-" if ordine["numero_tavolo"] is None else ordine["numero_tavolo"]
            persone = "-" if ordine["numero_persone"] is None else ordine["numero_persone"]
            completato = "Si" if ordine["completato"] == 1 else "No"
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
    headers = {"Content-Disposition": f'attachment; filename=\"{filename}\"'}
    return Response(pdf_bytes, mimetype="application/pdf", headers=headers)

@app.route('/api/rifornisci_prodotto', methods=['POST'])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def rifornisci_prodotto():
    data = request.get_json()
    id_prodotto = data.get('id')
    try:
        quantita = int(data.get('quantita'))
    except (ValueError, TypeError):
        return jsonify({"errore": "Quantità non valida"}), 400

    if not id_prodotto or quantita <= 0:
        return jsonify({"errore": "Dati mancanti o non validi"}), 400

    esegui_query(
        "UPDATE prodotti SET quantita = quantita + ? WHERE id = ?",
        (quantita, id_prodotto),
        commit=True
    )
    
    # Aggiorna anche lo stato di disponibilità se necessario
    esegui_query(
        "UPDATE prodotti SET disponibile = 1 WHERE id = ? AND quantita > 0",
        (id_prodotto,),
        commit=True
    )
    
    socketio.start_background_task(ricalcola_statistiche)
    return jsonify({"messaggio": "Prodotto rifornito con successo"})

@app.route('/api/modifica_prodotto', methods=['POST'])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def modifica_prodotto():
    data = request.get_json()
    
    try:
        # Logica automatica disponibilità
        quantita = int(data['quantita'])
        disponibile = 1 if quantita > 0 else 0
        
        esegui_query("""
            UPDATE prodotti 
            SET nome = ?, categoria_dashboard = ?, quantita = ?, disponibile = ?
            WHERE id = ?
        """, (
            data['nome'], 
            data['categoria_dashboard'], 
            quantita, 
            disponibile,
            data['id']
        ), commit=True)
        socketio.start_background_task(ricalcola_statistiche)
        return jsonify({"messaggio": "Prodotto modificato con successo"})
    except Exception as e:
        print(f"Errore modifica prodotto: {e}")
        return jsonify({"errore": "Errore durante la modifica"}), 500

@app.route('/api/aggiungi_prodotto', methods=['POST'])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def aggiungi_prodotto():
    data = request.get_json()
    
    try:
        nome = data.get('nome')
        categoria_dashboard = data.get('categoria_dashboard')
        categoria_menu = data.get('categoria_menu')
        prezzo = float(data.get('prezzo', 0))
        quantita = int(data.get('quantita', 0))
        disponibile = 1 if data.get('disponibile') else 0
        
        # Validazione base
        if not nome or not categoria_dashboard or not categoria_menu:
            return jsonify({"errore": "Dati mancanti"}), 400
            
        # Logica automatica disponibilità (se quantità > 0, forza disponibile)
        if quantita > 0:
            disponibile = 1
            
        esegui_query("""
            INSERT INTO prodotti (nome, categoria_dashboard, categoria_menu, prezzo, quantita, disponibile, venduti)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (nome, categoria_dashboard, categoria_menu, prezzo, quantita, disponibile), commit=True)
        
        socketio.start_background_task(ricalcola_statistiche)
        return jsonify({"messaggio": "Prodotto aggiunto con successo"})
    except Exception as e:
        print(f"Errore aggiunta prodotto: {e}")
        return jsonify({"errore": "Errore durante l'aggiunta"}), 500

@app.route('/api/elimina_prodotto', methods=['POST'])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def elimina_prodotto():
    data = request.get_json()
    
    try:
        esegui_query("DELETE FROM prodotti WHERE id = ?", (data['id'],), commit=True)
        socketio.start_background_task(ricalcola_statistiche)
        return jsonify({"messaggio": "Prodotto eliminato con successo"})
    except Exception as e:
        print(f"Errore eliminazione prodotto: {e}")
        return jsonify({"errore": "Errore durante l'eliminazione"}), 500

@app.route('/api/elimina_ordine', methods=['POST'])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def elimina_ordine():
    data = request.get_json()
    id_ordine = data.get('id')
    
    if not id_ordine:
        return jsonify({"errore": "ID ordine mancante"}), 400

    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()
            
            # 1. Recupera i prodotti dell'ordine da eliminare
            cursore.execute("""
                SELECT prodotto_id, quantita 
                FROM ordini_prodotti 
                WHERE ordine_id = ?
            """, (id_ordine,))
            prodotti_ordine = cursore.fetchall()

            # 2. Ripristina le quantità nel magazzino e riduci i venduti
            for p in prodotti_ordine:
                prodotto_id = p["prodotto_id"]
                quantita = p["quantita"]
                
                cursore.execute("""
                    UPDATE prodotti 
                    SET quantita = quantita + ?, venduti = venduti - ?
                    WHERE id = ?
                """, (quantita, quantita, prodotto_id))

                # Se la quantità torna > 0, rendi il prodotto disponibile
                cursore.execute("""
                    UPDATE prodotti 
                    SET disponibile = 1 
                    WHERE id = ? AND quantita > 0
                """, (prodotto_id,))
            
            # 3. Elimina l'ordine
            cursore.execute("DELETE FROM ordini_prodotti WHERE ordine_id = ?", (id_ordine,))
            cursore.execute("DELETE FROM ordini WHERE id = ?", (id_ordine,))
            connessione.commit()
        
        socketio.start_background_task(ricalcola_statistiche)
        return jsonify({"messaggio": "Ordine eliminato con successo"})
    except Exception as e:
        print(f"Errore eliminazione ordine: {e}")
        return jsonify({"errore": "Errore durante l'eliminazione"}), 500

@app.route('/api/modifica_ordine', methods=['POST'])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def modifica_ordine():
    data = request.get_json()
    id_ordine = data.get('id_ordine')
    
    if not id_ordine:
        return jsonify({"errore": "ID ordine mancante"}), 400

    try:
        nome_cliente = data.get('nome_cliente')
        numero_tavolo = data.get('numero_tavolo')
        numero_persone = data.get('numero_persone')
        metodo_pagamento = data.get('metodo_pagamento')
        
        # Gestione valori vuoti
        if numero_tavolo == '':
            numero_tavolo = None
        if numero_persone == '':
            numero_persone = None

        esegui_query("""
            UPDATE ordini 
            SET nome_cliente = ?, numero_tavolo = ?, numero_persone = ?, metodo_pagamento = ?
            WHERE id = ?
        """, (nome_cliente, numero_tavolo, numero_persone, metodo_pagamento, id_ordine), commit=True)
        
        socketio.start_background_task(ricalcola_statistiche)
        
        return jsonify({"messaggio": "Ordine aggiornato con successo"})
    except Exception as e:
        print(f"Errore modifica ordine: {e}")
        return jsonify({"errore": "Errore durante l'aggiornamento"}), 500

@app.route('/api/aggiungi_utente', methods=['POST'])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def aggiungi_utente():
    data = request.get_json()
    
    username = data.get('username')
    password = data.get('password')
    is_admin = 1 if data.get('is_admin') else 0
    attivo = 1 if data.get('attivo') else 0
    permessi = data.get('permessi', [])

    if not username or not password:
        return jsonify({"errore": "Username e password obbligatori"}), 400

    if not isinstance(permessi, list):
        permessi = []
    permessi = [p.strip() for p in permessi if isinstance(p, str) and p.strip()]
    permessi = list(dict.fromkeys(permessi))

    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()

            # Verifica esistenza username
            cursore.execute("SELECT id FROM utenti WHERE username = ?", (username,))
            if cursore.fetchone():
                return jsonify({"errore": "Username già in uso"}), 400

            # Hash password
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()

            # Inserisci utente
            cursore.execute("""
                INSERT INTO utenti (username, password_hash, is_admin, attivo)
                VALUES (?, ?, ?, ?)
            """, (username, password_hash, is_admin, attivo))
            
            id_utente = cursore.lastrowid

            # Inserisci permessi
            for pagina in permessi:
                cursore.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)", (id_utente, pagina))
            
            connessione.commit()

        return jsonify({"messaggio": "Utente creato con successo"})
    except Exception as e:
        print(f"Errore aggiunta utente: {e}")
        return jsonify({"errore": "Errore durante la creazione"}), 500

@app.route('/api/modifica_utente', methods=['POST'])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def modifica_utente():
    data = request.get_json()
    id_utente = data.get('id_utente')

    if not id_utente:
        return jsonify({"errore": "ID utente mancante"}), 400

    try:
        username = data.get('username')
        password = data.get('password')
        is_admin = 1 if data.get('is_admin') else 0
        attivo = 1 if data.get('attivo') else 0
        permessi = data.get('permessi', [])

        if not isinstance(permessi, list):
            permessi = []
        permessi = [p.strip() for p in permessi if isinstance(p, str) and p.strip()]
        permessi = list(dict.fromkeys(permessi))

        with ottieni_db() as connessione:
            cursore = connessione.cursor()

            # Aggiorna utente
            if password:
                password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
                cursore.execute("""
                    UPDATE utenti
                    SET username = ?, password_hash = ?, is_admin = ?, attivo = ?
                    WHERE id = ?
                """, (username, password_hash, is_admin, attivo, id_utente))
            else:
                cursore.execute("""
                    UPDATE utenti
                    SET username = ?, is_admin = ?, attivo = ?
                    WHERE id = ?
                """, (username, is_admin, attivo, id_utente))

            # Aggiorna permessi (rimuovi tutti e reinserisci)
            cursore.execute("DELETE FROM permessi_pagine WHERE utente_id = ?", (id_utente,))
            
            for pagina in permessi:
                cursore.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)", (id_utente, pagina))
            
            connessione.commit()

        return jsonify({"messaggio": "Utente modificato con successo"})
    except Exception as e:
        print(f"Errore modifica utente: {e}")
        return jsonify({"errore": "Errore durante la modifica"}), 500

@app.route('/api/elimina_utente', methods=['POST'])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def elimina_utente():
    data = request.get_json()
    id_utente = data.get('id_utente')

    if not id_utente:
        return jsonify({"errore": "ID utente mancante"}), 400
    
    # Prevenzione auto-eliminazione
    if 'user_id' in session and str(session['user_id']) == str(id_utente):
         return jsonify({"errore": "Non puoi eliminare il tuo stesso account"}), 400

    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()
            
            # Verifica esistenza
            cursore.execute("SELECT id FROM utenti WHERE id = ?", (id_utente,))
            if not cursore.fetchone():
                return jsonify({"errore": "Utente non trovato"}), 404

            # Elimina permessi e utente
            cursore.execute("DELETE FROM permessi_pagine WHERE utente_id = ?", (id_utente,))
            cursore.execute("DELETE FROM utenti WHERE id = ?", (id_utente,))
            
            connessione.commit()

        return jsonify({"messaggio": "Utente eliminato con successo"})
    except Exception as e:
        print(f"Errore eliminazione utente: {e}")
        return jsonify({"errore": "Errore durante l'eliminazione"}), 500

@app.route('/api/ordine/<int:ordine_id>/dettagli')
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def ordine_dettagli(ordine_id):
    dettagli = esegui_query("""
        SELECT 
            p.nome,
            p.categoria_menu,
            op.quantita,
            p.prezzo,
            (p.prezzo * op.quantita) as subtotale,
            op.stato
        FROM ordini_prodotti op
        JOIN prodotti p ON op.prodotto_id = p.id
        WHERE op.ordine_id = ?
    """, (ordine_id,))
    
    # Calculate total
    totale = sum(d['subtotale'] for d in dettagli)
    
    return render_template('partials/_ordine_dettagli.html', dettagli=dettagli, totale=totale, ordine_id=ordine_id)

# @app.route('/test_expansion')
# @accesso_richiesto
# @richiedi_permesso("AMMINISTRAZIONE")
# def test_expansion():
#     # Fetch some orders for testing
#     ordini = esegui_query("""
#         SELECT o.id, o.nome_cliente, o.numero_tavolo, o.numero_persone, o.data_ordine, o.metodo_pagamento,
#                COALESCE(SUM(p.prezzo * op.quantita), 0) as totale
#         FROM ordini o
#         LEFT JOIN ordini_prodotti op ON o.id = op.ordine_id
#         LEFT JOIN prodotti p ON op.prodotto_id = p.id
#         GROUP BY o.id
#         ORDER BY o.data_ordine DESC
#         LIMIT 5
#     """)
#     return render_template('test_row_expansion.html', ordini=ordini)

@app.route('/api/ordine/<int:id_ordine>')
def api_ordine(id_ordine):
    intestazione = esegui_query(
        """
        SELECT id, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento, data_ordine
        FROM ordini
        WHERE id = ?
        """,
        (id_ordine,),
        uno=True
    )
    if not intestazione:
        abort(404)
    righe_articoli = esegui_query(
        """
        SELECT p.nome AS nome, op.quantita AS quantita, p.prezzo AS prezzo
        FROM ordini_prodotti op
        JOIN prodotti p ON p.id = op.prodotto_id
        WHERE op.ordine_id = ?
        """,
        (id_ordine,)
    )
    articoli = [
        {"nome": r["nome"], "quantita": r["quantita"], "prezzo": r["prezzo"]}
        for r in righe_articoli
    ]
    return jsonify({
        "id": intestazione["id"],
        "nome_cliente": intestazione["nome_cliente"],
        "numero_tavolo": intestazione["numero_tavolo"],
        "numero_persone": intestazione["numero_persone"],
        "metodo_pagamento": intestazione["metodo_pagamento"],
        "data_ordine": intestazione["data_ordine"],
        "items": articoli
    })

@app.route('/api/amministrazione/ordini_html')
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def api_amministrazione_ordini_html():
    ordini = esegui_query("""
        SELECT o.id, o.nome_cliente, o.numero_tavolo, o.numero_persone, o.data_ordine, o.metodo_pagamento,
               COALESCE(SUM(p.prezzo * op.quantita), 0) as totale
        FROM ordini o
        LEFT JOIN ordini_prodotti op ON o.id = op.ordine_id
        LEFT JOIN prodotti p ON op.prodotto_id = p.id
        GROUP BY o.id
        ORDER BY o.data_ordine DESC
    """)
    return render_template('partials/_amministrazione_ordini_rows.html', ordini=ordini)

@app.route('/api/amministrazione/prodotti_html')
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def api_amministrazione_prodotti_html():
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
        ORDER BY categoria_menu;
    """)
    
    categorie_db = esegui_query("SELECT DISTINCT categoria_menu FROM prodotti ORDER BY categoria_menu")
    categorie = [riga["categoria_menu"] for riga in categorie_db]
    prima_categoria = categorie[0] if categorie else None

    return render_template('partials/_amministrazione_prodotti_rows.html', prodotti=prodotti, prima_categoria=prima_categoria)

@app.route('/genera_statistiche/')
def genera_statistiche():
    ricalcola_statistiche()
    return redirect('/amministrazione/')

@app.route('/debug/reset_dati/')
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def debug_reset_dati():
    esegui_query("DELETE FROM ordini_prodotti", commit=True)
    esegui_query("DELETE FROM ordini", commit=True)
    esegui_query("UPDATE prodotti SET disponibile = 1, quantita = 100, venduti = 0", commit=True)
    ricalcola_statistiche()
    return redirect('/amministrazione/')

# --- AVVIO SERVER ---

if __name__ == '__main__':
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except:
        ip = '127.0.0.1'
    finally:
        s.close()
    print(f'Avvio server — apri: http://{ip}:8000/')
    debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
    socketio.run(app, host='0.0.0.0', port=8000, debug=debug_mode)
