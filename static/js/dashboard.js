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
    const currentState = button.dataset.status;

    // --- OPTIMISTIC UI UPDATE ---
    // Calcoliamo subito il prossimo stato per aggiornare l'interfaccia istantaneamente
    const stati = ["In Attesa", "In Preparazione", "Pronto", "Completato"];
    const idx = stati.indexOf(currentState);
    let nextState = currentState;
    
    // Logica di avanzamento stato (replica quella del server)
    if (idx !== -1 && idx < stati.length - 1) {
        nextState = stati[idx + 1];
    } else if (currentState === "Pronto") {
        // Se era pronto, il server potrebbe resettarlo a In Preparazione se c'è un timer,
        // ma per ora assumiamo il flusso normale o lasciamo che il server corregga.
        // Qui gestiamo il caso base.
    }

    // Salviamo lo stato originale per eventuale rollback
    const originalText = button.textContent;
    const originalStatus = button.dataset.status;

    // Aggiorniamo subito il bottone
    button.textContent = nextState;
    button.dataset.status = nextState;

    // Aggiorniamo anche la card (per stile e opacità se completato)
    const card = button.closest('.scheda-ordine');
    if (card) {
        card.dataset.status = nextState;
        if (nextState === "Completato") {
            // Feedback visivo immediato di completamento
            card.style.opacity = "0.5";
            card.style.pointerEvents = "none";
        }
    }

    fetch("/cambia_stato/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ordine_id, categoria })
    })
        .then(res => res.json())
        .then(data => {
            // Il server ora risponderà solo con il nuovo stato, senza tutto l'HTML.
            // La dashboard si aggiornerà completamente via socket poco dopo.
            
            // Se il server ci corregge lo stato (es. logica timer o altro), aggiorniamo
            if (data.nuovo_stato && data.nuovo_stato !== nextState) {
                 button.textContent = data.nuovo_stato;
                 button.dataset.status = data.nuovo_stato;
                 if (card) {
                     card.dataset.status = data.nuovo_stato;
                     if (data.nuovo_stato !== "Completato") {
                         card.style.opacity = "";
                         card.style.pointerEvents = "";
                     }
                 }
            }
        })
        .catch(err => {
            console.error("Errore:", err);
            // ROLLBACK in caso di errore
            button.textContent = originalText;
            button.dataset.status = originalStatus;
            if (card) {
                card.dataset.status = originalStatus;
                card.style.opacity = "";
                card.style.pointerEvents = "";
            }
        });
}

function aggiornaDashboard() {
    const categoria = categoriaCorrente; // già estratta sopra
    fetch(`/dashboard/${categoria}/partial`)
        .then(res => res.json())
        .then(data => {
            document.querySelectorAll('.griglia-ordini')[0].innerHTML = data.html_non_completati;
            document.querySelectorAll('.griglia-ordini')[1].innerHTML = data.html_completati;
        })
        .catch(err => console.error("Errore aggiornamento:", err));
}