import pytest
import tempfile
import os
import sqlite3
import contextlib
from app import app

@pytest.fixture
def client(monkeypatch):
    """Fixture che configura un client di test e un database temporaneo."""
    # Crea un file temporaneo per il database
    db_fd, db_path = tempfile.mkstemp()
    
    # Configurazione app
    app.config['TESTING'] = True
    
    # Funzione mock per sqlite3.connect
    original_connect = sqlite3.connect
    
    def mock_connect(database, *args, **kwargs):
        # Se il codice cerca di connettersi a 'db.sqlite3', lo ridirigiamo al file temporaneo
        if database == 'db.sqlite3':
            return original_connect(db_path, *args, **kwargs)
        return original_connect(database, *args, **kwargs)
    
    # Applica il monkeypatch su 'app.sq.connect' 
    monkeypatch.setattr("app.sq.connect", mock_connect)

    # Mock SocketIO per evitare thread in background e errori di concorrenza
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)
    
    # Inizializza il database con lo schema
    with app.app_context():
        # Leggi lo schema SQL
        with open('db.sql', 'r') as f:
            schema = f.read()
            
        # Esegui lo schema sul DB temporaneo
        with contextlib.closing(sqlite3.connect(db_path)) as conn:
            conn.executescript(schema)
            
    # Fornisci il client ai test
    with app.test_client() as client:
        yield client
        
    # Pulizia
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass  # Su Windows potrebbe fallire se il file è ancora in uso

class AuthActions:
    def __init__(self, client):
        self._client = client

    def login(self, username='admin', password='password'):
        """Helper per effettuare il login."""
        return self._client.post(
            '/login/',
            data={'username': username, 'password': password}
        )

    def logout(self):
        """Helper per effettuare il logout."""
        return self._client.get('/logout/')

@pytest.fixture
def auth(client):
    """Fixture che restituisce l'oggetto AuthActions per gestire autenticazione."""
    # Assicuriamoci che esista un utente admin di default
    import bcrypt
    from app import ottieni_db
    
    with ottieni_db() as conn:
        # Controlla se esiste già
        exists = conn.execute("SELECT 1 FROM utenti WHERE username = 'admin'").fetchone()
        if not exists:
            password_hash = bcrypt.hashpw('password'.encode(), bcrypt.gensalt()).decode()
            conn.execute(
                "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
                ('admin', password_hash, 1, 1)
            )
            conn.commit()
            
    return AuthActions(client)
