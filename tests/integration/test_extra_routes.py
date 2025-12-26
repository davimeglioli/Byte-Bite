import pytest
import bcrypt
from app import ottieni_db, ricalcola_statistiche

def test_amministrazione_route(client, auth):
    """Test access to administration page."""
    # Login as admin
    auth.login()
    
    response = client.get('/amministrazione/')
    assert response.status_code == 200
    assert b'Amministrazione' in response.data

def test_genera_statistiche_route(client, auth):
    """Test /genera_statistiche/ route."""
    auth.login()
    response = client.get('/genera_statistiche/')
    assert response.status_code == 302 # Redirects
    assert response.location.endswith('/amministrazione/')

def test_debug_reset_dati_route(client, auth):
    """Test /debug/reset_dati/ route."""
    auth.login()
    
    # Insert some data to be reset
    with ottieni_db() as conn:
        conn.execute("INSERT INTO ordini (id, nome_cliente, numero_tavolo, asporto, metodo_pagamento) VALUES (999, 'To Delete', 1, 0, 'Contanti')")
        conn.execute("INSERT INTO ordini_prodotti (ordine_id, prodotto_id, quantita) VALUES (999, 1, 1)")
        conn.commit()
        
    response = client.get('/debug/reset_dati/')
    assert response.status_code == 302
    
    with ottieni_db() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM ordini").fetchone()['c']
        assert count == 0

def test_403_forbidden(client, auth):
    """Test 403 Forbidden error handler."""
    # Create a non-admin user
    password = "pass"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    with ottieni_db() as conn:
        conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES ('user', ?, 0, 1)", (password_hash,))
        conn.commit()
    
    # Login as non-admin
    auth.login(username='user', password='pass')
    
    # Try to access admin page (requires AMMINISTRAZIONE permission, which user doesn't have)
    response = client.get('/amministrazione/')
    assert response.status_code == 403
    assert b'Accesso Negato' in response.data or b'403' in response.data

def test_inactive_user(client, auth):
    """Test behavior when user is inactive."""
    # Create inactive user
    password = "pass"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    with ottieni_db() as conn:
        conn.execute("INSERT INTO utenti (username, password_hash, is_admin, attivo) VALUES ('inactive', ?, 0, 0)", (password_hash,))
        conn.commit()
        
    auth.login(username='inactive', password='pass')
    
    # Try to access a protected route
    response = client.get('/amministrazione/')
    # Should redirect to login because user is inactive (session cleared)
    assert response.status_code == 302
    assert '/login/' in response.location
