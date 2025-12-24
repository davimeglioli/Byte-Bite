from flask import Flask, json, jsonify, redirect, render_template, request, session, abort, url_for
import sqlite3 as sq
import socket
import bcrypt
import secrets
from flask_socketio import SocketIO, join_room
import uuid
from functools import wraps

# Dizionario per tracciare i timer attivi per gli ordini
timer_attivi = {}

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_timeout=60,      # Quanto tempo il server aspetta un PONG
    ping_interval=25,     # Ogni quanto manda un PING
)

# --- UTILITY DATABASE ---

def ottieni_db():
    """Stabilisce una connessione al database."""
    connessione = sq.connect('db.sqlite3')
    connessione.row_factory = sq.Row
    return connessione

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
    """Recupera i dati dell'utente attualmente loggato."""
    id_utente = session.get("id_utente")
    if not id_utente:
        return None

    return esegui_query(
        "SELECT id, username, is_admin, attivo FROM utenti WHERE id = ?",
        (id_utente,),
        uno=True
    )

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
    # Carica tutti gli ordini
    ordini = esegui_query("""
        SELECT id, metodo_pagamento, data_ordine, completato
        FROM ordini
    """)

    # Totale ordini e completati
    ordini_totali = len(ordini)
    ordini_completati = sum(1 for o in ordini if o["completato"] == 1)

    # Reset statistiche
    esegui_query("DELETE FROM statistiche_totali", commit=True)
    esegui_query("DELETE FROM statistiche_categorie", commit=True)
    esegui_query("DELETE FROM statistiche_ore", commit=True)

    # Categorie dashboard fisse
    categorie = ["Bar", "Cucina", "Griglia", "Gnoccheria"]

    # Inserisce le categorie
    for cat in categorie:
        esegui_query("""
            INSERT INTO statistiche_categorie (categoria_dashboard, totale)
            VALUES (?, 0)
        """, (cat,), commit=True)

    # Inizializza ore da 0 a 23
    for h in range(24):
        esegui_query("""
            INSERT INTO statistiche_ore (ora, totale)
            VALUES (?, 0)
        """, (h,), commit=True)

    # Inizializza totali incasso
    totale_incasso = 0
    totale_contanti = 0
    totale_carta = 0

    # Ciclo su tutti gli ordini
    for ordine in ordini:
        ordine_id = ordine["id"]
        metodo = ordine["metodo_pagamento"]

        # Calcola incasso dell'ordine
        incasso_ordine = esegui_query("""
            SELECT SUM(p.prezzo * op.quantita) AS totale
            FROM ordini_prodotti op
            JOIN prodotti p ON p.id = op.prodotto_id
            WHERE op.ordine_id = ?
        """, (ordine_id,), uno=True)["totale"] or 0

        # Somma incasso totale
        totale_incasso += incasso_ordine

        # Aggiorna incassi contanti/carta
        if metodo == "Contanti":
            totale_contanti += incasso_ordine
        else:
            totale_carta += incasso_ordine

        # Calcola ora dell'ordine
        ora = esegui_query("""
            SELECT CAST(strftime('%H', data_ordine) AS INT) AS h
            FROM ordini WHERE id = ?
        """, (ordine_id,), uno=True)["h"]

        # Aggiorna statistiche per ora
        esegui_query("""
            UPDATE statistiche_ore
            SET totale = totale + 1
            WHERE ora = ?
        """, (ora,), commit=True)

        # Calcola categorie dashboard coinvolte
        righe_cat = esegui_query("""
            SELECT p.categoria_dashboard, SUM(op.quantita) AS qta
            FROM ordini_prodotti op
            JOIN prodotti p ON p.id = op.prodotto_id
            WHERE op.ordine_id = ?
            GROUP BY p.categoria_dashboard
        """, (ordine_id,))

        # Aggiorna statistiche categorie
        for riga in righe_cat:
            esegui_query("""
                UPDATE statistiche_categorie
                SET totale = totale + ?
                WHERE categoria_dashboard = ?
            """, (riga["qta"], riga["categoria_dashboard"]), commit=True)

    # Inserisce statistiche totali
    esegui_query("""
        INSERT INTO statistiche_totali
        (id, ordini_totali, ordini_completati, totale_incasso, totale_contanti, totale_carta)
        VALUES (1, ?, ?, ?, ?, ?)
    """, (
        ordini_totali,
        ordini_completati,
        totale_incasso,
        totale_contanti,
        totale_carta
    ), commit=True)
    
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
    conn = ottieni_db()
    conn.row_factory = sq.Row
    
    # Usa GROUP BY per ottenere categorie uniche mantenendo l'ordine originale
    categorie_righe = esegui_query('SELECT categoria_menu FROM prodotti GROUP BY categoria_menu ORDER BY MIN(id)')
    categorie = [riga['categoria_menu'] for riga in categorie_righe]

    # Prodotti per ogni categoria
    prodotti_per_categoria = {}
    for cat in categorie:
        prodotti_per_categoria[cat] = esegui_query(
            'SELECT * FROM prodotti WHERE categoria_menu = ?', (cat,)
        )

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

    # Inserisce il nuovo ordine
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        cursore.execute("""
            INSERT INTO ordini (asporto, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento)
            VALUES (?, ?, ?, ?, ?)
        """, (asporto, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento))
        id_ordine = cursore.lastrowid  # ID dell'ordine appena creato

        # Inserisci i prodotti e aggiorna il magazzino
        for p in prodotti:
            cursore.execute("""
                INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)
                VALUES (?, ?, ?, ?)
            """, (id_ordine, p["id"], p["quantita"], "In Attesa"))
            cursore.execute("""
                UPDATE prodotti
                SET quantita = quantita - ?, venduti = venduti + ?
                WHERE id = ?
            """, (p["quantita"], p["quantita"], p["id"]))

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

# --- ROUTES: DASHBOARD ---

@app.route('/dashboard/<category>/')
@accesso_richiesto
def dashboard(category):
    permesso = "DASHBOARD_" + category.upper()

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

        #socketio.sleep(0.1)  # Piccolo delay per sicurezza
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

    return render_template(
        "amministrazione.html",
        ordini=ordini,
        prodotti=prodotti,
        categorie=categorie
    )

@app.route('/api/statistiche/')
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def api_statistiche():
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

    return jsonify({
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
    })

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
        
        # Se l'utente ha esplicitamente disattivato la disponibilità anche con quantità > 0 (opzionale, ma sicuro)
        # In questo caso seguiamo la logica richiesta: la quantità comanda lo stato.
        # Se vuoi che l'utente possa avere Qta > 0 ma Disponibile = False, rimuovi la riga sopra e usa data['disponibile']
        # Ma per ora implemento la richiesta "passa a disponibile in auto"
        
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

@app.route('/test_expansion')
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def test_expansion():
    # Fetch some orders for testing
    ordini = esegui_query("""
        SELECT o.id, o.nome_cliente, o.numero_tavolo, o.numero_persone, o.data_ordine, o.metodo_pagamento,
               COALESCE(SUM(p.prezzo * op.quantita), 0) as totale
        FROM ordini o
        LEFT JOIN ordini_prodotti op ON o.id = op.ordine_id
        LEFT JOIN prodotti p ON op.prodotto_id = p.id
        GROUP BY o.id
        ORDER BY o.data_ordine DESC
        LIMIT 5
    """)
    return render_template('test_row_expansion.html', ordini=ordini)

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
    return render_template('partials/_amministrazione_prodotti_rows.html', prodotti=prodotti)

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
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)
