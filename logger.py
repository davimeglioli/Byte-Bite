import logging
import os
from logging.handlers import RotatingFileHandler

CARTELLA_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def configura_logging(debug: bool = False) -> None:
    """Configura il sistema di logging dell'applicazione."""
    os.makedirs(CARTELLA_LOG, exist_ok=True)

    livello = logging.DEBUG if debug else logging.INFO

    formato = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler su file con rotazione (max 5 MB per file, max 5 backup)
    handler_file = RotatingFileHandler(
        filename=os.path.join(CARTELLA_LOG, "byte_bite.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler_file.setFormatter(formato)
    handler_file.setLevel(livello)

    # Handler su console
    handler_console = logging.StreamHandler()
    handler_console.setFormatter(formato)
    handler_console.setLevel(livello)

    logger_root = logging.getLogger()
    logger_root.setLevel(livello)

    if not logger_root.handlers:
        logger_root.addHandler(handler_file)
        logger_root.addHandler(handler_console)

    # Silenzia librerie esterne verbose
    for nome_lib in ("werkzeug", "socketio", "engineio", "gevent", "urllib3"):
        logging.getLogger(nome_lib).setLevel(logging.WARNING)
