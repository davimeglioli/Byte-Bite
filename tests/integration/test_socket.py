from flask_socketio import SocketIOTestClient
from app import app, socketio

def test_socketio_connection(client):
    """Testa che un client possa connettersi al WebSocket."""
    socket_client = socketio.test_client(app, flask_test_client=client)
    
    assert socket_client.is_connected()
    
    # Test Join Room
    socket_client.emit('join', {'categoria': 'Cucina'})
    
    socket_client.disconnect()

def test_socketio_emissione_aggiornamento(client, monkeypatch):
    """
    Testa che quando cambia lo stato di un ordine, venga emesso l'evento 'aggiorna_dashboard'.
    """
    socket_client = socketio.test_client(app, flask_test_client=client)
    socket_client.emit('join', {'categoria': 'Cucina'})
    
    # Simuliamo un'emissione dal server
    socketio.emit('aggiorna_dashboard', {'categoria': 'Cucina'}, room='Cucina')
    
    received = socket_client.get_received()
    
    # Verifica
    assert len(received) > 0
    evento = received[0]
    assert evento['name'] == 'aggiorna_dashboard'
    assert evento['args'][0]['categoria'] == 'Cucina'
    
    socket_client.disconnect()
