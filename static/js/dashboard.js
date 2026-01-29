// ==================== Dashboard ====================
// Gestisce: socket realtime, cambio stato ordine e refresh parziale HTML.

// Connessione socket: usa solo websocket per ridurre latenza e fallback.
const socket = io({
    transports: ["websocket"],
    upgrade: false,
});

// Legge la categoria corrente dal titolo (es. "Dashboard Cucina").
const categoriaCorrente = document
    .querySelector("h2")
    .textContent
    .replace("Dashboard ", "")
    .trim();

// Si iscrive alla stanza della categoria.
socket.emit("join", { categoria: categoriaCorrente });

// Aggiornamento realtime: quando arriva un evento, ricarica solo la categoria corrente.
socket.on("aggiorna_dashboard", (dati) => {
    if (dati.categoria === categoriaCorrente) {
        aggiornaDashboard();
    }
});

function cambiaStato(bottone) {
    // Legge parametri necessari dal DOM.
    const ordine_id = bottone.dataset.id;
    const categoria = bottone.dataset.categoria;
    const statoAttuale = bottone.dataset.status;

    // Calcola subito il prossimo stato per aggiornare la UI istantaneamente.
    const stati = ["In Attesa", "In Preparazione", "Pronto", "Completato"];
    const indiceStato = stati.indexOf(statoAttuale);

    let statoSuccessivo = statoAttuale;
    if (indiceStato !== -1 && indiceStato < stati.length - 1) {
        statoSuccessivo = stati[indiceStato + 1];
    }

    // Salva valori originali per eventuale rollback.
    const testoOriginale = bottone.textContent;
    const statoOriginale = bottone.dataset.status;

    // Applica l'update ottimistico sul bottone.
    bottone.textContent = statoSuccessivo;
    bottone.dataset.status = statoSuccessivo;

    // Applica l'update ottimistico anche sulla card.
    const schedaOrdine = bottone.closest(".scheda-ordine");
    if (schedaOrdine) {
        schedaOrdine.dataset.status = statoSuccessivo;

        // Se completato, disabilita interazioni e abbassa opacità.
        if (statoSuccessivo === "Completato") {
            schedaOrdine.style.opacity = "0.5";
            schedaOrdine.style.pointerEvents = "none";
        }
    }

    // Invia la richiesta al backend per confermare lo stato.
    fetch("/cambia_stato/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ordine_id, categoria }),
    })
        .then((res) => res.json())
        .then((datiRisposta) => {
            // Il backend può correggere lo stato (es. logiche timer).
            if (datiRisposta.nuovo_stato && datiRisposta.nuovo_stato !== statoSuccessivo) {
                bottone.textContent = datiRisposta.nuovo_stato;
                bottone.dataset.status = datiRisposta.nuovo_stato;

                if (schedaOrdine) {
                    schedaOrdine.dataset.status = datiRisposta.nuovo_stato;

                    // Se non è completato, ripristina interazioni.
                    if (datiRisposta.nuovo_stato !== "Completato") {
                        schedaOrdine.style.opacity = "";
                        schedaOrdine.style.pointerEvents = "";
                    }
                }
            }
        })
        .catch((errore) => {
            // Se fallisce, ripristina lo stato originale (rollback).
            console.error("Errore:", errore);

            bottone.textContent = testoOriginale;
            bottone.dataset.status = statoOriginale;

            if (schedaOrdine) {
                schedaOrdine.dataset.status = statoOriginale;
                schedaOrdine.style.opacity = "";
                schedaOrdine.style.pointerEvents = "";
            }
        });
}

function aggiornaDashboard() {
    // Richiede HTML parziale per aggiornare liste "in corso" e "completati".
    const categoria = categoriaCorrente;

    fetch(`/dashboard/${categoria}/partial`)
        .then((res) => res.json())
        .then((dati) => {
            const griglie = document.querySelectorAll(".griglia-ordini");
            if (griglie.length < 2) return;

            // Prima griglia: ordini non completati.
            griglie[0].innerHTML = dati.html_non_completati;

            // Seconda griglia: ordini completati.
            griglie[1].innerHTML = dati.html_completati;
        })
        .catch((errore) => console.error("Errore aggiornamento:", errore));
}
