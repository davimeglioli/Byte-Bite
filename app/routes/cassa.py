import logging

from flask import jsonify, render_template, request, session

from app.auth import accesso_richiesto, richiedi_permesso
from app import app
from app.db import esegui_query, ottieni_db
from app.services import notifica_e_ricalcola

logger = logging.getLogger(__name__)


@app.route("/cassa/")
@accesso_richiesto
@richiedi_permesso("CASSA")
def cassa():
    tutti_prodotti = esegui_query("SELECT * FROM prodotti ORDER BY id")
    categorie = []
    prodotti_per_categoria = {}
    for prodotto in tutti_prodotti:
        categoria = prodotto["categoria_menu"]
        if categoria not in prodotti_per_categoria:
            categorie.append(categoria)
            prodotti_per_categoria[categoria] = []
        prodotti_per_categoria[categoria].append(prodotto)
    return render_template("cassa.html", categorie=categorie, prodotti_per_categoria=prodotti_per_categoria)


@app.route("/api/ordini", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("CASSA")
def aggiungi_ordine():
    dati = request.get_json()

    asporto = bool(dati.get("asporto"))
    nome_cliente = dati.get("nome_cliente")
    metodo_pagamento = dati.get("metodo_pagamento")
    prodotti = dati.get("prodotti", [])
    numero_tavolo = None if asporto else (dati.get("numero_tavolo") or None)
    numero_persone = None if asporto else (dati.get("numero_persone") or None)

    if not prodotti:
        logger.warning("Tentativo di creare ordine senza prodotti - utente: '%s'", session.get("username"))
        return jsonify({"errore": "Nessun prodotto selezionato"}), 400

    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()
            cursore.execute(
                """
                INSERT INTO ordini (asporto, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (asporto, nome_cliente, numero_tavolo, numero_persone, metodo_pagamento),
            )
            id_ordine = cursore.fetchone()["id"]

            for prodotto in prodotti:
                cursore.execute(
                    """
                    UPDATE prodotti
                    SET quantita = quantita - %s, venduti = venduti + %s
                    WHERE id = %s AND quantita >= %s
                    """,
                    (prodotto["quantita"], prodotto["quantita"], prodotto["id"], prodotto["quantita"]),
                )
                if cursore.rowcount == 0:
                    # rowcount 0 means stock was insufficient — abort the whole transaction.
                    nome_prodotto = prodotto.get("nome", "Sconosciuto")
                    logger.warning(
                        "Stock insufficiente per prodotto '%s' (ID: %s) - ordine annullato",
                        nome_prodotto, prodotto.get("id"),
                    )
                    raise Exception(f"Prodotto {nome_prodotto} esaurito o insufficiente.")

                cursore.execute(
                    "INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita, stato) VALUES (%s, %s, %s, %s)",
                    (id_ordine, prodotto["id"], prodotto["quantita"], "In Attesa"),
                )

            cursore.execute(
                """
                SELECT DISTINCT prodotti.categoria_dashboard
                FROM ordini_prodotti
                JOIN prodotti ON prodotti.id = ordini_prodotti.prodotto_id
                WHERE ordini_prodotti.ordine_id = %s
                """,
                (id_ordine,),
            )
            categorie_dashboard = [r["categoria_dashboard"] for r in cursore.fetchall()]
            connessione.commit()

        logger.info(
            "Nuovo ordine #%s creato - cliente: '%s', prodotti: %s, asporto: %s, pagamento: %s, utente: '%s'",
            id_ordine, nome_cliente, len(prodotti), asporto, metodo_pagamento, session.get("username"),
        )
        notifica_e_ricalcola(*categorie_dashboard)
        return jsonify({"messaggio": "Ordine creato con successo"}), 201

    except Exception as errore:
        logger.error("Errore durante la creazione dell'ordine - utente: '%s': %s", session.get("username"), errore)
        return jsonify({"errore": str(errore)}), 500
