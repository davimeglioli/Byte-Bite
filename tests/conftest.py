import pytest
import tempfile
import os
import sqlite3
import contextlib
import threading
import time
import bcrypt
from app import app, socketio
import app as app_module

# --- CONFIGURAZIONE E2E (Session Scope) ---

PORT = 5001
BASE_URL = f"http://127.0.0.1:{PORT}"

@pytest.fixture(scope="session")
def test_db_path_e2e(tmp_path_factory):
    """Crea un percorso per il database di test E2E (persistente per la sessione)."""
    fn = tmp_path_factory.mktemp("data") / "test_db_e2e.sqlite3"
    return str(fn)

@pytest.fixture(scope="session")
def run_server(test_db_path_e2e):
    """Inizializza il database E2E e avvia il server Flask in un thread separato."""
    
    # 1. Inizializza Schema DB
    with open('db.sql', 'r') as f:
        schema = f.read()
    
    conn = sqlite3.connect(test_db_path_e2e)
    conn.executescript(schema)
    
    # 2. Seed Dati Iniziali (Admin, Cassa, Prodotti)
    
    # Admin User: admin / admin
    pwd_hash = bcrypt.hashpw('admin'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)", 
                 ('admin', pwd_hash, 1, 1))
    
    # Cashier User: cassa / cassa
    pwd_hash_cassa = bcrypt.hashpw('cassa'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)", 
                 ('cassa', pwd_hash_cassa, 0, 1))
    
    # Permessi Cassa
    cursor = conn.execute("SELECT id FROM utenti WHERE username='cassa'")
    user_id = cursor.fetchone()[0]
    conn.execute("INSERT INTO permessi_pagine (utente_id, pagina) VALUES (?, ?)", (user_id, 'CASSA'))
    
    # Prodotti
    conn.execute("""
        INSERT INTO prodotti (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti) 
        VALUES 
        ('Caffè Test', 1.0, 'Bar', 'Bar', 1, 100, 0),
        ('Pasta Test', 10.0, 'Primi', 'Cucina', 1, 50, 0)
    """)
    
    conn.commit()
    conn.close()

    # 3. Monkeypatch manuale di sqlite3.connect per il server thread
    original_connect = sqlite3.connect
    
    def mock_connect_e2e(database, *args, **kwargs):
        # Se l'app cerca di connettersi a 'db.sqlite3', la deviamo sul file E2E
        if 'db.sqlite3' in str(database):
            return original_connect(test_db_path_e2e, *args, **kwargs)
        return original_connect(database, *args, **kwargs)
        
    app_module.sq.connect = mock_connect_e2e
    
    # 4. Avvia Server
    def start_app():
        try:
            # Disabilita log startup
            import logging
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)
            
            # allow_unsafe_werkzeug=True necessario per env non-prod
            socketio.run(app, port=PORT, host='127.0.0.1', use_reloader=False, allow_unsafe_werkzeug=True, debug=False)
        except Exception as e:
            print(f"Server Error: {e}")
        
    server_thread = threading.Thread(target=start_app, daemon=True)
    server_thread.start()
    
    # Attesa che il server sia su
    time.sleep(2) 
    
    yield
    
    # Ripristino (opzionale dato che il processo muore, ma pulito)
    app_module.sq.connect = original_connect

@pytest.fixture(scope="session")
def base_url(run_server):
    """Restituisce l'URL base del server di test E2E. Assicura che il server sia avviato."""
    return BASE_URL

# --- CONFIGURAZIONE UNIT/INTEGRATION (Function Scope) ---

@pytest.fixture
def client(monkeypatch):
    """Fixture che configura un client di test e un database temporaneo isolato."""
    # Crea un file temporaneo per il database
    db_fd, db_path = tempfile.mkstemp()
    
    # Configurazione app
    old_testing = app.config.get('TESTING', False)
    app.config['TESTING'] = True
    
    # Funzione mock per sqlite3.connect (Function Scope)
    original_connect = sqlite3.connect
    
    def mock_connect_unit(database, *args, **kwargs):
        if database == 'db.sqlite3':
            return original_connect(db_path, *args, **kwargs)
        return original_connect(database, *args, **kwargs)
    
    # Applica il monkeypatch su 'app.sq.connect' (Sovrascrive eventuale patch E2E per questo test)
    monkeypatch.setattr("app.sq.connect", mock_connect_unit)

    # Mock SocketIO per evitare thread in background nei test unitari
    monkeypatch.setattr("app.socketio.start_background_task", lambda *args, **kwargs: None)
    
    # Inizializza il database con lo schema
    with app.app_context():
        with open('db.sql', 'r') as f:
            schema = f.read()
        with contextlib.closing(sqlite3.connect(db_path)) as conn:
            conn.executescript(schema)
            
    # Fornisci il client ai test
    with app.test_client() as client:
        yield client
        
    # Pulizia
    app.config['TESTING'] = old_testing
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass

class AuthActions:
    def __init__(self, client):
        self._client = client

    def login(self, username='admin', password='password'):
        return self._client.post(
            '/login/',
            data={'username': username, 'password': password}
        )

    def logout(self):
        return self._client.get('/logout/')

@pytest.fixture
def auth(client):
    """Fixture che restituisce l'oggetto AuthActions per gestire autenticazione."""
    import bcrypt
    from app import ottieni_db
    
    with ottieni_db() as conn:
        exists = conn.execute("SELECT 1 FROM utenti WHERE username = 'admin'").fetchone()
        if not exists:
            password_hash = bcrypt.hashpw('password'.encode(), bcrypt.gensalt()).decode()
            conn.execute(
                "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
                ('admin', password_hash, 1, 1)
            )
            conn.commit()
            
    return AuthActions(client)
