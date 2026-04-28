import copy
import logging
import threading

from flask_socketio import join_room

from core import app, socketio, timer_attivi
from db import esegui_query

logger = logging.getLogger(__name__)

# Cache in-memory per statistiche amministrazione.
_statistiche_cache = None
_statistiche_lock = threading.RLock()


def emissione_sicura(evento, dati, stanza=None):
    """Invia un messaggio SocketIO gestendo eventuali errori."""
    try:
        # Invia l'evento alla stanza richiesta (o broadcast se stanza è None).
        socketio.emit(evento, dati, room=stanza)
        if stanza and stanza != "amministrazione" and evento == "aggiorna_dashboard":
            # Replica l'aggiornamento anche all'area amministrazione.
            socketio.emit(evento, dati, room="amministrazione")
    except Exception as e:
        logger.error("Errore durante l'emissione dell'evento SocketIO '%s' (stanza: %s): %s", evento, stanza, e)


@socketio.on("join")
def gestisci_join(dati):
    """Gestisce l'ingresso di un client in una stanza SocketIO."""
    # Ogni dashboard si iscrive alla sua categoria per ricevere solo eventi utili.
    categoria = dati.get("categoria")
    if categoria:
        # Iscrive la connessione alla stanza (es. Bar, Cucina, Griglia).
        join_room(categoria)
        logger.debug("Client iscritto alla stanza '%s'", categoria)


def ottieni_ordini_per_categoria(categoria):
    """Recupera gli ordini (completati e non) per una specifica categoria."""
    # Normalizza il nome categoria così coincide con il valore salvato a DB.
    categoria = categoria.capitalize()

    # Estrae righe ordine-prodotto e le ordina cronologicamente.
    ordini_db = esegui_query(
        """
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
        WHERE p.categoria_dashboard = %s
        ORDER BY o.data_ordine ASC;
    """,
        (categoria,),
    )

    # Raggruppa le righe per ordine per costruire la struttura attesa dai template.
    ordini = {}
    for riga in ordini_db:
        # Chiave di aggregazione: id ordine.
        id_ordine = riga["ordine_id"]
        ordini.setdefault(
            id_ordine,
            {
                "id": id_ordine,
                "nome_cliente": riga["nome_cliente"],
                "numero_tavolo": riga["numero_tavolo"],
                "numero_persone": riga["numero_persone"],
                "data_ordine": riga["data_ordine"],
                "stato": riga["stato"],
                "prodotti": [],
            },
        )["prodotti"].append({"nome": riga["prodotto_nome"], "quantita": riga["quantita"]})

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


def _calcola_dati_statistiche_da_db():
    """Calcola le statistiche direttamente dalle tabelle operative."""
    # Numero ordini totali e completati.
    ordini_totali = esegui_query("SELECT COUNT(*) AS c FROM ordini", uno=True)["c"]
    ordini_completati = esegui_query("SELECT COUNT(*) AS c FROM ordini WHERE completato = TRUE", uno=True)["c"]

    # Totale incasso indipendentemente dal metodo.
    riga_totale_incasso = esegui_query(
        """
        SELECT SUM(p.prezzo * op.quantita) AS totale
        FROM ordini_prodotti op
        JOIN prodotti p ON p.id = op.prodotto_id
        """,
        uno=True,
    )
    totale_incasso = float(riga_totale_incasso["totale"] or 0)

    # Totale pagato in contanti.
    riga_totale_contanti = esegui_query(
        """
        SELECT SUM(p.prezzo * op.quantita) AS totale
        FROM ordini_prodotti op
        JOIN prodotti p ON p.id = op.prodotto_id
        JOIN ordini o ON o.id = op.ordine_id
        WHERE o.metodo_pagamento = 'Contanti'
        """,
        uno=True,
    )
    totale_contanti = float(riga_totale_contanti["totale"] or 0)

    # Totale pagato con carta.
    riga_totale_carta = esegui_query(
        """
        SELECT SUM(p.prezzo * op.quantita) AS totale
        FROM ordini_prodotti op
        JOIN prodotti p ON p.id = op.prodotto_id
        JOIN ordini o ON o.id = op.ordine_id
        WHERE o.metodo_pagamento = 'Carta'
        """,
        uno=True,
    )
    totale_carta = float(riga_totale_carta["totale"] or 0)

    # Distribuzione ordini per ora.
    righe_ore = esegui_query(
        """
        SELECT EXTRACT(HOUR FROM data_ordine)::INT AS ora, COUNT(*) AS totale
        FROM ordini
        GROUP BY EXTRACT(HOUR FROM data_ordine)
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
    categorie = [{"categoria_dashboard": r["categoria_dashboard"], "totale": int(r["totale"])} for r in righe_cat] if righe_cat else []

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
            "totale_carta": totale_carta,
        },
        "categorie": categorie,
        "ore": ore,
        "top10": top10,
    }


def ricalcola_statistiche(notifica=True):
    """Ricalcola le statistiche e aggiorna la cache in memoria."""
    global _statistiche_cache
    logger.debug("Ricalcolo statistiche avviato")
    nuovi_dati = _calcola_dati_statistiche_da_db()
    with _statistiche_lock:
        # Salva una copia isolata per evitare mutazioni accidentali dal chiamante.
        _statistiche_cache = copy.deepcopy(nuovi_dati)
    logger.debug("Statistiche ricalcolate - ordini totali: %s, incasso: %.2f EUR",
                 nuovi_dati["totali"]["ordini_totali"],
                 nuovi_dati["totali"]["totale_incasso"])
    if notifica:
        emissione_sicura("aggiorna_dashboard", {})


def cambia_stato_automatico(ordine_id, categoria, id_timer):
    """Gestisce il passaggio automatico allo stato 'Completato' dopo un timeout."""
    chiave_timer = (ordine_id, categoria)

    # Attende un breve timeout (con possibilità di annullamento).
    for _ in range(10):
        # Sleep cooperativo per non bloccare l'event loop SocketIO.
        socketio.sleep(1)
        if (
            chiave_timer not in timer_attivi
            or timer_attivi[chiave_timer]["id"] != id_timer
            or timer_attivi[chiave_timer]["annulla"]
        ):
            logger.debug("Timer annullato per ordine #%s [%s]", ordine_id, categoria)
            return

    # Ricontrolla lo stato del timer prima di aggiornare il DB.
    if chiave_timer not in timer_attivi or timer_attivi[chiave_timer]["annulla"]:
        logger.debug("Timer annullato prima del completamento per ordine #%s [%s]", ordine_id, categoria)
        return

    # Forza lo stato "Completato" per tutti i prodotti della categoria.
    esegui_query(
        """
        UPDATE ordini_prodotti
        SET stato = 'Completato'
        WHERE ordine_id = %s
        AND prodotto_id IN (
            SELECT id FROM prodotti WHERE categoria_dashboard = %s
        );
    """,
        (ordine_id, categoria),
        commit=True,
    )

    # Aggiorna il flag completato dell'ordine se non restano prodotti non completati.
    residui = esegui_query(
        "SELECT COUNT(*) AS c FROM ordini_prodotti WHERE ordine_id = %s AND stato != 'Completato'",
        (ordine_id,),
        uno=True,
    )["c"]
    esegui_query(
        "UPDATE ordini SET completato = %s WHERE id = %s",
        (residui == 0, ordine_id),
        commit=True,
    )

    logger.info("Completamento automatico ordine #%s [%s] - residui non completati: %s", ordine_id, categoria, residui)

    # Rimuove il timer e notifica la dashboard interessata.
    timer_attivi.pop(chiave_timer, None)

    emissione_sicura("aggiorna_dashboard", {"categoria": categoria}, stanza=categoria)
    # Aggiorna statistiche in background per non rallentare gli update realtime.
    socketio.start_background_task(ricalcola_statistiche)


def costruisci_dati_statistiche():
    """Restituisce le statistiche dalla cache RAM (lazy init al primo uso)."""
    global _statistiche_cache
    with _statistiche_lock:
        if _statistiche_cache is not None:
            return copy.deepcopy(_statistiche_cache)

    # Primo accesso dopo riavvio: calcolo una volta e riuso poi la cache.
    ricalcola_statistiche(notifica=False)
    with _statistiche_lock:
        return copy.deepcopy(_statistiche_cache or {})
