def test_config(client):
    """Testa che la configurazione di test sia attiva."""
    # Accediamo all'app tramite il client
    assert client.application.config['TESTING'] is True

def test_home_page(client):
    """Testa che la home page risponda correttamente."""
    response = client.get('/')
    assert response.status_code == 200
    assert b"Seleziona area" in response.data

def test_404(client):
    """Testa una pagina inesistente."""
    response = client.get('/pagina-inesistente')
    assert response.status_code == 404
