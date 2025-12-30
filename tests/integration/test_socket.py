from app import app, emissione_sicura, socketio

# ==================== SocketIO ====================


def test_socketio_connessione_e_join_stanza(cliente):
    # Crea un client SocketIO collegato al client Flask.
    client_socket = socketio.test_client(app, flask_test_client=cliente)
    # Verifica che la connessione sia attiva.
    assert client_socket.is_connected()
    # Effettua join della stanza Cucina.
    client_socket.emit("join", {"categoria": "Cucina"})
    # Chiude la connessione.
    client_socket.disconnect()

def test_socketio_emette_aggiorna_dashboard(cliente):
    # Crea un client SocketIO e si iscrive alla stanza.
    client_socket = socketio.test_client(app, flask_test_client=cliente)
    client_socket.emit("join", {"categoria": "Cucina"})

    # Simula una emit dal server verso la stanza Cucina.
    socketio.emit("aggiorna_dashboard", {"categoria": "Cucina"}, room="Cucina")

    # Legge gli eventi ricevuti dal client.
    ricevuti = client_socket.get_received()
    # Verifica che almeno un evento sia arrivato.
    assert len(ricevuti) > 0
    # Verifica nome evento e payload.
    evento = ricevuti[0]
    assert evento["name"] == "aggiorna_dashboard"
    assert evento["args"][0]["categoria"] == "Cucina"

    # Chiude la connessione.
    client_socket.disconnect()

def test_amministrazione_riceve_aggiornamenti_di_altre_stanze(cliente):
    # Crea un client admin iscritto alla stanza amministrazione.
    client_admin = socketio.test_client(app, flask_test_client=cliente)
    client_admin.emit("join", {"categoria": "amministrazione"})

    # Crea un client cucina iscritto alla stanza Cucina.
    client_cucina = socketio.test_client(app, flask_test_client=cliente)
    client_cucina.emit("join", {"categoria": "Cucina"})

    # Svuota eventuali eventi precedenti.
    client_admin.get_received()
    client_cucina.get_received()

    # Usa emissione_sicura che replica su amministrazione.
    emissione_sicura("aggiorna_dashboard", {"categoria": "Cucina"}, stanza="Cucina")

    # Verifica ricezione lato amministrazione.
    ricevuti_admin = client_admin.get_received()
    assert len(ricevuti_admin) > 0
    assert ricevuti_admin[0]["name"] == "aggiorna_dashboard"
    assert ricevuti_admin[0]["args"][0]["categoria"] == "Cucina"

    # Verifica ricezione lato cucina.
    ricevuti_cucina = client_cucina.get_received()
    assert len(ricevuti_cucina) > 0

    # Chiude entrambe le connessioni.
    client_admin.disconnect()
    client_cucina.disconnect()
