import contextlib
import logging
import os
import secrets
import socket
import sqlite3 as sq
import uuid
from datetime import datetime
from functools import wraps

import bcrypt
from dotenv import load_dotenv
from flask import (
    Flask,
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
from flask_socketio import SocketIO, join_room
from fpdf import FPDF, XPos, YPos

load_dotenv()

# ==================== Configurazione ====================
timer_attivi = {}

app = Flask(__name__)

# Configura logging solo su console (root logger) per avere un formato uniforme.
_logger_root = logging.getLogger()
# Pulisce eventuali handler pre-esistenti per evitare duplicazioni di output.
_logger_root.handlers.clear()
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
_logger_root.addHandler(_console_handler)

# Legge il livello da env (LOG_LEVEL) e lo normalizza su un livello valido.
_livello_log = os.getenv("LOG_LEVEL", "INFO").upper()
_logger_level = getattr(logging, _livello_log, logging.INFO)
_logger_root.setLevel(_logger_level)

# Allinea il logger di Flask al root logger e propaga i record (utile anche per i test).
app.logger.handlers.clear()
app.logger.propagate = True
app.logger.setLevel(_logger_level)
# Imposta una chiave di sessione stabile (da env) o generata al volo.
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))

with app.app_context():
    try:
        # Migliora concorrenza su SQLite quando ci sono più richieste.
        with sq.connect("db.sqlite3", timeout=30) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        app.logger.exception("Impossibile abilitare WAL mode")

@app.errorhandler(403)
def errore_403(error):
    # Handler centralizzato per accessi non autorizzati.
    return "403 Forbidden", 403

socketio = SocketIO(app, cors_allowed_origins="*", logger=False, engineio_logger=False)

# ==================== Database ====================

@contextlib.contextmanager
def ottieni_db():
    """Stabilisce una connessione al database e la chiude automaticamente."""
    # Crea una connessione per-request con timeout per ridurre i lock su SQLite.
    connessione = sq.connect("db.sqlite3", timeout=30)
    # Permette accesso ai campi delle righe per nome colonna.
    connessione.row_factory = sq.Row
    try:
        # Espone la connessione al chiamante.
        yield connessione
    finally:
        # Chiude sempre la connessione anche in caso di errore.
        connessione.close()

def esegui_query(query, argomenti=(), uno=False, commit=False):
    """Esegue una query SQL e gestisce la connessione."""
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        # Usa parametri bindati per evitare injection e gestire i tipi correttamente.
        cursore.execute(query, argomenti)
        righe = None
        if not commit:
            # Per SELECT e simili: restituisce tutte le righe lette.
            righe = cursore.fetchall()
        if commit:
            # Per INSERT/UPDATE/DELETE: applica la transazione.
            connessione.commit()
    # Se richiesto, restituisce solo la prima riga; altrimenti la lista completa.
    return (righe[0] if righe else None) if uno else (righe or [])

# ==================== Autenticazione ====================

def ottieni_utente_loggato():
    """Recupera i dati dell'utente attualmente loggato dalla sessione (cache) o dal DB."""
    # Identifica l'utente tramite sessione.
    id_utente = session.get("id_utente")
    if not id_utente:
        # Nessuna sessione: nessun utente loggato.
        return None

    # Se la cache in sessione è coerente, evita una query al DB.
    if session.get("user_cache_id") == id_utente:
        # Struttura standard usata da permessi e template.
        return {
            "id": session["user_cache_id"],
            "username": session["user_cache_username"],
            "is_admin": session["user_cache_is_admin"],
            "attivo": session["user_cache_attivo"]
        }

    # Prima richiesta o cache invalida: carica dal database.
    utente = esegui_query(
        "SELECT id, username, is_admin, attivo FROM utenti WHERE id = ?",
        (id_utente,),
        uno=True
    )

    if utente:
        # Aggiorna la cache per le richieste successive.
        session["user_cache_id"] = utente["id"]
        session["user_cache_username"] = utente["username"]
        session["user_cache_is_admin"] = utente["is_admin"]
        session["user_cache_attivo"] = utente["attivo"]

    # Ritorna la riga (sq.Row) o None se l'utente non esiste.
    return utente

def accesso_richiesto(f):
    """Decoratore per richiedere il login per accedere a una route."""
    @wraps(f)
    def gestore(*args, **kwargs):
        # Se non loggato, rimanda alla pagina di accesso.
        if "id_utente" not in session:
            return redirect(url_for("accesso"))
        # Se loggato, esegue la funzione originale.
        return f(*args, **kwargs)
    return gestore

def richiedi_permesso(pagina):
    """Decoratore per verificare i permessi di accesso a una pagina specifica."""
    def decorator(f):
        @wraps(f)
        def gestore(*args, **kwargs):
            # Garantisce che esista una sessione valida.
            if "id_utente" not in session:
                return redirect(url_for("accesso"))

            # Recupera l'utente (con cache sessione per ridurre query).
            utente = ottieni_utente_loggato()

            # Se l'utente è disattivo, svuota la sessione e forza il login.
            if not utente or utente["attivo"] != 1:
                session.clear()
                return redirect(url_for("accesso"))

            # L'amministratore ha accesso completo.
            if utente["is_admin"] == 1:
                return f(*args, **kwargs)

            # Verifica il permesso specifico per la pagina richiesta.
            permesso = esegui_query("""
                SELECT 1 FROM permessi_pagine
                WHERE utente_id = ? AND pagina = ?
            """, (utente["id"], pagina), uno=True)

            if permesso:
                # Permesso presente: esegue la route.
                return f(*args, **kwargs)

            # In assenza di permesso, blocca l'accesso.
            abort(403)

        return gestore
    return decorator

# ==================== SocketIO ====================

def emissione_sicura(evento, dati, stanza=None):
    """Invia un messaggio SocketIO gestendo eventuali errori."""
    try:
        # Invia l'evento alla stanza richiesta (o broadcast se stanza è None).
        socketio.emit(evento, dati, room=stanza)
        if stanza and stanza != "amministrazione" and evento == "aggiorna_dashboard":
            # Replica l'aggiornamento anche all'area amministrazione.
            socketio.emit(evento, dati, room="amministrazione")
    except Exception as errore:
        app.logger.warning("Errore durante emissione: %s", errore, exc_info=True)

@socketio.on("join")
def gestisci_join(dati):
    """Gestisce l'ingresso di un client in una stanza SocketIO."""
    # Ogni dashboard si iscrive alla sua categoria per ricevere solo eventi utili.
    categoria = dati.get("categoria")
    if categoria:
        # Iscrive la connessione alla stanza (es. Bar, Cucina, Griglia).
        join_room(categoria)

# ==================== Logica di business ====================

def ottieni_ordini_per_categoria(categoria):
    """Recupera gli ordini (completati e non) per una specifica categoria."""
    # Normalizza il nome categoria così coincide con il valore salvato a DB.
    categoria = categoria.capitalize()

    # Estrae righe ordine-prodotto e le ordina cronologicamente.
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

    # Raggruppa le righe per ordine per costruire la struttura attesa dai template.
    ordini = {}
    for riga in ordini_db:
        # Chiave di aggregazione: id ordine.
        id_ordine = riga["ordine_id"]
        ordini.setdefault(id_ordine, {
            "id": id_ordine,
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

    # Separa gli ordini completati da quelli ancora in lavorazione.
    ordini_non_completati = []
    ordini_completati = []

    for ordine in ordini.values():
        if ordine["stato"] == "Completato":
            ordini_completati.append(ordine)
        else:
            ordini_non_completati.append(ordine)

    # Mostra per primi i completati più recenti.
    ordini_completati.sort(key=lambda o: o["data_ordine"], reverse=True)

    return ordini_non_completati, ordini_completati

def ricalcola_statistiche():
    """Ricalcola tutte le statistiche e le salva nel database."""

    # Calcola i totali complessivi e per metodo di pagamento.
    statistiche_totali = esegui_query("""
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

    # Calcola i volumi per categoria dashboard.
    statistiche_categorie = esegui_query("""
        SELECT p.categoria_dashboard, SUM(op.quantita) as totale
        FROM ordini_prodotti op
        JOIN prodotti p ON op.prodotto_id = p.id
        GROUP BY p.categoria_dashboard
    """)

    # Calcola la distribuzione ordini per ora del giorno.
    statistiche_ore = esegui_query("""
        SELECT CAST(strftime('%H', data_ordine) AS INT) as ora, COUNT(*) as totale
        FROM ordini
        GROUP BY ora
    """)

    with ottieni_db() as connessione:
        cursore = connessione.cursor()

        # Rigenera completamente le tabelle statistiche per mantenere coerenza.
        cursore.execute("DELETE FROM statistiche_totali")
        cursore.execute("DELETE FROM statistiche_categorie")
        cursore.execute("DELETE FROM statistiche_ore")

        # Inserisce una sola riga per i totali generali.
        cursore.execute("""
            INSERT INTO statistiche_totali 
            (id, ordini_totali, ordini_completati, totale_incasso, totale_contanti, totale_carta)
            VALUES (1, ?, ?, ?, ?, ?)
        """, (
            statistiche_totali["ordini_totali"] or 0,
            statistiche_totali["ordini_completati"] or 0,
            statistiche_totali["totale_incasso"],
            statistiche_totali["totale_contanti"],
            statistiche_totali["totale_carta"],
        ))

        # Mantiene l'ordine delle categorie coerente con la UI.
        categorie_fisse = ["Bar", "Cucina", "Griglia", "Gnoccheria"]
        totali_per_categoria = {riga["categoria_dashboard"]: riga["totale"] for riga in statistiche_categorie}
        for categoria in categorie_fisse:
            # Usa 0 quando una categoria non ha vendite.
            valore = totali_per_categoria.get(categoria, 0)
            cursore.execute(
                "INSERT INTO statistiche_categorie (categoria_dashboard, totale) VALUES (?, ?)",
                (categoria, valore),
            )

        # Inserisce tutte le ore 0-23 così il grafico è sempre completo.
        totali_per_ora = {riga["ora"]: riga["totale"] for riga in statistiche_ore}
        for ora in range(24):
            valore = totali_per_ora.get(ora, 0)
            cursore.execute("INSERT INTO statistiche_ore (ora, totale) VALUES (?, ?)", (ora, valore))

        connessione.commit()

    # Notifica globale: le dashboard possono aggiornare i widget.
    emissione_sicura("aggiorna_dashboard", {})

def cambia_stato_automatico(ordine_id, categoria, timer_id):
    """Gestisce il passaggio automatico allo stato 'Completato' dopo un timeout."""
    chiave_timer = (ordine_id, categoria)

    # Attende un breve timeout (con possibilità di annullamento).
    for _ in range(10):
        # Sleep cooperativo per non bloccare l'event loop SocketIO.
        socketio.sleep(1)
        if (
            chiave_timer not in timer_attivi
            or timer_attivi[chiave_timer]["id"] != timer_id
            or timer_attivi[chiave_timer]["annulla"]
        ):
            return

    # Ricontrolla lo stato del timer prima di aggiornare il DB.
    if chiave_timer not in timer_attivi or timer_attivi[chiave_timer]["annulla"]:
        return

    # Forza lo stato "Completato" per tutti i prodotti della categoria.
    esegui_query("""
        UPDATE ordini_prodotti
        SET stato = 'Completato'
        WHERE ordine_id = ?
        AND prodotto_id IN (
            SELECT id FROM prodotti WHERE categoria_dashboard = ?
        );
    """, (ordine_id, categoria), commit=True)

    # Aggiorna il flag completato dell'ordine se non restano prodotti non completati.
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

    # Rimuove il timer e notifica la dashboard interessata.
    timer_attivi.pop(chiave_timer, None)

    emissione_sicura("aggiorna_dashboard", {"categoria": categoria}, stanza=categoria)
    # Aggiorna statistiche in background per non rallentare gli update realtime.
    socketio.start_background_task(ricalcola_statistiche)

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
            FROM utenti WHERE username = ?
        """, (username,), uno=True)

        if not utente:
            # Risposta generica per non rivelare quale campo è sbagliato.
            return render_template("login.html", error="Username o password errata")

        if utente["attivo"] != 1:
            # Blocca account disattivati a livello amministrativo.
            return render_template("login.html", error="Account disattivato")

        # Verifica la password con hash bcrypt.
        if not bcrypt.checkpw(password, utente["password_hash"].encode()):
            return render_template("login.html", error="Username o password errata")

        # Salva i dati minimi in sessione.
        session["id_utente"] = utente["id"]
        session["username"] = utente["username"]

        # Redirect verso la home dopo login.
        return redirect(url_for("home"))

    return render_template("login.html")

# ==================== Route: generali ====================

@app.route("/")
def home():
    # Pagina iniziale.
    return render_template("index.html")

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
    last_order_id = request.args.get("last_order_id")

    return render_template(
        "cassa.html",
        categorie=categorie,
        prodotti_per_categoria=prodotti_per_categoria,
        last_order_id=last_order_id
    )

@app.route("/aggiungi_ordine/", methods=["POST"])
def aggiungi_ordine():
    # Converte i campi del form nel formato atteso dal DB.
    asporto = 1 if request.form.get("isTakeaway") == "on" else 0
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
        return redirect(url_for("cassa") + "?error=Nessun prodotto selezionato", code=303)

    try:
        # Inserisce l'ordine e le righe prodotto in un'unica transazione.
        with ottieni_db() as connessione:
            cursore = connessione.cursor()
            # Inserisce l'intestazione ordine.
            cursore.execute("""
                INSERT INTO ordini (asporto, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento)
                VALUES (?, ?, ?, ?, ?)
            """, (asporto, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento))
            id_ordine = cursore.lastrowid

            for prodotto in prodotti:
                # Scala la quantità solo se c'è disponibilità sufficiente.
                cursore.execute("""
                    UPDATE prodotti
                    SET quantita = quantita - ?, venduti = venduti + ?
                    WHERE id = ? AND quantita >= ?
                """, (prodotto["quantita"], prodotto["quantita"], prodotto["id"], prodotto["quantita"]))

                if cursore.rowcount == 0:
                    # Se non aggiorna righe, lo stock non basta: abort della transazione.
                    raise Exception(f"Prodotto {prodotto.get('nome', 'Sconosciuto')} esaurito o insufficiente.")

                # Registra la riga ordine-prodotti con stato iniziale.
                cursore.execute("""
                    INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato)
                    VALUES (?, ?, ?, ?)
                """, (id_ordine, prodotto["id"], prodotto["quantita"], "In Attesa"))

            # Individua le dashboard da aggiornare in tempo reale.
            cursore.execute("""
                SELECT DISTINCT prodotti.categoria_dashboard
                FROM ordini_prodotti
                JOIN prodotti ON prodotti.id = ordini_prodotti.prodotto_id
                WHERE ordini_prodotti.ordine_id = ?
            """, (id_ordine,))
            categorie_dashboard = [riga[0] for riga in cursore.fetchall()]
            # Conferma atomica: o tutto scritto o nulla.
            connessione.commit()

        # Notifica le dashboard e aggiorna le statistiche in background.
        for categoria in categorie_dashboard:
            emissione_sicura("aggiorna_dashboard", {"categoria": categoria}, stanza=categoria)
        socketio.start_background_task(ricalcola_statistiche)

        return redirect(url_for("cassa") + f"?last_order_id={id_ordine}", code=303)

    except Exception as errore:
        # Log minimale e redirect verso la cassa con messaggio errore.
        app.logger.exception("Errore creazione ordine")
        return redirect(url_for("cassa") + f"?error={errore}", code=303)

# ==================== Route: dashboard ====================

@app.route("/dashboard/<category>/")
@accesso_richiesto
def dashboard(category):
    # Applica controllo permessi (admin o permesso dashboard).
    pagina_permesso = "DASHBOARD"

    # Richiama il decoratore come check esplicito (in caso di dashboard condivisa).
    richiedi_permesso(pagina_permesso)(lambda: None)()

    # Carica gli ordini e mostra la pagina della categoria richiesta.
    ordini_non_completati, ordini_completati = ottieni_ordini_per_categoria(category)
    return render_template(
        "dashboard.html",
        category=category.capitalize(),
        ordini_non_completati=ordini_non_completati,
        ordini_completati=ordini_completati
    )

@app.route("/dashboard/<category>/partial")
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
        WHERE ordine_id = ? AND prodotti.categoria_dashboard = ?
        LIMIT 1;
    """, (id_ordine, categoria), uno=True)

    stato_attuale = riga_stato["stato"]

    # Lista degli stati in sequenza (usata per avanzare).
    stati = ["In Attesa", "In Preparazione", "Pronto", "Completato"]

    chiave_timer = (id_ordine, categoria)

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
        SET stato = ?
        WHERE ordine_id = ?
        AND prodotto_id IN (
            SELECT id FROM prodotti WHERE categoria_dashboard = ?
        );
    """, (nuovo_stato, id_ordine, categoria), commit=True)

    # Aggiorna il flag completato dell'ordine in base ai residui.
    residui = esegui_query(
        "SELECT COUNT(*) AS c FROM ordini_prodotti WHERE ordine_id = ? AND stato != 'Completato'",
        (id_ordine,),
        uno=True
    )["c"]
    # Un ordine è completato solo se tutte le righe sono "Completato".
    esegui_query(
        "UPDATE ordini SET completato = ? WHERE id = ?",
        (1 if residui == 0 else 0, id_ordine),
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
        ORDER BY categoria_menu;
    """)

    # Liste categorie per filtro/selector lato UI.
    categorie_db = esegui_query("SELECT DISTINCT categoria_menu FROM prodotti")
    categorie = [riga["categoria_menu"] for riga in categorie_db]
    prima_categoria = categorie[0] if categorie else None

    # Costruisce elenco utenti con i permessi associati.
    utenti_db = esegui_query("SELECT id, username, is_admin, attivo FROM utenti ORDER BY username")
    utenti = []
    for riga in utenti_db:
        # Converte la riga DB in dict serializzabile/iterabile.
        utente = dict(riga)
        righe_permessi = esegui_query(
            "SELECT pagina FROM permessi_pagine WHERE utente_id = ?",
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

def costruisci_dati_statistiche():
    # Aggrega dati per grafici e riepiloghi lato amministrazione.
    # Numero ordini totali e completati.
    ordini_totali = esegui_query("SELECT COUNT(*) AS c FROM ordini", uno=True)["c"]
    ordini_completati = esegui_query("SELECT COUNT(*) AS c FROM ordini WHERE completato = 1", uno=True)["c"]

    # Totale incasso indipendentemente dal metodo.
    riga_totale_incasso = esegui_query(
        """
        SELECT SUM(p.prezzo * op.quantita) AS totale
        FROM ordini_prodotti op
        JOIN prodotti p ON p.id = op.prodotto_id
        """,
        uno=True
    )
    totale_incasso = riga_totale_incasso["totale"] or 0

    # Totale pagato in contanti.
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

    # Totale pagato con carta.
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

    # Distribuzione ordini per ora.
    righe_ore = esegui_query(
        """
        SELECT CAST(strftime('%H', data_ordine) AS INT) AS ora, COUNT(*) AS totale
        FROM ordini
        GROUP BY ora
        ORDER BY ora ASC
        """
    )
    ore = [dict(r) for r in righe_ore] if righe_ore else []

    # Volumi per categoria dashboard.
    righe_cat = esegui_query(
        """
        SELECT p.categoria_dashboard, SUM(op.quantita) AS totale
        FROM ordini_prodotti op
        JOIN prodotti p ON p.id = op.prodotto_id
        GROUP BY p.categoria_dashboard
        """
    )
    categorie = [dict(r) for r in righe_cat] if righe_cat else []

    # Classifica prodotti più venduti.
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
                WHERE op.ordine_id = ?
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

            tipo = "Asporto" if ordine["asporto"] == 1 else "Tavolo"
            tavolo = "-" if ordine["numero_tavolo"] is None else ordine["numero_tavolo"]
            persone = "-" if ordine["numero_persone"] is None else ordine["numero_persone"]
            completato = "Si" if ordine["completato"] == 1 else "No"
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
    headers = {"Content-Disposition": f'attachment; filename=\"{filename}\"'}
    return Response(pdf_bytes, mimetype="application/pdf", headers=headers)

# ==================== API: prodotti ====================

@app.route("/api/aggiungi_prodotto", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def aggiungi_prodotto():
    # Crea un nuovo prodotto a catalogo (con logica disponibilità basata sulla quantità).
    dati = request.get_json()

    try:
        # Legge e normalizza i campi in ingresso.
        nome = dati.get("nome")
        categoria_dashboard = dati.get("categoria_dashboard")
        categoria_menu = dati.get("categoria_menu")
        prezzo = float(dati.get("prezzo", 0))
        quantita = int(dati.get("quantita", 0))
        disponibile = 1 if dati.get("disponibile") else 0

        # Validazione minima dei campi obbligatori.
        if not nome or not categoria_dashboard or not categoria_menu:
            return jsonify({"errore": "Dati mancanti"}), 400

        if quantita > 0:
            # Se c'è stock, il prodotto deve risultare disponibile.
            disponibile = 1

        # Inserisce il prodotto con venduti iniziali a 0.
        esegui_query(
            """
            INSERT INTO prodotti (nome, categoria_dashboard, categoria_menu, prezzo, quantita, disponibile, venduti)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (nome, categoria_dashboard, categoria_menu, prezzo, quantita, disponibile),
            commit=True,
        )

        # Aggiorna statistiche dopo modifica catalogo.
        socketio.start_background_task(ricalcola_statistiche)

        # Traccia in console l'azione amministrativa per audit e debugging.
        app.logger.info(
            "ADMIN prodotto_aggiunto attore_id=%s attore=%s nome=%s cat_dash=%s cat_menu=%s prezzo=%s quantita=%s",
            # Identifica l'utente che sta operando da amministrazione.
            session.get("id_utente"),
            session.get("user_cache_username") or session.get("username"),
            # Dati principali del prodotto creato.
            nome,
            categoria_dashboard,
            categoria_menu,
            prezzo,
            quantita,
        )
        return jsonify({"messaggio": "Prodotto aggiunto con successo"})
    except Exception:
        # Errore generico per evitare leak di dettagli DB al client.
        app.logger.exception("Errore aggiunta prodotto")
        return jsonify({"errore": "Errore durante l'aggiunta"}), 500

@app.route("/api/modifica_prodotto", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def modifica_prodotto():
    # Aggiorna i campi del prodotto e sincronizza la disponibilità.
    dati = request.get_json()

    try:
        # Converte quantità e calcola disponibile in modo automatico.
        quantita = int(dati["quantita"])
        disponibile = 1 if quantita > 0 else 0

        # Aggiorna nome, categoria e stock.
        esegui_query(
            """
            UPDATE prodotti 
            SET nome = ?, categoria_dashboard = ?, quantita = ?, disponibile = ?
            WHERE id = ?
            """,
            (
                dati["nome"],
                dati["categoria_dashboard"],
                quantita,
                disponibile,
                dati["id"],
            ),
            commit=True,
        )
        # Aggiorna statistiche dopo variazione stock.
        socketio.start_background_task(ricalcola_statistiche)

        # Traccia in console l'azione amministrativa per audit e debugging.
        app.logger.info(
            "ADMIN prodotto_modificato attore_id=%s attore=%s id=%s nome=%s cat_dash=%s quantita=%s disponibile=%s",
            # Identifica l'utente che sta operando da amministrazione.
            session.get("id_utente"),
            session.get("user_cache_username") or session.get("username"),
            # Dati principali del prodotto aggiornato.
            dati.get("id"),
            dati.get("nome"),
            dati.get("categoria_dashboard"),
            quantita,
            disponibile,
        )
        return jsonify({"messaggio": "Prodotto modificato con successo"})
    except Exception:
        app.logger.exception("Errore modifica prodotto")
        return jsonify({"errore": "Errore durante la modifica"}), 500

@app.route("/api/rifornisci_prodotto", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def rifornisci_prodotto():
    # Incrementa lo stock di un prodotto e lo rende disponibile se necessario.
    dati = request.get_json()
    id_prodotto = dati.get("id")
    try:
        # Converte quantità in int e valida.
        quantita = int(dati.get("quantita"))
    except (ValueError, TypeError):
        return jsonify({"errore": "Quantità non valida"}), 400

    if not id_prodotto or quantita <= 0:
        return jsonify({"errore": "Dati mancanti o non validi"}), 400

    # Aumenta lo stock.
    esegui_query(
        "UPDATE prodotti SET quantita = quantita + ? WHERE id = ?",
        (quantita, id_prodotto),
        commit=True,
    )

    # Se lo stock torna > 0, forza disponibile.
    esegui_query(
        "UPDATE prodotti SET disponibile = 1 WHERE id = ? AND quantita > 0",
        (id_prodotto,),
        commit=True,
    )

    socketio.start_background_task(ricalcola_statistiche)

    # Traccia in console l'azione amministrativa per audit e debugging.
    app.logger.info(
        "ADMIN prodotto_rifornito attore_id=%s attore=%s id=%s aggiunta_quantita=%s",
        # Identifica l'utente che sta operando da amministrazione.
        session.get("id_utente"),
        session.get("user_cache_username") or session.get("username"),
        # Prodotto rifornito e quantità aggiunta.
        id_prodotto,
        quantita,
    )
    return jsonify({"messaggio": "Prodotto rifornito con successo"})

@app.route("/api/elimina_prodotto", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def elimina_prodotto():
    # Elimina un prodotto dal catalogo.
    dati = request.get_json()

    try:
        # Eliminazione diretta per id.
        esegui_query("DELETE FROM prodotti WHERE id = ?", (dati["id"],), commit=True)
        # Aggiorna statistiche dopo modifica catalogo.
        socketio.start_background_task(ricalcola_statistiche)

        # Traccia in console l'azione amministrativa per audit e debugging.
        app.logger.info(
            "ADMIN prodotto_eliminato attore_id=%s attore=%s id=%s",
            # Identifica l'utente che sta operando da amministrazione.
            session.get("id_utente"),
            session.get("user_cache_username") or session.get("username"),
            # Prodotto eliminato (id).
            dati.get("id"),
        )
        return jsonify({"messaggio": "Prodotto eliminato con successo"})
    except Exception:
        app.logger.exception("Errore eliminazione prodotto")
        return jsonify({"errore": "Errore durante l'eliminazione"}), 500

# ==================== API: ordini ====================

@app.route("/api/modifica_ordine", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def modifica_ordine():
    # Aggiorna i metadati dell'ordine (cliente, tavolo/persone, pagamento).
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

        # Converte stringhe vuote in NULL per SQLite.
        if numero_tavolo == "":
            numero_tavolo = None
        if numero_persone == "":
            numero_persone = None

        # Aggiorna intestazione ordine.
        esegui_query(
            """
            UPDATE ordini 
            SET nome_cliente = ?, numero_tavolo = ?, numero_persone = ?, metodo_pagamento = ?
            WHERE id = ?
            """,
            (nome_cliente, numero_tavolo, numero_persone, metodo_pagamento, id_ordine),
            commit=True,
        )

        # Aggiorna statistiche dopo modifica ordine.
        socketio.start_background_task(ricalcola_statistiche)

        # Traccia in console l'azione amministrativa per audit e debugging.
        app.logger.info(
            "ADMIN ordine_modificato attore_id=%s attore=%s id_ordine=%s cliente=%s tavolo=%s persone=%s pagamento=%s",
            # Identifica l'utente che sta operando da amministrazione.
            session.get("id_utente"),
            session.get("user_cache_username") or session.get("username"),
            # Metadati ordine aggiornati dall'interfaccia admin.
            id_ordine,
            nome_cliente,
            numero_tavolo,
            numero_persone,
            metodo_pagamento,
        )

        return jsonify({"messaggio": "Ordine aggiornato con successo"})
    except Exception:
        app.logger.exception("Errore modifica ordine")
        return jsonify({"errore": "Errore durante l'aggiornamento"}), 500

@app.route("/api/elimina_ordine", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def elimina_ordine():
    # Elimina un ordine ripristinando il magazzino e i venduti.
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
                WHERE ordine_id = ?
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
                    SET quantita = quantita + ?, venduti = venduti - ?
                    WHERE id = ?
                    """,
                    (quantita, quantita, prodotto_id),
                )

                # Se torna disponibile, la UI può renderlo selezionabile.
                cursore.execute(
                    """
                    UPDATE prodotti 
                    SET disponibile = 1 
                    WHERE id = ? AND quantita > 0
                    """,
                    (prodotto_id,),
                )

            # Rimuove prima le righe e poi l'intestazione ordine.
            cursore.execute("DELETE FROM ordini_prodotti WHERE ordine_id = ?", (id_ordine,))
            cursore.execute("DELETE FROM ordini WHERE id = ?", (id_ordine,))
            connessione.commit()

        # Aggiorna statistiche dopo eliminazione.
        socketio.start_background_task(ricalcola_statistiche)

        # Traccia in console l'azione amministrativa per audit e debugging.
        app.logger.info(
            "ADMIN ordine_eliminato attore_id=%s attore=%s id_ordine=%s righe=%s",
            # Identifica l'utente che sta operando da amministrazione.
            session.get("id_utente"),
            session.get("user_cache_username") or session.get("username"),
            # Id ordine e numero righe ripristinate a magazzino.
            id_ordine,
            len(prodotti_ordine),
        )
        return jsonify({"messaggio": "Ordine eliminato con successo"})
    except Exception:
        app.logger.exception("Errore eliminazione ordine")
        return jsonify({"errore": "Errore durante l'eliminazione"}), 500

@app.route("/api/ordine/<int:ordine_id>/dettagli")
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def ordine_dettagli(ordine_id):
    # Ritorna un frammento HTML con dettaglio righe ordine e totale.
    # Query unica che include subtotale per riga.
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
        WHERE op.ordine_id = ?
        """,
        (ordine_id,),
    )

    # Somma i subtotali calcolati dalla query.
    totale = sum(riga["subtotale"] for riga in dettagli)
    # Render parziale usato dall'admin per espansione riga.
    return render_template(
        "partials/_ordine_dettagli.html",
        dettagli=dettagli,
        totale=totale,
        ordine_id=ordine_id,
    )

def test_expansion():
    # Vista di supporto per test manuali (non registrata come route).
    ordini = esegui_query(
        """
        SELECT o.id, o.nome_cliente, o.numero_tavolo, o.numero_persone, o.data_ordine, o.metodo_pagamento,
               COALESCE(SUM(p.prezzo * op.quantita), 0) as totale
        FROM ordini o
        LEFT JOIN ordini_prodotti op ON o.id = op.ordine_id
        LEFT JOIN prodotti p ON op.prodotto_id = p.id
        GROUP BY o.id
        ORDER BY o.data_ordine DESC
        LIMIT 5
        """
    )
    return render_template("test_row_expansion.html", ordini=ordini)

@app.route("/api/ordine/<int:id_ordine>")
def api_ordine(id_ordine):
    # Restituisce intestazione e righe dell'ordine in JSON.
    # Prima: intestazione ordine (metadati).
    intestazione = esegui_query(
        """
        SELECT id, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento, data_ordine
        FROM ordini
        WHERE id = ?
        """,
        (id_ordine,),
        uno=True,
    )
    if not intestazione:
        # Ordine inesistente.
        abort(404)

    # Seconda: righe prodotti associate.
    righe_articoli = esegui_query(
        """
        SELECT p.nome AS nome, op.quantita AS quantita, p.prezzo AS prezzo
        FROM ordini_prodotti op
        JOIN prodotti p ON p.id = op.prodotto_id
        WHERE op.ordine_id = ?
        """,
        (id_ordine,),
    )
    # Converte le righe in una lista di dict semplici.
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
    is_admin = 1 if dati.get("is_admin") else 0
    attivo = 1 if dati.get("attivo") else 0
    permessi = dati.get("permessi", [])

    if not username or not password:
        return jsonify({"errore": "Username e password obbligatori"}), 400

    # Normalizza permessi: lista di stringhe uniche non vuote.
    if not isinstance(permessi, list):
        permessi = []
    permessi = [p.strip() for p in permessi if isinstance(p, str) and p.strip()]
    permessi = list(dict.fromkeys(permessi))

    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()

            # Evita duplicati username.
            cursore.execute("SELECT id FROM utenti WHERE username = ?", (username,))
            if cursore.fetchone():
                return jsonify({"errore": "Username già in uso"}), 400

            # Genera hash password (rounds bassi per ambienti limitati).
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()

            # Inserisce utente.
            cursore.execute("""
                INSERT INTO utenti (username, password_hash, is_admin, attivo)
                VALUES (?, ?, ?, ?)
            """, (username, password_hash, is_admin, attivo))
            
            id_utente = cursore.lastrowid

            # Inserisce permessi associati.
            for pagina in permessi:
                cursore.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)", (id_utente, pagina))
            
            connessione.commit()

        # Traccia in console l'azione amministrativa per audit e debugging.
        app.logger.info(
            "ADMIN utente_creato attore_id=%s attore=%s id_utente=%s username=%s is_admin=%s attivo=%s permessi=%s",
            # Identifica l'utente che sta operando da amministrazione.
            session.get("id_utente"),
            session.get("user_cache_username") or session.get("username"),
            # Dati account creato e permessi assegnati.
            id_utente,
            username,
            is_admin,
            attivo,
            permessi,
        )
        return jsonify({"messaggio": "Utente creato con successo"})
    except Exception:
        app.logger.exception("Errore aggiunta utente")
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
        is_admin = 1 if dati.get("is_admin") else 0
        attivo = 1 if dati.get("attivo") else 0
        permessi = dati.get("permessi", [])

        # Normalizza permessi.
        if not isinstance(permessi, list):
            permessi = []
        permessi = [p.strip() for p in permessi if isinstance(p, str) and p.strip()]
        permessi = list(dict.fromkeys(permessi))

        with ottieni_db() as connessione:
            cursore = connessione.cursor()

            if password:
                # Se presente, aggiorna anche la password.
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

            # Sostituisce l'insieme permessi.
            cursore.execute("DELETE FROM permessi_pagine WHERE utente_id = ?", (id_utente,))
            
            for pagina in permessi:
                cursore.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)", (id_utente, pagina))

            connessione.commit()

        # Traccia in console l'azione amministrativa per audit e debugging.
        app.logger.info(
            "ADMIN utente_modificato attore_id=%s attore=%s id_utente=%s username=%s is_admin=%s attivo=%s permessi=%s password_aggiornata=%s",
            # Identifica l'utente che sta operando da amministrazione.
            session.get("id_utente"),
            session.get("user_cache_username") or session.get("username"),
            # Dati account aggiornato e permessi assegnati.
            id_utente,
            username,
            is_admin,
            attivo,
            permessi,
            # Indica se la password è stata anche aggiornata.
            bool(password),
        )
        return jsonify({"messaggio": "Utente modificato con successo"})
    except Exception:
        app.logger.exception("Errore modifica utente")
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
    if "user_id" in session and str(session["user_id"]) == str(id_utente):
        # Protezione contro l'auto-eliminazione.
        return jsonify({"errore": "Non puoi eliminare il tuo stesso account"}), 400

    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()
            
            # Verifica che l'utente esista.
            cursore.execute("SELECT id FROM utenti WHERE id = ?", (id_utente,))
            if not cursore.fetchone():
                return jsonify({"errore": "Utente non trovato"}), 404

            # Elimina permessi e poi utente.
            cursore.execute("DELETE FROM permessi_pagine WHERE utente_id = ?", (id_utente,))
            cursore.execute("DELETE FROM utenti WHERE id = ?", (id_utente,))

            connessione.commit()

        # Traccia in console l'azione amministrativa per audit e debugging.
        app.logger.info(
            "ADMIN utente_eliminato attore_id=%s attore=%s id_utente=%s",
            # Identifica l'utente che sta operando da amministrazione.
            session.get("id_utente"),
            session.get("user_cache_username") or session.get("username"),
            # Account eliminato (id).
            id_utente,
        )
        return jsonify({"messaggio": "Utente eliminato con successo"})
    except Exception:
        app.logger.exception("Errore eliminazione utente")
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
        ORDER BY categoria_menu;
    """)
    
    # Calcola la prima categoria per inizializzare il pannello UI.
    categorie_db = esegui_query("SELECT DISTINCT categoria_menu FROM prodotti ORDER BY categoria_menu")
    categorie = [riga["categoria_menu"] for riga in categorie_db]
    prima_categoria = categorie[0] if categorie else None

    return render_template(
        "partials/_amministrazione_prodotti_rows.html",
        prodotti=prodotti,
        prima_categoria=prima_categoria,
    )

# ==================== Route: utilità ====================

@app.route("/genera_statistiche/")
def genera_statistiche():
    # Forza un ricalcolo statistiche e torna alla pagina amministrazione.
    # Utile quando si vogliono aggiornare i grafici manualmente.
    ricalcola_statistiche()
    return redirect("/amministrazione/")

@app.route("/debug/reset_dati/")
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def debug_reset_dati():
    # Utility di debug: azzera ordini e ripristina magazzino.
    # Attenzione: cancella dati in modo irreversibile nel DB corrente.
    esegui_query("DELETE FROM ordini_prodotti", commit=True)
    esegui_query("DELETE FROM ordini", commit=True)
    esegui_query("UPDATE prodotti SET disponibile = 1, quantita = 100, venduti = 0", commit=True)
    ricalcola_statistiche()
    return redirect("/amministrazione/")

# ==================== Avvio server ====================

if __name__ == "__main__":
    # Calcola un IP locale "ragionevole" per stampare l'URL di avvio.
    socket_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        socket_udp.connect(("8.8.8.8", 80))
        ip_locale = socket_udp.getsockname()[0]
    except Exception:
        ip_locale = "127.0.0.1"
    finally:
        socket_udp.close()
    modalita_debug = os.getenv("DEBUG", "False").lower() == "true"
    socketio.run(app, host="0.0.0.0", port=8000, debug=modalita_debug)
