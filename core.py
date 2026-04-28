import os
import secrets

from dotenv import load_dotenv
from flask import Flask
from flask_socketio import SocketIO

load_dotenv()

# Stato condiviso per timer realtime dashboard.
timer_attivi = {}

app = Flask(__name__)

# Imposta una chiave di sessione stabile (da env) o generata al volo.
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))


@app.errorhandler(403)
def errore_403(error):
    # Handler centralizzato per accessi non autorizzati.
    return "403 Forbidden", 403


socketio = SocketIO(
    app,
    cors_allowed_origins="*",
)
