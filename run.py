import logging
import os
import socket

from app import app, socketio

logger = logging.getLogger(__name__)

if __name__ == "__main__":
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
