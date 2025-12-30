import json
import random

from locust import HttpUser, between, task

# ==================== Carico ====================


class UtenteCassa(HttpUser):
    # Simula un utente cassa con richieste frequenti.
    wait_time = between(0.1, 0.5)

    def on_start(self):
        # Esegue login all'avvio della simulazione.
        self.client.post("/login/", data={"username": "cassa", "password": "cassa"})

    @task(5)
    def visualizza_cassa(self):
        # Naviga la pagina cassa più spesso rispetto all'invio ordine.
        self.client.get("/cassa/")

    @task(1)
    def invia_ordine(self):
        # Usa una lista prodotti stabile per generare carico prevedibile.
        prodotti = [
            {"id": 1, "quantita": 1, "nome": "Spritz Aperol"},
            {"id": 2, "quantita": 2, "nome": "Spritz Campari"},
        ]

        # Compone payload ordine con campi richiesti dalla rotta.
        dati = {
            "nome_cliente": f"UtenteCarico_{random.randint(1, 10000)}",
            "numero_tavolo": str(random.randint(1, 20)),
            "numero_persone": str(random.randint(1, 4)),
            "metodo_pagamento": random.choice(["Contanti", "Carta"]),
            "prodotti": json.dumps(prodotti),
            "isTakeaway": "",
        }

        # Invia l'ordine.
        self.client.post("/aggiungi_ordine/", data=dati)


class UtenteDashboard(HttpUser):
    # Simula una dashboard che effettua polling/navigazioni.
    wait_time = between(0.5, 2)

    def on_start(self):
        # Esegue login admin per accedere alle dashboard.
        self.client.post("/login/", data={"username": "admin", "password": "admin"})

    @task
    def visualizza_dashboard(self):
        # Alterna le categorie per distribuire il traffico.
        categoria = random.choice(["Bar", "Cucina", "Griglia", "Gnoccheria"])
        # Effettua la richiesta alla dashboard selezionata.
        self.client.get(f"/dashboard/{categoria}/")
