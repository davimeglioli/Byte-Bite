import logging

from flask import jsonify, request, session

from app.auth import accesso_richiesto, richiedi_permesso
from app import app
from app.db import esegui_query, ottieni_db
from app.services import carica_ordini, notifica_e_ricalcola

logger = logging.getLogger(__name__)


@app.route("/api/ordini", methods=["GET"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def lista_ordini():
    ordini = carica_ordini()
    return jsonify({
        "ordini": [
            {
                "id": o["id"],
                "nome_cliente": o["nome_cliente"],
                "numero_tavolo": o["numero_tavolo"],
                "numero_persone": o["numero_persone"],
                "data_ordine": o["data_ordine"].strftime("%d/%m/%Y %H:%M"),
                "metodo_pagamento": o["metodo_pagamento"],
                "totale": float(o["totale"]),
            }
            for o in ordini
        ]
    })


@app.route("/api/ordini/<int:id_ordine>", methods=["GET"])
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
        return jsonify({"errore": "Ordine non trovato"}), 404

    prodotti = esegui_query(
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
    totale = sum((r["subtotale"] or 0) for r in prodotti)
    return jsonify({
        "id": intestazione["id"],
        "nome_cliente": intestazione["nome_cliente"],
        "numero_tavolo": intestazione["numero_tavolo"],
        "numero_persone": intestazione["numero_persone"],
        "metodo_pagamento": intestazione["metodo_pagamento"],
        "data_ordine": intestazione["data_ordine"],
        "totale": float(totale),
        "prodotti": [
            {
                "nome": r["nome"],
                "categoria_menu": r["categoria_menu"],
                "quantita": r["quantita"],
                "prezzo": float(r["prezzo"]),
                "subtotale": float(r["subtotale"] or 0),
                "stato": r["stato"],
            }
            for r in prodotti
        ],
    })


@app.route("/api/ordini/<int:id_ordine>", methods=["PUT"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def modifica_ordine(id_ordine):
    dati = request.get_json()
    try:
        nome_cliente = dati.get("nome_cliente")
        numero_tavolo = dati.get("numero_tavolo") or None
        numero_persone = dati.get("numero_persone") or None
        metodo_pagamento = dati.get("metodo_pagamento")

        esegui_query(
            """
            UPDATE ordini
            SET nome_cliente = %s, numero_tavolo = %s, numero_persone = %s, metodo_pagamento = %s
            WHERE id = %s
            """,
            (nome_cliente, numero_tavolo, numero_persone, metodo_pagamento, id_ordine),
            commit=True,
        )
        logger.info(
            "Ordine #%s aggiornato - cliente: '%s', utente: '%s'",
            id_ordine, nome_cliente, session.get("username"),
        )
        notifica_e_ricalcola()
        return jsonify({"messaggio": "Ordine aggiornato con successo"})

    except Exception as e:
        logger.error(
            "Errore durante l'aggiornamento dell'ordine #%s - utente: '%s': %s",
            id_ordine, session.get("username"), e,
        )
        return jsonify({"errore": "Errore durante l'aggiornamento"}), 500


@app.route("/api/ordini/<int:id_ordine>", methods=["DELETE"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def elimina_ordine(id_ordine):
    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()

            cursore.execute(
                "SELECT prodotto_id, quantita FROM ordini_prodotti WHERE ordine_id = %s",
                (id_ordine,),
            )
            prodotti_ordine = cursore.fetchall()

            for prodotto in prodotti_ordine:
                prodotto_id = prodotto["prodotto_id"]
                quantita = prodotto["quantita"]
                cursore.execute(
                    "UPDATE prodotti SET quantita = quantita + %s, venduti = venduti - %s WHERE id = %s",
                    (quantita, quantita, prodotto_id),
                )
                cursore.execute(
                    "UPDATE prodotti SET disponibile = TRUE WHERE id = %s AND quantita > 0",
                    (prodotto_id,),
                )

            cursore.execute("DELETE FROM ordini_prodotti WHERE ordine_id = %s", (id_ordine,))
            cursore.execute("DELETE FROM ordini WHERE id = %s", (id_ordine,))
            connessione.commit()

        logger.info(
            "Ordine #%s eliminato con ripristino magazzino - utente: '%s'",
            id_ordine, session.get("username"),
        )
        notifica_e_ricalcola()
        return "", 204

    except Exception as e:
        logger.error(
            "Errore durante l'eliminazione dell'ordine #%s - utente: '%s': %s",
            id_ordine, session.get("username"), e,
        )
        return jsonify({"errore": "Errore durante l'eliminazione"}), 500
