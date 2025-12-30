# ==================== Base ====================


def test_configurazione_test_attiva(cliente):
    # Verifica che la configurazione di test sia attiva.
    assert cliente.application.config["TESTING"] is True


def test_home_risponde(cliente):
    # Esegue una richiesta alla home.
    risposta = cliente.get("/")
    # Verifica codice di risposta.
    assert risposta.status_code == 200
    # Verifica contenuto minimo presente nella pagina.
    assert b"Seleziona area" in risposta.data


def test_pagina_inesistente_restituisce_404(cliente):
    # Richiede una rotta non esistente.
    risposta = cliente.get("/pagina-inesistente")
    # Verifica che l'app risponda con 404.
    assert risposta.status_code == 404
