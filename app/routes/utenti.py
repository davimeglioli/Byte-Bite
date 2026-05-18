import logging

import bcrypt
from flask import jsonify, request, session

from app.auth import accesso_richiesto, richiedi_permesso
from app import app
from app.db import ottieni_db

logger = logging.getLogger(__name__)


def _normalizza_permessi(permessi):
    if not isinstance(permessi, list):
        permessi = []
    return list(dict.fromkeys(p.strip() for p in permessi if isinstance(p, str) and p.strip()))


@app.route("/api/utenti", methods=["POST"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def aggiungi_utente():
    dati = request.get_json()

    username = dati.get("username")
    password = dati.get("password")
    is_admin = bool(dati.get("is_admin"))
    attivo = bool(dati.get("attivo"))
    permessi = _normalizza_permessi(dati.get("permessi", []))

    if not username or not password:
        return jsonify({"errore": "Username e password obbligatori"}), 400

    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()

            cursore.execute("SELECT id FROM utenti WHERE username = %s", (username,))
            if cursore.fetchone():
                logger.warning(
                    "Tentativo di creare utente con username già in uso: '%s' - operatore: '%s'",
                    username, session.get("username"),
                )
                return jsonify({"errore": "Username già in uso"}), 400

            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
            cursore.execute(
                """
                INSERT INTO utenti (username, password_hash, is_admin, attivo)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (username, password_hash, is_admin, attivo),
            )
            id_utente = cursore.fetchone()["id"]

            for pagina in permessi:
                cursore.execute(
                    "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
                    (id_utente, pagina),
                )
            connessione.commit()

        logger.info(
            "Nuovo utente creato: '%s' (ID: %s, admin: %s, permessi: %s) - operatore: '%s'",
            username, id_utente, is_admin, permessi, session.get("username"),
        )
        return jsonify({"messaggio": "Utente creato con successo"}), 201

    except Exception as e:
        logger.error(
            "Errore durante la creazione dell'utente '%s' - operatore: '%s': %s",
            username, session.get("username"), e,
        )
        return jsonify({"errore": "Errore durante la creazione"}), 500


@app.route("/api/utenti/<int:id_utente>", methods=["PUT"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def modifica_utente(id_utente):
    dati = request.get_json()
    try:
        username = dati.get("username")
        password = dati.get("password")
        is_admin = bool(dati.get("is_admin"))
        attivo = bool(dati.get("attivo"))
        permessi = _normalizza_permessi(dati.get("permessi", []))

        with ottieni_db() as connessione:
            cursore = connessione.cursor()

            if password:
                password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
                cursore.execute(
                    """
                    UPDATE utenti
                    SET username = %s, password_hash = %s, is_admin = %s, attivo = %s
                    WHERE id = %s
                    """,
                    (username, password_hash, is_admin, attivo, id_utente),
                )
            else:
                cursore.execute(
                    "UPDATE utenti SET username = %s, is_admin = %s, attivo = %s WHERE id = %s",
                    (username, is_admin, attivo, id_utente),
                )

            cursore.execute("DELETE FROM permessi_pagine WHERE utente_id = %s", (id_utente,))
            for pagina in permessi:
                cursore.execute(
                    "INSERT INTO permessi_pagine (utente_id, pagina) VALUES (%s, %s)",
                    (id_utente, pagina),
                )
            connessione.commit()

        logger.info(
            "Utente #%s modificato: '%s' (admin: %s, attivo: %s) - operatore: '%s'",
            id_utente, username, is_admin, attivo, session.get("username"),
        )
        return jsonify({"messaggio": "Utente modificato con successo"})

    except Exception as e:
        logger.error(
            "Errore durante la modifica dell'utente #%s - operatore: '%s': %s",
            id_utente, session.get("username"), e,
        )
        return jsonify({"errore": "Errore durante la modifica"}), 500


@app.route("/api/utenti/<int:id_utente>", methods=["DELETE"])
@accesso_richiesto
@richiedi_permesso("AMMINISTRAZIONE")
def elimina_utente(id_utente):
    if str(session.get("id_utente")) == str(id_utente):
        logger.warning(
            "Tentativo di eliminare il proprio account (ID: %s) - utente: '%s'",
            id_utente, session.get("username"),
        )
        return jsonify({"errore": "Non puoi eliminare il tuo stesso account"}), 400

    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()

            cursore.execute("SELECT id, username FROM utenti WHERE id = %s", (id_utente,))
            riga = cursore.fetchone()
            if not riga:
                logger.warning(
                    "Eliminazione utente fallita - ID #%s non trovato - operatore: '%s'",
                    id_utente, session.get("username"),
                )
                return jsonify({"errore": "Utente non trovato"}), 404

            username_eliminato = riga["username"]
            cursore.execute("DELETE FROM permessi_pagine WHERE utente_id = %s", (id_utente,))
            cursore.execute("DELETE FROM utenti WHERE id = %s", (id_utente,))
            connessione.commit()

        logger.info(
            "Utente #%s ('%s') eliminato - operatore: '%s'",
            id_utente, username_eliminato, session.get("username"),
        )
        return "", 204

    except Exception as e:
        logger.error(
            "Errore durante l'eliminazione dell'utente #%s - operatore: '%s': %s",
            id_utente, session.get("username"), e,
        )
        return jsonify({"errore": "Errore durante l'eliminazione"}), 500
