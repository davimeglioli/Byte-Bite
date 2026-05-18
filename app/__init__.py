import logging
import os
import secrets

from dotenv import load_dotenv
from flask import Flask, request
from flask_socketio import SocketIO

from app.logger import configura_logging

load_dotenv()

modalita_debug = os.getenv("DEBUG", "False").lower() == "true"
configura_logging(debug=modalita_debug)

logger = logging.getLogger(__name__)

timer_attivi = {}

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(
    __name__,
    static_folder=os.path.join(_BASE, "static"),
    template_folder=os.path.join(_BASE, "templates"),
)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))

logger.info("Applicazione Byte-Bite inizializzata (debug=%s)", modalita_debug)


@app.errorhandler(403)
def errore_403(error):
    logger.warning("Accesso negato (403) - URL: %s, IP: %s", request.path, request.remote_addr)
    return "403 Forbidden", 403


socketio = SocketIO(app, cors_allowed_origins="*")

from app.routes import amministrazione, auth, cassa, dashboard, ordini, prodotti, utenti  # noqa: E402, F401
