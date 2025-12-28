from flask_socketio import SocketIOTestClient
from app import app, socketio, emissione_sicura

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

def test_admin_receives_updates(client):
    """
    Testa che l'amministrazione riceva aggiornamenti destinati ad altre stanze.
    """
    # Client Amministrazione
    admin_client = socketio.test_client(app, flask_test_client=client)
    admin_client.emit('join', {'categoria': 'amministrazione'})
    
    # Client Cucina (per confronto)
    kitchen_client = socketio.test_client(app, flask_test_client=client)
    kitchen_client.emit('join', {'categoria': 'Cucina'})
    
    # Svuota buffer
    admin_client.get_received()
    kitchen_client.get_received()
    
    # Emuliamo un aggiornamento per la Cucina usando emissione_sicura
    emissione_sicura('aggiorna_dashboard', {'categoria': 'Cucina'}, stanza='Cucina')
    
    # Verifica Amministrazione
    received_admin = admin_client.get_received()
    assert len(received_admin) > 0
    assert received_admin[0]['name'] == 'aggiorna_dashboard'
    assert received_admin[0]['args'][0]['categoria'] == 'Cucina'
    
    # Verifica Cucina
    received_kitchen = kitchen_client.get_received()
    assert len(received_kitchen) > 0
    
    admin_client.disconnect()
    kitchen_client.disconnect()
