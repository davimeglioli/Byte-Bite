import logging
import os
import socket

from core import app, socketio
from core import timer_attivi
from auth import accesso_richiesto, ottieni_utente_loggato, richiedi_permesso
from db import esegui_query, ottieni_db
from services import (
    cambia_stato_automatico,
    emissione_sicura,
    ottieni_ordini_per_categoria,
    ricalcola_statistiche,
)
import routes

logger = logging.getLogger(__name__)

# ==================== Avvio server ====================

if __name__ == "__main__":
    # Calcola un IP locale "ragionevole" per stampare l'URL di avvio.
    socket_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        socket_udp.connect(("8.8.8.8", 80))
        ip_locale = socket_udp.getsockname()[0]
    except Exception:
        ip_locale = "127.0.0.1"
    finally:
        socket_udp.close()
    modalita_debug = os.getenv("DEBUG", "False").lower() == "true"
    logger.info("Avvio server Byte-Bite - http://%s:8000 (debug=%s)", ip_locale, modalita_debug)
    socketio.run(app, host="0.0.0.0", port=8000, debug=modalita_debug)
