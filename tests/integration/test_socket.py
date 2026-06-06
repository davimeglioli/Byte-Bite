from app import app, socketio
from app.services import emissione_sicura

# ==================== SocketIO ====================


def test_socketio_connessione_e_join_stanza(cliente):
    client_socket = socketio.test_client(app, namespace="/dashboard", flask_test_client=cliente)
    assert client_socket.is_connected(namespace="/dashboard")
    client_socket.emit("join", {"categoria": "Cucina"}, namespace="/dashboard")
    client_socket.disconnect(namespace="/dashboard")


def test_socketio_emette_aggiorna_dashboard(cliente):
    client_socket = socketio.test_client(app, namespace="/dashboard", flask_test_client=cliente)
    client_socket.emit("join", {"categoria": "Cucina"}, namespace="/dashboard")

    socketio.emit("aggiorna_dashboard", {"categoria": "Cucina"}, room="Cucina", namespace="/dashboard")

    ricevuti = client_socket.get_received(namespace="/dashboard")
    assert len(ricevuti) > 0
    evento = ricevuti[0]
    assert evento["name"] == "aggiorna_dashboard"
    assert evento["args"][0]["categoria"] == "Cucina"

    client_socket.disconnect(namespace="/dashboard")


def test_dashboard_e_admin_sono_isolati(cliente):
    # Dashboard client su /dashboard non deve ricevere eventi emessi su /admin.
    client_dashboard = socketio.test_client(app, namespace="/dashboard", flask_test_client=cliente)
    client_dashboard.emit("join", {"categoria": "Cucina"}, namespace="/dashboard")

    client_admin = socketio.test_client(app, namespace="/admin", flask_test_client=cliente)
    client_admin.emit("join", {"categoria": "amministrazione"}, namespace="/admin")

    client_dashboard.get_received(namespace="/dashboard")
    client_admin.get_received(namespace="/admin")

    # Emetti aggiorna_admin solo sul namespace /admin.
    emissione_sicura("aggiorna_admin", {"ordini": [], "prodotti": []}, stanza="amministrazione", namespace="/admin")

    # L'admin deve riceverlo.
    ricevuti_admin = client_admin.get_received(namespace="/admin")
    assert len(ricevuti_admin) > 0
    assert ricevuti_admin[0]["name"] == "aggiorna_admin"

    # Il dashboard NON deve riceverlo.
    ricevuti_dashboard = client_dashboard.get_received(namespace="/dashboard")
    assert len(ricevuti_dashboard) == 0

    client_dashboard.disconnect(namespace="/dashboard")
    client_admin.disconnect(namespace="/admin")
