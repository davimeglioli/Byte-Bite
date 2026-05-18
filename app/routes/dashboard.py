import logging
import uuid

from flask import jsonify, render_template

from app.auth import accesso_richiesto, richiedi_permesso
from app import app, socketio, timer_attivi
from app.db import esegui_query
from app.services import cambia_stato_automatico, notifica_e_ricalcola, ottieni_ordini_per_categoria

logger = logging.getLogger(__name__)

_STATI = ["In Attesa", "In Preparazione", "Pronto", "Completato"]


@app.route("/dashboard/<category>/")
@accesso_richiesto
@richiedi_permesso("DASHBOARD")
def dashboard(category):
    ordini_non_completati, ordini_completati = ottieni_ordini_per_categoria(category)
    return render_template(
        "dashboard.html",
        category=category.capitalize(),
        ordini_non_completati=ordini_non_completati,
        ordini_completati=ordini_completati,
    )


@app.route("/api/ordini/categoria/<category>")
@accesso_richiesto
@richiedi_permesso("DASHBOARD")
def dashboard_parziale(category):
    ordini_non_completati, ordini_completati = ottieni_ordini_per_categoria(category)

    def serializza(lista):
        return [
            {
                "id": o["id"],
                "nome_cliente": o["nome_cliente"],
                "numero_tavolo": o["numero_tavolo"],
                "numero_persone": o["numero_persone"],
                "data_ordine": o["data_ordine"].strftime("%H:%M"),
                "stato": o["stato"],
                "prodotti": o["prodotti"],
            }
            for o in lista
        ]

    return jsonify({
        "non_completati": serializza(ordini_non_completati),
        "completati": serializza(ordini_completati),
    })


@app.route("/api/ordini/<int:id_ordine>/stato/<categoria>", methods=["PATCH"])
@accesso_richiesto
@richiedi_permesso("DASHBOARD")
def cambia_stato(id_ordine, categoria):
    riga_stato = esegui_query(
        """
        SELECT stato
        FROM ordini_prodotti
        JOIN prodotti ON prodotti.id = ordini_prodotti.prodotto_id
        WHERE ordine_id = %s AND prodotti.categoria_dashboard = %s
        LIMIT 1
        """,
        (id_ordine, categoria),
        uno=True,
    )

    if not riga_stato:
        logger.warning("Cambio stato fallito - ordine #%s o categoria '%s' non trovata", id_ordine, categoria)
        return jsonify({"errore": "Ordine o categoria non trovata"}), 404

    stato_attuale = riga_stato["stato"]
    chiave_timer = (id_ordine, categoria)

    if stato_attuale == "Completato":
        logger.warning("Cambio stato rifiutato - ordine #%s [%s] già completato", id_ordine, categoria)
        return jsonify({"errore": "Ordine già completato"}), 400

    if stato_attuale == "Pronto":
        # Click on "Pronto" steps back to "In Preparazione" and cancels the auto-complete timer.
        if chiave_timer in timer_attivi:
            timer_attivi[chiave_timer]["annulla"] = True
            del timer_attivi[chiave_timer]
        nuovo_stato = "In Preparazione"
    else:
        nuovo_stato = _STATI[_STATI.index(stato_attuale) + 1]

    esegui_query(
        """
        UPDATE ordini_prodotti
        SET stato = %s
        WHERE ordine_id = %s
        AND prodotto_id IN (
            SELECT id FROM prodotti WHERE categoria_dashboard = %s
        )
        """,
        (nuovo_stato, id_ordine, categoria),
        commit=True,
    )

    logger.info("Stato ordine #%s [%s]: '%s' → '%s'", id_ordine, categoria, stato_attuale, nuovo_stato)

    residui = esegui_query(
        "SELECT COUNT(*) AS c FROM ordini_prodotti WHERE ordine_id = %s AND stato != 'Completato'",
        (id_ordine,),
        uno=True,
    )["c"]
    esegui_query(
        "UPDATE ordini SET completato = %s WHERE id = %s",
        (residui == 0, id_ordine),
        commit=True,
    )

    notifica_e_ricalcola(categoria)

    if nuovo_stato == "Pronto":
        # Cancel any existing timer for this order+category before starting a new one.
        if chiave_timer in timer_attivi:
            timer_attivi[chiave_timer]["annulla"] = True
            timer_attivi.pop(chiave_timer, None)

        id_timer = str(uuid.uuid4())
        timer_attivi[chiave_timer] = {"annulla": False, "id": id_timer}
        socketio.start_background_task(cambia_stato_automatico, id_ordine, categoria, id_timer)

    return jsonify({"nuovo_stato": nuovo_stato})
