import contextlib
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def ottieni_db():
    """Stabilisce una connessione al database PostgreSQL e la chiude automaticamente."""
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "byte_bite")
    db_user = os.getenv("DB_USER", "byte_bite_user")
    db_password = os.getenv("DB_PASSWORD", "secure_password_change_me")

    try:
        connessione = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
            connect_timeout=30
        )
    except psycopg2.Error as e:
        logger.error("Impossibile connettersi al database (host: %s:%s, db: %s): %s", db_host, db_port, db_name, e)
        raise

    connessione.cursor_factory = RealDictCursor
    try:
        with connessione.cursor() as cur:
            cur.execute("SET TIME ZONE 'Europe/Rome'")
        connessione.commit()
        yield connessione
    finally:
        connessione.close()


def esegui_query(query, argomenti=(), uno=False, commit=False):
    """Esegue una query SQL e gestisce la connessione."""
    try:
        with ottieni_db() as connessione:
            cursore = connessione.cursor()
            # Parametri bindati: prevengono SQL injection e gestiscono i tipi correttamente.
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
