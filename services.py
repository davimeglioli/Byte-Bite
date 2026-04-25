from flask_socketio import join_room

from core import app, socketio, timer_attivi
from db import esegui_query, ottieni_db


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
        WHERE p.categoria_dashboard = ?
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


def ricalcola_statistiche():
    """Ricalcola tutte le statistiche e le salva nel database."""

    # Calcola i totali complessivi e per metodo di pagamento.
    statistiche_totali = esegui_query(
        """
        SELECT
            (SELECT COUNT(*) FROM ordini) as ordini_totali,
            (SELECT COUNT(*) FROM ordini WHERE completato = 1) as ordini_completati,
            COALESCE(SUM(p.prezzo * op.quantita), 0) as totale_incasso,
            COALESCE(SUM(CASE WHEN o.metodo_pagamento = 'Contanti' THEN p.prezzo * op.quantita ELSE 0 END), 0) as totale_contanti,
            COALESCE(SUM(CASE WHEN o.metodo_pagamento != 'Contanti' THEN p.prezzo * op.quantita ELSE 0 END), 0) as totale_carta
        FROM ordini o
        JOIN ordini_prodotti op ON o.id = op.ordine_id
        JOIN prodotti p ON op.prodotto_id = p.id
    """,
        uno=True,
    )

    # Calcola i volumi per categoria dashboard.
    statistiche_categorie = esegui_query(
        """
        SELECT p.categoria_dashboard, SUM(op.quantita) as totale
        FROM ordini_prodotti op
        JOIN prodotti p ON op.prodotto_id = p.id
        GROUP BY p.categoria_dashboard
    """
    )

    # Calcola la distribuzione ordini per ora del giorno.
    statistiche_ore = esegui_query(
        """
        SELECT CAST(strftime('%H', data_ordine) AS INT) as ora, COUNT(*) as totale
        FROM ordini
        GROUP BY ora
    """
    )

    with ottieni_db() as connessione:
        cursore = connessione.cursor()

        # Rigenera completamente le tabelle statistiche per mantenere coerenza.
        cursore.execute("DELETE FROM statistiche_totali")
        cursore.execute("DELETE FROM statistiche_categorie")
        cursore.execute("DELETE FROM statistiche_ore")

        # Inserisce una sola riga per i totali generali.
        cursore.execute(
            """
            INSERT INTO statistiche_totali
            (id, ordini_totali, ordini_completati, totale_incasso, totale_contanti, totale_carta)
            VALUES (1, ?, ?, ?, ?, ?)
        """,
            (
                statistiche_totali["ordini_totali"] or 0,
                statistiche_totali["ordini_completati"] or 0,
                statistiche_totali["totale_incasso"],
                statistiche_totali["totale_contanti"],
                statistiche_totali["totale_carta"],
            ),
        )

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
    esegui_query(
        """
        UPDATE ordini_prodotti
        SET stato = 'Completato'
        WHERE ordine_id = ?
        AND prodotto_id IN (
            SELECT id FROM prodotti WHERE categoria_dashboard = ?
        );
    """,
        (ordine_id, categoria),
        commit=True,
    )

    # Aggiorna il flag completato dell'ordine se non restano prodotti non completati.
    residui = esegui_query(
        "SELECT COUNT(*) AS c FROM ordini_prodotti WHERE ordine_id = ? AND stato != 'Completato'",
        (ordine_id,),
        uno=True,
    )["c"]
    esegui_query(
        "UPDATE ordini SET completato = ? WHERE id = ?",
        (1 if residui == 0 else 0, ordine_id),
        commit=True,
    )

    # Rimuove il timer e notifica la dashboard interessata.
    timer_attivi.pop(chiave_timer, None)

    emissione_sicura("aggiorna_dashboard", {"categoria": categoria}, stanza=categoria)
    # Aggiorna statistiche in background per non rallentare gli update realtime.
    socketio.start_background_task(ricalcola_statistiche)


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
        uno=True,
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
        uno=True,
    )
    totale_contanti = riga_totale_contanti["totale"] or 0

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
    totale_carta = riga_totale_carta["totale"] or 0

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
            "totale_carta": totale_carta,
        },
        "categorie": categorie,
        "ore": ore,
        "top10": top10,
    }
