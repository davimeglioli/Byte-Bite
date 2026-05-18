import copy
import logging
import threading

from flask_socketio import join_room

from app import app, socketio, timer_attivi
from app.db import esegui_query

logger = logging.getLogger(__name__)

_statistiche_cache = None
_statistiche_lock = threading.RLock()

_TIMEOUT_AUTO_COMPLETAMENTO_SEC = 10


def emissione_sicura(evento, dati, stanza=None):
    try:
        socketio.emit(evento, dati, room=stanza)
        if stanza and stanza != "amministrazione" and evento == "aggiorna_dashboard":
            # Replica to the amministrazione room so the admin panel stays in sync.
            socketio.emit(evento, dati, room="amministrazione")
    except Exception as e:
        logger.error("Errore durante l'emissione dell'evento SocketIO '%s' (stanza: %s): %s", evento, stanza, e)


def notifica_e_ricalcola(*categorie):
    """Emette aggiorna_dashboard e avvia il ricalcolo statistiche in background.

    Senza argomenti notifica la stanza 'amministrazione'.
    Con una o più categorie notifica ciascuna stanza di categoria.
    """
    if categorie:
        for cat in categorie:
            emissione_sicura("aggiorna_dashboard", {"categoria": cat}, stanza=cat)
    else:
        emissione_sicura("aggiorna_dashboard", {}, stanza="amministrazione")
    socketio.start_background_task(ricalcola_statistiche)


@socketio.on("join")
def gestisci_join(dati):
    categoria = dati.get("categoria")
    if categoria:
        join_room(categoria)
        logger.debug("Client iscritto alla stanza '%s'", categoria)


def ottieni_ordini_per_categoria(categoria):
    # capitalize() aligns the URL segment with the DB-stored category name.
    categoria = categoria.capitalize()

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
        ORDER BY o.data_ordine ASC
        """,
        (categoria,),
    )

    ordini = {}
    for riga in ordini_db:
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

    ordini_non_completati = []
    ordini_completati = []
    for ordine in ordini.values():
        if ordine["stato"] == "Completato":
            ordini_completati.append(ordine)
        else:
            ordini_non_completati.append(ordine)

    ordini_completati.sort(key=lambda o: o["data_ordine"], reverse=True)
    return ordini_non_completati, ordini_completati


def carica_ordini():
    return esegui_query("""
        SELECT o.id, o.nome_cliente, o.numero_tavolo, o.numero_persone, o.data_ordine, o.metodo_pagamento,
               COALESCE(SUM(p.prezzo * op.quantita), 0) AS totale
        FROM ordini o
        LEFT JOIN ordini_prodotti op ON o.id = op.ordine_id
        LEFT JOIN prodotti p ON op.prodotto_id = p.id
        GROUP BY o.id
        ORDER BY o.data_ordine DESC
    """)


def carica_prodotti():
    prodotti = esegui_query("""
        SELECT id, nome, categoria_dashboard, categoria_menu, prezzo, disponibile, quantita, venduti
        FROM prodotti
        ORDER BY MIN(id) OVER (PARTITION BY categoria_menu), id
    """)
    categorie_db = esegui_query(
        "SELECT categoria_menu FROM prodotti GROUP BY categoria_menu ORDER BY MIN(id)"
    )
    categorie = [r["categoria_menu"] for r in categorie_db]
    return prodotti, categorie, categorie[0] if categorie else None


def _calcola_dati_statistiche_da_db():
    ordini_totali = esegui_query("SELECT COUNT(*) AS c FROM ordini", uno=True)["c"]
    ordini_completati = esegui_query("SELECT COUNT(*) AS c FROM ordini WHERE completato = TRUE", uno=True)["c"]

    riga_totale_incasso = esegui_query(
        """
        SELECT SUM(p.prezzo * op.quantita) AS totale
        FROM ordini_prodotti op
        JOIN prodotti p ON p.id = op.prodotto_id
        """,
        uno=True,
    )
    totale_incasso = float(riga_totale_incasso["totale"] or 0)

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

    righe_ore = esegui_query(
        """
        SELECT EXTRACT(HOUR FROM data_ordine)::INT AS ora, COUNT(*) AS totale
        FROM ordini
        GROUP BY EXTRACT(HOUR FROM data_ordine)
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
    categorie = [
        {"categoria_dashboard": r["categoria_dashboard"], "totale": int(r["totale"])}
        for r in righe_cat
    ] if righe_cat else []

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
    global _statistiche_cache
    logger.debug("Ricalcolo statistiche avviato")
    nuovi_dati = _calcola_dati_statistiche_da_db()
    with _statistiche_lock:
        # Deep copy prevents accidental mutation by callers sharing the cached object.
        _statistiche_cache = copy.deepcopy(nuovi_dati)
    logger.debug(
        "Statistiche ricalcolate - ordini totali: %s, incasso: %.2f EUR",
        nuovi_dati["totali"]["ordini_totali"],
        nuovi_dati["totali"]["totale_incasso"],
    )
    if notifica:
        emissione_sicura("aggiorna_dashboard", {})


def cambia_stato_automatico(ordine_id, categoria, id_timer):
    chiave_timer = (ordine_id, categoria)

    for _ in range(_TIMEOUT_AUTO_COMPLETAMENTO_SEC):
        socketio.sleep(1)  # Cooperative sleep — does not block the SocketIO event loop.
        if (
            chiave_timer not in timer_attivi
            or timer_attivi[chiave_timer]["id"] != id_timer
            or timer_attivi[chiave_timer]["annulla"]
        ):
            logger.debug("Timer annullato per ordine #%s [%s]", ordine_id, categoria)
            return

    # Re-check after the timeout: a newer "Pronto" click replaces the entry with a new id.
    if (
        chiave_timer not in timer_attivi
        or timer_attivi[chiave_timer]["annulla"]
        or timer_attivi[chiave_timer]["id"] != id_timer
    ):
        logger.debug("Timer annullato prima del completamento per ordine #%s [%s]", ordine_id, categoria)
        return

    esegui_query(
        """
        UPDATE ordini_prodotti
        SET stato = 'Completato'
        WHERE ordine_id = %s
        AND prodotto_id IN (
            SELECT id FROM prodotti WHERE categoria_dashboard = %s
        )
        """,
        (ordine_id, categoria),
        commit=True,
    )

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

    timer_attivi.pop(chiave_timer, None)
    # Run stats update in background to avoid delaying the realtime UI update.
    notifica_e_ricalcola(categoria)


def costruisci_dati_statistiche():
    global _statistiche_cache
    with _statistiche_lock:
        if _statistiche_cache is not None:
            return copy.deepcopy(_statistiche_cache)

    # First access after restart: compute once, then serve from cache on subsequent calls.
    ricalcola_statistiche(notifica=False)
    with _statistiche_lock:
        return copy.deepcopy(_statistiche_cache or {})
