import contextlib
import logging
import os
import threading

import psycopg2
import psycopg2.extensions
import psycopg2.pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _parametri_connessione() -> dict:
    return dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "byte_bite"),
        user=os.getenv("DB_USER", "byte_bite_user"),
        password=os.getenv("DB_PASSWORD", "secure_password_change_me"),
        connect_timeout=30,
        options="-c TimeZone=Europe/Rome",
    )


def _ottieni_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = psycopg2.pool.ThreadedConnectionPool(2, 10, **_parametri_connessione())
                logger.info("Pool di connessioni DB inizializzato (min=2, max=10)")
    return _pool


@contextlib.contextmanager
def ottieni_db():
    """Fornisce una connessione dal pool e la restituisce al termine."""
    pool = _ottieni_pool()
    connessione = pool.getconn()
    connessione.cursor_factory = RealDictCursor
    try:
        yield connessione
    finally:
        if connessione.closed:
            pool.putconn(connessione, close=True)
        else:
            try:
                if connessione.status != psycopg2.extensions.STATUS_READY:
                    connessione.rollback()
            finally:
                pool.putconn(connessione)


def esegui_query(query, argomenti=(), uno=False, commit=False):
    """Esegue una query SQL e gestisce la connessione."""
    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()
            cursore.execute(query, argomenti)
            if commit:
                connessione.commit()
                righe = None
            else:
                righe = cursore.fetchall()
    except psycopg2.Error as e:
        logger.error("Errore durante l'esecuzione della query: %s", e)
        raise
    return (righe[0] if righe else None) if uno else (righe or [])
