import contextlib
import os
import psycopg2
from psycopg2.extras import RealDictCursor


@contextlib.contextmanager
def ottieni_db():
    """Stabilisce una connessione al database PostgreSQL e la chiude automaticamente."""
    # Legge le credenziali da variabili di ambiente
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "byte_bite")
    db_user = os.getenv("DB_USER", "byte_bite_user")
    db_password = os.getenv("DB_PASSWORD", "secure_password_change_me")
    
    # Crea una connessione a PostgreSQL
    connessione = psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password,
        connect_timeout=30
    )
    # Permette accesso ai campi delle righe per nome colonna (RealDictCursor)
    connessione.cursor_factory = RealDictCursor
    try:
        # Espone la connessione al chiamante.
        yield connessione
    finally:
        # Chiude sempre la connessione anche in caso di errore.
        connessione.close()


def esegui_query(query, argomenti=(), uno=False, commit=False):
    """Esegue una query SQL e gestisce la connessione."""
    with ottieni_db() as connessione:
        cursore = connessione.cursor()
        # Usa parametri bindati per evitare injection e gestire i tipi correttamente.
        cursore.execute(query, argomenti)
        righe = None
        if not commit:
            # Per SELECT e simili: restituisce tutte le righe lette.
            righe = cursore.fetchall()
        if commit:
            # Per INSERT/UPDATE/DELETE: applica la transazione.
            connessione.commit()
    # Se richiesto, restituisce solo la prima riga; altrimenti la lista completa.
    return (righe[0] if righe else None) if uno else (righe or [])
