import logging

from flask import jsonify, request, session

from app.auth import accesso_richiesto, richiedi_permesso
from app import app
from app.db import esegui_query
from app.services import carica_prodotti, notifica_e_ricalcola

logger = logging.getLogger(__name__)


@app.route("/api/prodotti", methods=["GET"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def lista_prodotti():
    prodotti, categorie, prima_categoria = carica_prodotti()
    return jsonify({
        "prima_categoria": prima_categoria,
        "prodotti": [
            {
                "id": p["id"],
                "nome": p["nome"],
                "categoria_dashboard": p["categoria_dashboard"],
                "categoria_menu": p["categoria_menu"],
                "prezzo": float(p["prezzo"]),
                "disponibile": bool(p["disponibile"]),
                "quantita": p["quantita"],
                "venduti": p["venduti"],
            }
            for p in prodotti
        ],
    })


@app.route("/api/prodotti", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def aggiungi_prodotto():
    dati = request.get_json()
    try:
        nome = dati.get("nome")
        categoria_dashboard = dati.get("categoria_dashboard")
        categoria_menu = dati.get("categoria_menu")
        prezzo = float(dati.get("prezzo", 0))
        quantita = int(dati.get("quantita", 0))
        disponibile = bool(dati.get("disponibile"))

        if not nome or not categoria_dashboard or not categoria_menu:
            logger.warning("Tentativo di aggiunta prodotto con dati mancanti - utente: '%s'", session.get("username"))
            return jsonify({"errore": "Dati mancanti"}), 400

        if quantita > 0:
            disponibile = True

        esegui_query(
            """
            INSERT INTO prodotti (nome, categoria_dashboard, categoria_menu, prezzo, quantita, disponibile, venduti)
            VALUES (%s, %s, %s, %s, %s, %s, 0)
            """,
            (nome, categoria_dashboard, categoria_menu, prezzo, quantita, disponibile),
            commit=True,
        )
        logger.info(
            "Prodotto aggiunto: '%s' (€%.2f, categoria: %s/%s, quantita: %s) - utente: '%s'",
            nome, prezzo, categoria_menu, categoria_dashboard, quantita, session.get("username"),
        )
        notifica_e_ricalcola()
        return jsonify({"messaggio": "Prodotto aggiunto con successo"}), 201

    except Exception as e:
        logger.error("Errore durante l'aggiunta del prodotto - utente: '%s': %s", session.get("username"), e)
        return jsonify({"errore": "Errore durante l'aggiunta"}), 500


@app.route("/api/prodotti/<int:id_prodotto>", methods=["PUT"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def modifica_prodotto(id_prodotto):
    dati = request.get_json()
    try:
        quantita = int(dati["quantita"])
        prezzo = float(dati["prezzo"])
        disponibile = quantita > 0

        esegui_query(
            """
            UPDATE prodotti
            SET nome = %s, categoria_dashboard = %s, prezzo = %s, quantita = %s, disponibile = %s
            WHERE id = %s
            """,
            (dati["nome"], dati["categoria_dashboard"], prezzo, quantita, disponibile, id_prodotto),
            commit=True,
        )
        logger.info(
            "Prodotto #%s modificato: '%s' (€%.2f, quantita: %s) - utente: '%s'",
            id_prodotto, dati["nome"], prezzo, quantita, session.get("username"),
        )
        notifica_e_ricalcola()
        return jsonify({"messaggio": "Prodotto modificato con successo"})

    except Exception as e:
        logger.error(
            "Errore durante la modifica del prodotto #%s - utente: '%s': %s",
            id_prodotto, session.get("username"), e,
        )
        return jsonify({"errore": "Errore durante la modifica"}), 500


@app.route("/api/prodotti/<int:id_prodotto>/rifornimento", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def rifornisci_prodotto(id_prodotto):
    dati = request.get_json()
    try:
        quantita = int(dati.get("quantita"))
    except (ValueError, TypeError):
        return jsonify({"errore": "Quantità non valida"}), 400

    if quantita <= 0:
        logger.warning("Rifornimento prodotto con quantità non valida - utente: '%s'", session.get("username"))
        return jsonify({"errore": "Quantità deve essere maggiore di zero"}), 400

    esegui_query(
        "UPDATE prodotti SET quantita = quantita + %s WHERE id = %s",
        (quantita, id_prodotto),
        commit=True,
    )
    esegui_query(
        "UPDATE prodotti SET disponibile = TRUE WHERE id = %s AND quantita > 0",
        (id_prodotto,),
        commit=True,
    )
    logger.info("Prodotto #%s rifornito di %s unità - utente: '%s'", id_prodotto, quantita, session.get("username"))
    notifica_e_ricalcola()
    return jsonify({"messaggio": "Prodotto rifornito con successo"})


@app.route("/api/prodotti/<int:id_prodotto>", methods=["DELETE"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def elimina_prodotto(id_prodotto):
    try:
        esegui_query("DELETE FROM prodotti WHERE id = %s", (id_prodotto,), commit=True)
        logger.info("Prodotto #%s eliminato - utente: '%s'", id_prodotto, session.get("username"))
        notifica_e_ricalcola()
        return "", 204

    except Exception as e:
        logger.error(
            "Errore durante l'eliminazione del prodotto #%s - utente: '%s': %s",
            id_prodotto, session.get("username"), e,
        )
        return jsonify({"errore": "Errore durante l'eliminazione"}), 500
