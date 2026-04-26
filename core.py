import logging
import os
import secrets

from dotenv import load_dotenv
from flask import Flask
from flask_socketio import SocketIO

load_dotenv()

# Stato condiviso per timer realtime dashboard.
timer_attivi = {}

app = Flask(__name__)

# Configura logging solo su console (root logger) per avere un formato uniforme.
_logger_root = logging.getLogger()
# Pulisce eventuali handler pre-esistenti per evitare duplicazioni di output.
_logger_root.handlers.clear()
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
_logger_root.addHandler(_console_handler)

# Legge il livello da env (LOG_LEVEL) e lo normalizza su un livello valido.
_livello_log = os.getenv("LOG_LEVEL", "INFO").upper()
_logger_level = getattr(logging, _livello_log, logging.INFO)
_logger_root.setLevel(_logger_level)

# Allinea il logger di Flask al root logger e propaga i record (utile anche per i test).
app.logger.handlers.clear()
app.logger.propagate = True
app.logger.setLevel(_logger_level)
# Imposta una chiave di sessione stabile (da env) o generata al volo.
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))


@app.errorhandler(403)
def errore_403(error):
    # Handler centralizzato per accessi non autorizzati.
    return "403 Forbidden", 403


socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)
