import logging

import bcrypt
from flask import redirect, render_template, request, session, url_for

from app.auth import accesso_richiesto, ottieni_utente_loggato
from app import app
from app.db import esegui_query

logger = logging.getLogger(__name__)


@app.route("/login/", methods=["GET", "POST"])
def accesso():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not password:
            return render_template("login.html", error="Username o password errata")
        password = password.encode()

        utente = esegui_query(
            "SELECT id, username, password_hash, is_admin, attivo FROM utenti WHERE username = %s",
            (username,),
            uno=True,
        )

        if not utente:
            # Generic message — do not reveal which field is wrong.
            logger.warning("Tentativo di login con username inesistente: '%s' (IP: %s)", username, request.remote_addr)
            return render_template("login.html", error="Username o password errata")

        if not utente["attivo"]:
            logger.warning("Login negato - account disattivato: '%s' (IP: %s)", username, request.remote_addr)
            return render_template("login.html", error="Account disattivato")

        if not bcrypt.checkpw(password, utente["password_hash"].encode()):
            # Generic message — do not reveal which field is wrong.
            logger.warning("Login fallito - password errata per utente: '%s' (IP: %s)", username, request.remote_addr)
            return render_template("login.html", error="Username o password errata")

        session["id_utente"] = utente["id"]
        session["username"] = utente["username"]
        logger.info(
            "Login riuscito - utente: '%s' (ID: %s, admin: %s, IP: %s)",
            utente["username"], utente["id"], bool(utente["is_admin"]), request.remote_addr,
        )
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/")
def home():
    utente = ottieni_utente_loggato()
    return render_template("index.html", utente=utente)


@app.route("/logout/", methods=["POST"])
def logout():
    username = session.get("username", "sconosciuto")
    session.clear()
    logger.info("Logout - utente: '%s'", username)
    return redirect(url_for("accesso"))
