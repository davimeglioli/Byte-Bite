const socket = io({
    transports: ["websocket"],
    upgrade: false
}); // Connessione al socket
 
// Prende la categoria dal titolo (es. "Dashboard Cucina")
const categoriaCorrente = document
    .querySelector("h2")
    .textContent
    .replace("Dashboard ", "")
    .trim();

// Mi unisco alla stanza
socket.emit("join", { categoria: categoriaCorrente });

// Quando il server invia un aggiornamento in tempo reale, aggiorno la dashboard
socket.on("aggiorna_dashboard", (data) => {
    if (data.categoria === categoriaCorrente) {
        aggiornaDashboard();
    }
});

function cambiaStato(button) {
    const ordine_id = button.dataset.id;
    const categoria = button.dataset.categoria;

    fetch("/cambia_stato/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ordine_id, categoria })
    })
        .then(res => res.json())
        .then(data => {
            document.querySelectorAll('.orders-container')[0].innerHTML = data.html_non_completati;
            document.querySelectorAll('.orders-container')[1].innerHTML = data.html_completati;
        })
        .catch(err => console.error("Errore:", err));
}

function aggiornaDashboard() {
    const categoria = categoriaCorrente; // già estratta sopra
    fetch(`/dashboard/${categoria}/partial`)
        .then(res => res.json())
        .then(data => {
            document.querySelectorAll('.orders-container')[0].innerHTML = data.html_non_completati;
            document.querySelectorAll('.orders-container')[1].innerHTML = data.html_completati;
        })
        .catch(err => console.error("Errore aggiornamento:", err));
}