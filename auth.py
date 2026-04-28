import logging
from functools import wraps

from flask import abort, redirect, request, session, url_for

from db import esegui_query

logger = logging.getLogger(__name__)


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
            "attivo": session["user_cache_attivo"],
        }

    # Prima richiesta o cache invalida: carica dal database.
    utente = esegui_query(
        "SELECT id, username, is_admin, attivo FROM utenti WHERE id = %s",
        (id_utente,),
        uno=True,
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
            logger.warning(
                "Accesso non autenticato - URL: %s, IP: %s",
                request.path,
                request.remote_addr,
            )
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
                logger.warning(
                    "Accesso non autenticato a pagina protetta '%s' - IP: %s",
                    pagina,
                    request.remote_addr,
                )
                return redirect(url_for("accesso"))

            # Recupera l'utente (con cache sessione per ridurre query).
            utente = ottieni_utente_loggato()

            # Se l'utente è disattivo, svuota la sessione e forza il login.
            if not utente or utente["attivo"] != 1:
                username = session.get("username", "sconosciuto")
                logger.warning(
                    "Account disattivato o non trovato - utente: '%s', sessione invalidata",
                    username,
                )
                session.clear()
                return redirect(url_for("accesso"))

            # L'amministratore ha accesso completo.
            if utente["is_admin"] == 1:
                return f(*args, **kwargs)

            # Verifica il permesso specifico per la pagina richiesta.
            permesso = esegui_query(
                """
                SELECT 1 FROM permessi_pagine
                WHERE utente_id = %s AND pagina = %s
            """,
                (utente["id"], pagina),
                uno=True,
            )

            if permesso:
                # Permesso presente: esegue la route.
                return f(*args, **kwargs)

            # In assenza di permesso, blocca l'accesso.
            logger.warning(
                "Permesso negato - utente: '%s' (ID: %s), pagina: '%s'",
                utente["username"],
                utente["id"],
                pagina,
            )
            abort(403)

        return gestore

    return decorator
