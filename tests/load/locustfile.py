from locust import HttpUser, task, between
import random
import json

class CashierUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Esegue il login come cassiere all'avvio."""
        self.client.post("/login/", data={"username": "cassa", "password": "cassa"})

    @task(5)
    def view_cassa(self):
        """Naviga nella pagina della cassa."""
        self.client.get("/cassa/")

    @task(1)
    def place_order(self):
        """Simula l'inserimento di un ordine."""
        # Nota: In un ambiente reale, dovremmo prima recuperare gli ID dei prodotti disponibili.
        # Qui assumiamo che esistano prodotti con ID bassi o gestiamo l'errore lato server.
        products = [
            {"id": 1, "quantita": 1, "nome": "Caffè Load Test"},
            {"id": 2, "quantita": 2, "nome": "Pasta Load Test"}
        ]
        
        data = {
            "nome_cliente": f"LoadUser_{random.randint(1, 10000)}",
            "numero_tavolo": str(random.randint(1, 20)),
            "numero_persone": str(random.randint(1, 4)),
            "metodo_pagamento": random.choice(["Contanti", "Carta"]),
            "prodotti": json.dumps(products),
            "isTakeaway": ""
        }
        
        # La rotta /aggiungi_ordine/ gestisce la logica di creazione
        self.client.post("/aggiungi_ordine/", data=data)

class DashboardUser(HttpUser):
    wait_time = between(2, 5)
    
    def on_start(self):
        """Esegue il login come admin per vedere le dashboard."""
        self.client.post("/login/", data={"username": "admin", "password": "admin"})

    @task
    def view_dashboard(self):
        """Consulta una delle dashboard."""
        cat = random.choice(["Bar", "Cucina", "Griglia", "Gnoccheria"])
        self.client.get(f"/dashboard/{cat}/")
