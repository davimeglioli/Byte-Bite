import contextlib
import sqlite3 as sq


@contextlib.contextmanager
def ottieni_db():
    """Stabilisce una connessione al database e la chiude automaticamente."""
    # Crea una connessione per-request con timeout per ridurre i lock su SQLite.
    connessione = sq.connect("db.sqlite3", timeout=30)
    # Permette accesso ai campi delle righe per nome colonna.
    connessione.row_factory = sq.Row
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
