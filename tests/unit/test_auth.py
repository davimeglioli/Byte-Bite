import pytest
import bcrypt
from app import ottieni_db

def test_login_successo(client):
    """Testa che un utente valido possa effettuare il login."""
    password = "password123"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    # Crea utente di test nel DB temporaneo
    with ottieni_db() as conn:
        conn.execute(
            "INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES (?, ?, ?, ?)",
            ("testuser", password_hash, 0, 1)
        )
        conn.commit()
        
    # Tenta il login
    response = client.post('/login/', data={
        "username": "testuser",
        "password": password
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert len(response.history) > 0 # Confirm redirect
    assert response.request.path == "/"

def test_login_fallito(client):
    """Testa login con credenziali errate."""
    response = client.post('/login/', data={
        "username": "wronguser",
        "password": "wrongpassword"
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Username o password errata" in response.data

def test_accesso_protetto_senza_login(client):
    """Testa che le pagine protette richiedano il login."""
    # Prova ad accedere alla cassa senza login
    response = client.get('/cassa/', follow_redirects=True)
    
    # Dovrebbe reindirizzare al login
    assert response.status_code == 200
    assert b"Login" in response.data
    assert "login" in response.request.path
