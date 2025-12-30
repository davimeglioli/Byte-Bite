// ==================== Stato pagina ====================
let grafici = {
    categorie: null,
    ore: null,
    completati: null,
    top10: null,
};

let socketIo = null;
let stanzeIscritte = new Set();
let aggiornamentoPianificato = false;

// ==================== Statistiche e grafici ====================
async function caricaStatistiche() {
    // Carica i dati aggregati necessari per grafici e riepiloghi.
    const risposta = await fetch("/api/statistiche/");
    return await risposta.json();
}

function aggiornaRecap(totali) {
    // Aggiorna i numeri in alto nelle schede statistiche.
    const schede = document.querySelectorAll(".scheda-statistica .valore-statistica");
    schede[0].textContent = totali.ordini_totali;
    schede[1].textContent = totali.ordini_completati;
    schede[2].textContent = totali.totale_incasso.toFixed(2) + " €";
    schede[3].textContent = totali.totale_carta.toFixed(2) + " €";
    schede[4].textContent = totali.totale_contanti.toFixed(2) + " €";
}

function inizializzaGrafici(statistiche) {
    // Grafico 1: quantità per categoria dashboard.
    grafici.categorie = new Chart(document.getElementById("grafico1"), {
        type: "pie",
        data: {
            labels: statistiche.categorie.map((c) => c.categoria_dashboard),
            datasets: [{ data: statistiche.categorie.map((c) => c.totale) }],
        },
        options: { responsive: true, maintainAspectRatio: true, aspectRatio: 1 },
    });

    // Grafico 2: ordini per ora.
    grafici.ore = new Chart(document.getElementById("grafico2"), {
        type: "line",
        data: {
            labels: statistiche.ore.map((o) => o.ora),
            datasets: [{ label: "Ordini per ora", data: statistiche.ore.map((o) => o.totale), borderWidth: 2 }],
        },
        options: { responsive: true, maintainAspectRatio: true, aspectRatio: 1.2 },
    });

    // Grafico 3: completati vs non completati.
    grafici.completati = new Chart(document.getElementById("grafico3"), {
        type: "doughnut",
        data: {
            labels: ["Completati", "Non Completati"],
            datasets: [
                {
                    data: [
                        statistiche.totali.ordini_completati,
                        statistiche.totali.ordini_totali - statistiche.totali.ordini_completati,
                    ],
                },
            ],
        },
        options: { responsive: true, maintainAspectRatio: true, aspectRatio: 1 },
    });

    // Grafico 4: top 10 prodotti per venduti.
    grafici.top10 = new Chart(document.getElementById("grafico4"), {
        type: "bar",
        data: {
            labels: statistiche.top10.map((p) => p.nome),
            datasets: [{ label: "Venduti", data: statistiche.top10.map((p) => p.venduti), borderWidth: 2 }],
        },
        options: { responsive: true, maintainAspectRatio: true, aspectRatio: 1.2, scales: { y: { beginAtZero: true } } },
    });
}

function aggiornaGrafici(statistiche) {
    // Aggiorna grafico categorie.
    grafici.categorie.data.labels = statistiche.categorie.map((c) => c.categoria_dashboard);
    grafici.categorie.data.datasets[0].data = statistiche.categorie.map((c) => c.totale);
    grafici.categorie.update();

    // Aggiorna grafico ore.
    grafici.ore.data.labels = statistiche.ore.map((o) => o.ora);
    grafici.ore.data.datasets[0].data = statistiche.ore.map((o) => o.totale);
    grafici.ore.update();

    // Aggiorna grafico completati.
    grafici.completati.data.datasets[0].data = [
        statistiche.totali.ordini_completati,
        statistiche.totali.ordini_totali - statistiche.totali.ordini_completati,
    ];
    grafici.completati.update();

    // Aggiorna grafico top 10.
    grafici.top10.data.labels = statistiche.top10.map((p) => p.nome);
    grafici.top10.data.datasets[0].data = statistiche.top10.map((p) => p.venduti);
    grafici.top10.update();
}

// ==================== Realtime ====================
function iscrivitiStanze(_categorie) {
    // L'amministrazione riceve notifiche globali sulla stanza dedicata.
    if (!socketIo) return;

    const stanza = "amministrazione";
    if (stanzeIscritte.has(stanza)) return;

    socketIo.emit("join", { categoria: stanza });
    stanzeIscritte.add(stanza);
}

// ==================== Tabelle e filtri ====================
async function aggiornaTabellaOrdini() {
    // Ricarica solo le righe della tabella ordini (HTML parziale).
    const risposta = await fetch("/api/amministrazione/ordini_html");
    const html = await risposta.text();
    document.querySelector(".tabella-dati tbody").innerHTML = html;
}

function filtraProdotti(categoria) {
    // Filtra righe prodotti in base alla categoria menu.
    const righe = document.querySelectorAll(".tabella-dati tbody tr[data-categoria]");
    righe.forEach((riga) => {
        const categoriaRiga = riga.getAttribute("data-categoria");
        if (categoria === "Tutte" || categoriaRiga === categoria) {
            riga.classList.remove("nascosto");
        } else {
            riga.classList.add("nascosto");
        }
    });
}

async function aggiornaTabellaProdotti() {
    // Ricarica solo le righe della tabella prodotti (HTML parziale).
    const risposta = await fetch("/api/amministrazione/prodotti_html");
    const html = await risposta.text();

    // La pagina contiene due tbody con la stessa classe: [0]=ordini, [1]=prodotti.
    const tbodyTabelle = document.querySelectorAll(".tabella-dati tbody");
    if (tbodyTabelle.length < 2) return;

    tbodyTabelle[1].innerHTML = html;

    // Riapplica il filtro della tab attiva dopo il refresh.
    const tabAttiva = document.querySelector(".contenitore-menu .linguetta.attiva");
    if (!tabAttiva) return;

    const categoria = tabAttiva.getAttribute("data-categoria") || tabAttiva.textContent.trim();
    filtraProdotti(categoria);
}

async function toggleDettagli(bottone) {
    // Espande/chiude la riga dettagli dell'ordine nella tabella.
    const idOrdine = bottone.getAttribute("data-id");
    const rigaOrdine = bottone.closest("tr");
    const rigaSuccessiva = rigaOrdine.nextElementSibling;
    const espanso = bottone.classList.contains("attivo");

    if (espanso) {
        // Chiude e rimuove la riga dettagli se presente.
        bottone.classList.remove("attivo");
        if (rigaSuccessiva && rigaSuccessiva.classList.contains("riga-dettagli")) {
            rigaSuccessiva.remove();
        }
        return;
    }

    // Apre: prima pulisce eventuali dettagli residui.
    bottone.classList.add("attivo");
    if (rigaSuccessiva && rigaSuccessiva.classList.contains("riga-dettagli")) {
        rigaSuccessiva.remove();
    }

    try {
        // Richiede l'HTML dei dettagli e lo inserisce subito dopo la riga ordine.
        const risposta = await fetch(`/api/ordine/${idOrdine}/dettagli`);
        if (!risposta.ok) throw new Error("Errore nel caricamento dei dettagli");
        const html = await risposta.text();
        rigaOrdine.insertAdjacentHTML("afterend", html);
    } catch (errore) {
        // Ripristina il bottone e avvisa l'utente.
        console.error("Errore:", errore);
        alert("Impossibile caricare i dettagli dell'ordine.");
        bottone.classList.remove("attivo");
    }
}

// ==================== Aggiornamento pagina ====================
async function aggiornaTutto() {
    // Carica statistiche e aggiorna UI (grafici + tabelle).
    const statistiche = await caricaStatistiche();
    aggiornaRecap(statistiche.totali);
    aggiornaGrafici(statistiche);
    iscrivitiStanze(statistiche.categorie);

    // Tabelle: partono in parallelo (non atteso) per ridurre latenza percepita.
    aggiornaTabellaOrdini();
    aggiornaTabellaProdotti();
}

function pianificaAggiornamento() {
    // Debounce: in caso di tanti eventi socket, raggruppa gli aggiornamenti.
    if (aggiornamentoPianificato) return;
    aggiornamentoPianificato = true;

    setTimeout(async () => {
        await aggiornaTutto();
        aggiornamentoPianificato = false;
    }, 300);
}

document.addEventListener("DOMContentLoaded", async () => {
    // Primo render: statistiche + grafici iniziali.
    const statistiche = await caricaStatistiche();
    aggiornaRecap(statistiche.totali);
    inizializzaGrafici(statistiche);
    iscrivitiStanze(statistiche.categorie);

    // Realtime: ascolta gli eventi socket e pianifica un refresh debounced.
    if (typeof io !== "undefined") {
        socketIo = io();
        socketIo.on("connect", () => {
            iscrivitiStanze(statistiche.categorie);
        });
        socketIo.on("aggiorna_dashboard", () => {
            pianificaAggiornamento();
        });
    }

    // ==================== Filtri prodotti (linguette categorie) ====================
    const linguetteCategorie = document.querySelectorAll(".contenitore-menu .linguetta");
    if (linguetteCategorie.length > 0) {
        // Filtra le righe prodotto in base alla linguetta cliccata.
        function filtraProdottiDaTab(categoria) {
            const righe = document.querySelectorAll(".tabella-dati tbody tr[data-categoria]");
            righe.forEach((riga) => {
                const categoriaRiga = riga.getAttribute("data-categoria");
                if (categoria === "Tutte" || categoriaRiga === categoria) {
                    riga.classList.remove("nascosto");
                } else {
                    riga.classList.add("nascosto");
                }
            });
        }

        // Attiva la prima linguetta di default.
        linguetteCategorie[0].classList.add("attiva");
        filtraProdottiDaTab(linguetteCategorie[0].getAttribute("data-categoria") || linguetteCategorie[0].textContent.trim());

        // Al click, aggiorna la tab attiva e rifiltra la tabella.
        linguetteCategorie.forEach((linguetta) => {
            linguetta.addEventListener("click", () => {
                linguetteCategorie.forEach((t) => t.classList.remove("attiva"));
                linguetta.classList.add("attiva");

                const categoria = linguetta.getAttribute("data-categoria") || linguetta.textContent.trim();
                filtraProdottiDaTab(categoria);
            });
        });
    }

    // ==================== Modale: rifornimento prodotto ====================
    const modaleRifornimento = document.getElementById("modaleRifornimento");
    const nomeProdottoTarget = document.getElementById("nomeProdottoTarget");
    const idProdottoTarget = document.getElementById("idProdottoTarget");
    const btnAnnulla = document.getElementById("btnAnnulla");
    const formRifornimento = document.getElementById("formRifornimento");

    window.apriModaleRifornimento = function (id, nome) {
        // Precompila i campi e porta in primo piano la modale.
        nomeProdottoTarget.textContent = nome;
        idProdottoTarget.value = id;
        modaleRifornimento.classList.add("attivo");

        // Focus sul campo quantità per velocizzare l'operazione.
        setTimeout(() => {
            modaleRifornimento.querySelector('input[type="number"]').focus();
        }, 100);
    };

    function chiudiModaleRifornimento() {
        // Chiude e resetta il form per il prossimo utilizzo.
        modaleRifornimento.classList.remove("attivo");
        formRifornimento.reset();
    }

    btnAnnulla.addEventListener("click", chiudiModaleRifornimento);

    // Chiude cliccando fuori dalla finestra modale.
    modaleRifornimento.addEventListener("click", (e) => {
        if (e.target === modaleRifornimento) chiudiModaleRifornimento();
    });

    // Invia richiesta rifornimento e chiude la modale.
    formRifornimento.addEventListener("submit", async (e) => {
        e.preventDefault();

        const id = idProdottoTarget.value;
        const quantita = document.getElementById("quantitaInput").value;

        try {
            const risposta = await fetch("/api/rifornisci_prodotto", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id: id, quantita: quantita }),
            });

            if (!risposta.ok) {
                alert("Errore durante il rifornimento.");
            }
        } catch (errore) {
            console.error("Errore:", errore);
            alert("Errore di connessione.");
        }

        chiudiModaleRifornimento();
    });

    // ==================== Modale: modifica prodotto ====================
    const modaleModifica = document.getElementById("modaleModifica");
    const formModifica = document.getElementById("formModifica");
    const btnAnnullaModifica = document.getElementById("btnAnnullaModifica");

    // Elementi del form di modifica.
    const idProdottoModifica = document.getElementById("idProdottoModifica");
    const nomeProdottoModifica = document.getElementById("nomeProdottoModifica");
    const categoriaDashboardModifica = document.getElementById("categoriaDashboardModifica");
    const quantitaProdottoModifica = document.getElementById("quantitaProdottoModifica");
    const toggleDisponibilitaModifica = document.getElementById("toggleDisponibilitaModifica");
    const labelStatoModifica = document.getElementById("labelStatoModifica");

    function aggiornaLabelStato() {
        // Sincronizza testo e stile in base allo stato del toggle.
        const disponibile = toggleDisponibilitaModifica.checked;
        labelStatoModifica.textContent = disponibile ? "Disponibile" : "Non disponibile";

        if (disponibile) {
            labelStatoModifica.classList.add("testo-attivo");
            labelStatoModifica.classList.remove("testo-inattivo");
        } else {
            labelStatoModifica.classList.add("testo-inattivo");
            labelStatoModifica.classList.remove("testo-attivo");
        }
    }

    // Aggiorna label quando cambia il toggle.
    toggleDisponibilitaModifica.addEventListener("change", aggiornaLabelStato);

    // Quando cambia quantità, abilita/disabilita automaticamente la disponibilità.
    quantitaProdottoModifica.addEventListener("input", () => {
        const quantita = parseInt(quantitaProdottoModifica.value) || 0;
        toggleDisponibilitaModifica.checked = quantita > 0;
        aggiornaLabelStato();
    });

    window.apriModaleModifica = function (bottone) {
        // Estrae i valori dai data-attribute della riga tabella.
        const id = bottone.getAttribute("data-id");
        const nome = bottone.getAttribute("data-nome");
        const categoriaDashboard = bottone.getAttribute("data-cat");
        const quantita = bottone.getAttribute("data-qta");
        const disponibile = bottone.getAttribute("data-disp") === "1";

        // Precompila campi e apre la modale.
        idProdottoModifica.value = id;
        nomeProdottoModifica.value = nome;
        categoriaDashboardModifica.value = categoriaDashboard;
        quantitaProdottoModifica.value = quantita;
        toggleDisponibilitaModifica.checked = disponibile;
        aggiornaLabelStato();

        modaleModifica.classList.add("attivo");
    };

    function chiudiModaleModifica() {
        // Chiude la modale senza inviare modifiche.
        modaleModifica.classList.remove("attivo");
    }

    btnAnnullaModifica.addEventListener("click", chiudiModaleModifica);

    // Chiude cliccando fuori dalla finestra modale.
    modaleModifica.addEventListener("click", (e) => {
        if (e.target === modaleModifica) chiudiModaleModifica();
    });

    // Invia la modifica e chiude la modale.
    formModifica.addEventListener("submit", async (e) => {
        e.preventDefault();

        const dati = {
            id: idProdottoModifica.value,
            nome: nomeProdottoModifica.value,
            categoria_dashboard: categoriaDashboardModifica.value,
            quantita: parseInt(quantitaProdottoModifica.value),
            disponibile: toggleDisponibilitaModifica.checked,
        };

        try {
            const risposta = await fetch("/api/modifica_prodotto", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(dati),
            });

            if (!risposta.ok) {
                alert("Errore durante la modifica.");
            }
        } catch (errore) {
            console.error("Errore:", errore);
            alert("Errore di connessione.");
        }

        chiudiModaleModifica();
    });

    // ==================== Modale: eliminazione prodotto ====================
    const modaleElimina = document.getElementById("modaleElimina");
    const nomeProdottoElimina = document.getElementById("nomeProdottoElimina");
    const idProdottoElimina = document.getElementById("idProdottoElimina");
    const btnAnnullaElimina = document.getElementById("btnAnnullaElimina");
    const btnConfermaElimina = document.getElementById("btnConfermaElimina");

    window.apriModaleElimina = function (bottone) {
        // Prepara la conferma eliminazione con i dati del prodotto.
        const id = bottone.getAttribute("data-id");
        const nome = bottone.getAttribute("data-nome");

        idProdottoElimina.value = id;
        nomeProdottoElimina.textContent = nome;
        modaleElimina.classList.add("attivo");
    };

    function chiudiModaleElimina() {
        // Chiude la modale di conferma eliminazione.
        modaleElimina.classList.remove("attivo");
    }

    btnAnnullaElimina.addEventListener("click", chiudiModaleElimina);

    // Chiude cliccando fuori.
    modaleElimina.addEventListener("click", (e) => {
        if (e.target === modaleElimina) chiudiModaleElimina();
    });

    // Conferma eliminazione e chiude la modale.
    btnConfermaElimina.addEventListener("click", async () => {
        const id = idProdottoElimina.value;
        if (!id) return;

        try {
            const risposta = await fetch("/api/elimina_prodotto", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id: id }),
            });

            if (!risposta.ok) {
                alert("Errore durante l'eliminazione.");
            }
        } catch (errore) {
            console.error("Errore:", errore);
            alert("Errore di connessione.");
        }

        chiudiModaleElimina();
    });

    // ==================== Modale: eliminazione ordine ====================
    const modaleEliminaOrdine = document.getElementById("modaleEliminaOrdine");
    const idOrdineElimina = document.getElementById("idOrdineElimina");
    const idOrdineHidden = document.getElementById("idOrdineHidden");
    const btnAnnullaEliminaOrdine = document.getElementById("btnAnnullaEliminaOrdine");
    const btnConfermaEliminaOrdine = document.getElementById("btnConfermaEliminaOrdine");

    window.apriModaleEliminaOrdine = function (bottone) {
        // Precompila id ordine e mostra la modale.
        const id = bottone.getAttribute("data-id");
        if (idOrdineHidden) idOrdineHidden.value = id;
        if (idOrdineElimina) idOrdineElimina.textContent = id;
        if (modaleEliminaOrdine) modaleEliminaOrdine.classList.add("attivo");
    };

    function chiudiModaleEliminaOrdine() {
        // Chiude la modale eliminazione ordine.
        if (modaleEliminaOrdine) modaleEliminaOrdine.classList.remove("attivo");
    }

    if (btnAnnullaEliminaOrdine) {
        btnAnnullaEliminaOrdine.addEventListener("click", chiudiModaleEliminaOrdine);
    }

    // Chiude cliccando fuori.
    if (modaleEliminaOrdine) {
        modaleEliminaOrdine.addEventListener("click", (e) => {
            if (e.target === modaleEliminaOrdine) chiudiModaleEliminaOrdine();
        });
    }

    // Conferma eliminazione ordine.
    if (btnConfermaEliminaOrdine) {
        btnConfermaEliminaOrdine.addEventListener("click", async () => {
            const id = idOrdineHidden ? idOrdineHidden.value : null;
            if (!id) return;

            try {
                const risposta = await fetch("/api/elimina_ordine", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ id: id }),
                });

                if (!risposta.ok) {
                    alert("Errore durante l'eliminazione dell'ordine.");
                }
            } catch (errore) {
                console.error("Errore:", errore);
                alert("Errore di connessione.");
            }

            chiudiModaleEliminaOrdine();
        });
    }

    // ==================== Modale: modifica ordine ====================
    const modaleModificaOrdine = document.getElementById("modaleModificaOrdine");
    const formModificaOrdine = document.getElementById("formModificaOrdine");

    // Campi del form ordine.
    const idOrdineModifica = document.getElementById("idOrdineModifica");
    const clienteModifica = document.getElementById("clienteModifica");
    const tavoloModifica = document.getElementById("tavoloModifica");
    const personeModifica = document.getElementById("personeModifica");
    const pagamentoModifica = document.getElementById("pagamentoModifica");

    window.apriModaleModificaOrdine = function (bottone) {
        // Legge i dati già presenti nella tabella per precompilare la modale.
        const riga = bottone.closest("tr");
        const celle = riga.querySelectorAll("td");

        const id = riga.getAttribute("data-id");
        const cliente = celle[1].textContent.trim();
        const tavolo = celle[2].textContent.trim();
        const persone = celle[3].textContent.trim();
        const pagamento = celle[5].textContent.trim();

        // Converte "-" in stringa vuota per i campi opzionali.
        if (idOrdineModifica) idOrdineModifica.value = id;
        if (clienteModifica) clienteModifica.value = cliente;
        if (tavoloModifica) tavoloModifica.value = tavolo === "-" || tavolo === "" ? "" : tavolo;
        if (personeModifica) personeModifica.value = persone === "-" || persone === "" ? "" : persone;
        if (pagamentoModifica) pagamentoModifica.value = pagamento;

        // Mostra la modale.
        if (modaleModificaOrdine) modaleModificaOrdine.classList.add("attivo");
    };

    window.chiudiModaleModificaOrdine = function () {
        // Chiude la modale di modifica ordine.
        if (modaleModificaOrdine) modaleModificaOrdine.classList.remove("attivo");
    };

    // Chiude cliccando fuori.
    if (modaleModificaOrdine) {
        modaleModificaOrdine.addEventListener("click", (e) => {
            if (e.target === modaleModificaOrdine) window.chiudiModaleModificaOrdine();
        });
    }

    // Invia modifica ordine.
    if (formModificaOrdine) {
        formModificaOrdine.addEventListener("submit", async (e) => {
            e.preventDefault();

            const dati = {
                id_ordine: idOrdineModifica.value,
                nome_cliente: clienteModifica.value,
                numero_tavolo: tavoloModifica.value,
                numero_persone: personeModifica.value,
                metodo_pagamento: pagamentoModifica.value,
            };

            try {
                const risposta = await fetch("/api/modifica_ordine", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(dati),
                });

                if (!risposta.ok) {
                    const erroreRisposta = await risposta.json();
                    alert("Errore: " + (erroreRisposta.errore || "Impossibile modificare ordine"));
                }
            } catch (errore) {
                console.error("Errore:", errore);
                alert("Errore di connessione.");
            }

            window.chiudiModaleModificaOrdine();
        });
    }

    // ==================== Modale: aggiunta prodotto ====================
    const modaleAggiunta = document.getElementById("modaleAggiunta");
    const formAggiunta = document.getElementById("formAggiunta");
    const btnAnnullaAggiunta = document.getElementById("btnAnnullaAggiunta");

    // Elementi del form di aggiunta.
    const nomeProdottoAggiunta = document.getElementById("nomeProdottoAggiunta");
    const categoriaDashboardAggiunta = document.getElementById("categoriaDashboardAggiunta");
    const categoriaMenuAggiunta = document.getElementById("categoriaMenuAggiunta");
    const prezzoProdottoAggiunta = document.getElementById("prezzoProdottoAggiunta");
    const quantitaProdottoAggiunta = document.getElementById("quantitaProdottoAggiunta");
    const toggleDisponibilitaAggiunta = document.getElementById("toggleDisponibilitaAggiunta");
    const labelStatoAggiunta = document.getElementById("labelStatoAggiunta");

    function aggiornaLabelStatoAggiunta() {
        // Aggiorna testo e classi della label "Disponibile/Non disponibile".
        if (!labelStatoAggiunta || !toggleDisponibilitaAggiunta) return;

        const disponibile = toggleDisponibilitaAggiunta.checked;
        labelStatoAggiunta.textContent = disponibile ? "Disponibile" : "Non disponibile";

        if (disponibile) {
            labelStatoAggiunta.classList.add("testo-attivo");
            labelStatoAggiunta.classList.remove("testo-inattivo");
        } else {
            labelStatoAggiunta.classList.add("testo-inattivo");
            labelStatoAggiunta.classList.remove("testo-attivo");
        }
    }

    // Aggiorna label quando cambia il toggle.
    if (toggleDisponibilitaAggiunta) {
        toggleDisponibilitaAggiunta.addEventListener("change", aggiornaLabelStatoAggiunta);
    }

    // Quando cambia quantità, aggiorna automaticamente il toggle.
    if (quantitaProdottoAggiunta) {
        quantitaProdottoAggiunta.addEventListener("input", () => {
            const quantita = parseInt(quantitaProdottoAggiunta.value) || 0;
            toggleDisponibilitaAggiunta.checked = quantita > 0;
            aggiornaLabelStatoAggiunta();
        });
    }

    window.apriModaleAggiunta = function () {
        // Apre la modale e imposta i default.
        if (!modaleAggiunta) return;

        formAggiunta.reset();
        if (toggleDisponibilitaAggiunta) toggleDisponibilitaAggiunta.checked = true;
        aggiornaLabelStatoAggiunta();

        modaleAggiunta.classList.add("attivo");
    };

    function chiudiModaleAggiunta() {
        // Chiude la modale aggiunta prodotto.
        if (modaleAggiunta) modaleAggiunta.classList.remove("attivo");
    }

    if (btnAnnullaAggiunta) {
        btnAnnullaAggiunta.addEventListener("click", chiudiModaleAggiunta);
    }

    // Chiude cliccando fuori.
    if (modaleAggiunta) {
        modaleAggiunta.addEventListener("click", (e) => {
            if (e.target === modaleAggiunta) chiudiModaleAggiunta();
        });
    }

    // Invia aggiunta prodotto.
    if (formAggiunta) {
        formAggiunta.addEventListener("submit", async (e) => {
            e.preventDefault();

            const dati = {
                nome: nomeProdottoAggiunta.value,
                categoria_dashboard: categoriaDashboardAggiunta.value,
                categoria_menu: categoriaMenuAggiunta.value,
                prezzo: parseFloat(prezzoProdottoAggiunta.value),
                quantita: parseInt(quantitaProdottoAggiunta.value),
                disponibile: toggleDisponibilitaAggiunta.checked,
            };

            try {
                const risposta = await fetch("/api/aggiungi_prodotto", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(dati),
                });

                if (!risposta.ok) {
                    const erroreRisposta = await risposta.json();
                    alert("Errore: " + (erroreRisposta.errore || "Impossibile aggiungere prodotto"));
                }
            } catch (errore) {
                console.error("Errore:", errore);
                alert("Errore di connessione.");
            }

            chiudiModaleAggiunta();
        });
    }

    // ==================== Modale: modifica utente ====================
    const modaleModificaUtente = document.getElementById("modaleModificaUtente");
    const formModificaUtente = document.getElementById("formModificaUtente");
    const btnAnnullaModificaUtente = document.getElementById("btnAnnullaModificaUtente");

    // Campi del form utente.
    const idUtenteModifica = document.getElementById("idUtenteModifica");
    const usernameModifica = document.getElementById("usernameModifica");
    const passwordModifica = document.getElementById("passwordModifica");
    const isAdminModifica = document.getElementById("isAdminModifica");
    const isAttivoModifica = document.getElementById("isAttivoModifica");

    window.apriModaleModificaUtente = function (bottone) {
        // Estrae dati utente dai data-attribute del bottone.
        const id = bottone.getAttribute("data-id");
        const username = bottone.getAttribute("data-username");
        const isAdmin = bottone.getAttribute("data-is-admin") === "1";
        const isAttivo = bottone.getAttribute("data-attivo") === "1";

        // Permessi arrivano come stringa "A,B,C".
        const permessiStr = bottone.getAttribute("data-permessi") || "";
        const permessi = permessiStr ? permessiStr.split(",").filter(Boolean) : [];
        const permessiSet = new Set(permessi);

        // Precompila i campi base.
        if (idUtenteModifica) idUtenteModifica.value = id;
        if (usernameModifica) usernameModifica.value = username;
        if (passwordModifica) passwordModifica.value = "";

        // Toggle ruolo amministratore.
        if (isAdminModifica) {
            isAdminModifica.checked = isAdmin;
            isAdminModifica.dispatchEvent(new Event("change"));
        }

        // Toggle stato attivo.
        if (isAttivoModifica) {
            isAttivoModifica.checked = isAttivo;
            isAttivoModifica.dispatchEvent(new Event("change"));
        }

        // Seleziona le checkbox permessi.
        const checkboxPermessi = formModificaUtente ? formModificaUtente.querySelectorAll('input[name="permessi"]') : [];
        checkboxPermessi.forEach((cb) => {
            cb.checked = permessiSet.has(cb.value);
        });

        // Mostra la modale.
        if (modaleModificaUtente) modaleModificaUtente.classList.add("attivo");
    };

    window.chiudiModaleModificaUtente = function () {
        // Chiude la modale modifica utente.
        if (modaleModificaUtente) modaleModificaUtente.classList.remove("attivo");
    };

    if (btnAnnullaModificaUtente) {
        btnAnnullaModificaUtente.addEventListener("click", window.chiudiModaleModificaUtente);
    }

    // Chiude cliccando fuori.
    if (modaleModificaUtente) {
        modaleModificaUtente.addEventListener("click", (e) => {
            if (e.target === modaleModificaUtente) window.chiudiModaleModificaUtente();
        });
    }

    // Invia modifica utente.
    if (formModificaUtente) {
        formModificaUtente.addEventListener("submit", async (e) => {
            e.preventDefault();

            const permessiSelezionati = Array.from(formModificaUtente.querySelectorAll('input[name="permessi"]:checked')).map((cb) => cb.value);
            const permessiUnici = Array.from(new Set(permessiSelezionati));

            const dati = {
                id_utente: idUtenteModifica.value,
                username: usernameModifica.value,
                password: passwordModifica.value,
                is_admin: isAdminModifica.checked,
                attivo: isAttivoModifica.checked,
                permessi: permessiUnici,
            };

            try {
                const risposta = await fetch("/api/modifica_utente", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(dati),
                });

                if (risposta.ok) {
                    // Ricarica pagina per aggiornare la tabella utenti.
                    window.location.reload();
                } else {
                    const erroreRisposta = await risposta.json();
                    alert("Errore: " + (erroreRisposta.errore || "Impossibile modificare utente"));
                }
            } catch (errore) {
                console.error("Errore:", errore);
                alert("Errore di connessione.");
            }

            window.chiudiModaleModificaUtente();
        });
    }

    // ==================== Modale: aggiunta utente ====================
    const modaleAggiuntaUtente = document.getElementById("modaleAggiuntaUtente");
    const formAggiuntaUtente = document.getElementById("formAggiuntaUtente");
    const btnAnnullaAggiuntaUtente = document.getElementById("btnAnnullaAggiuntaUtente");

    // Campi del form di aggiunta.
    const usernameAggiunta = document.getElementById("usernameAggiunta");
    const passwordAggiunta = document.getElementById("passwordAggiunta");
    const isAdminAggiunta = document.getElementById("isAdminAggiunta");
    const isAttivoAggiunta = document.getElementById("isAttivoAggiunta");

    window.apriModaleAggiuntaUtente = function () {
        // Reset e default: utente standard e attivo.
        if (!modaleAggiuntaUtente) return;

        formAggiuntaUtente.reset();

        if (isAdminAggiunta) {
            isAdminAggiunta.checked = false;
            isAdminAggiunta.dispatchEvent(new Event("change"));
        }
        if (isAttivoAggiunta) {
            isAttivoAggiunta.checked = true;
            isAttivoAggiunta.dispatchEvent(new Event("change"));
        }

        modaleAggiuntaUtente.classList.add("attivo");
    };

    window.chiudiModaleAggiuntaUtente = function () {
        // Chiude la modale aggiunta utente.
        if (modaleAggiuntaUtente) modaleAggiuntaUtente.classList.remove("attivo");
    };

    if (btnAnnullaAggiuntaUtente) {
        btnAnnullaAggiuntaUtente.addEventListener("click", window.chiudiModaleAggiuntaUtente);
    }

    // Chiude cliccando fuori.
    if (modaleAggiuntaUtente) {
        modaleAggiuntaUtente.addEventListener("click", (e) => {
            if (e.target === modaleAggiuntaUtente) window.chiudiModaleAggiuntaUtente();
        });
    }

    // Invia creazione utente.
    if (formAggiuntaUtente) {
        formAggiuntaUtente.addEventListener("submit", async (e) => {
            e.preventDefault();

            const permessiSelezionati = Array.from(formAggiuntaUtente.querySelectorAll('input[name="permessi"]:checked')).map((cb) => cb.value);

            const dati = {
                username: usernameAggiunta.value,
                password: passwordAggiunta.value,
                is_admin: isAdminAggiunta.checked,
                attivo: isAttivoAggiunta.checked,
                permessi: permessiSelezionati,
            };

            try {
                const risposta = await fetch("/api/aggiungi_utente", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(dati),
                });

                if (risposta.ok) {
                    window.location.reload();
                } else {
                    const erroreRisposta = await risposta.json();
                    alert("Errore: " + (erroreRisposta.errore || "Impossibile aggiungere utente"));
                }
            } catch (errore) {
                console.error("Errore:", errore);
                alert("Errore di connessione.");
            }

            window.chiudiModaleAggiuntaUtente();
        });
    }

    // ==================== Modale: eliminazione utente ====================
    const modaleEliminaUtente = document.getElementById("modaleEliminaUtente");
    const usernameElimina = document.getElementById("usernameElimina");
    const idUtenteElimina = document.getElementById("idUtenteElimina");
    const btnAnnullaEliminaUtente = document.getElementById("btnAnnullaEliminaUtente");
    const btnConfermaEliminaUtente = document.getElementById("btnConfermaEliminaUtente");

    window.apriModaleEliminaUtente = function (bottone) {
        // Precompila i dati utente da eliminare e mostra la modale.
        const id = bottone.getAttribute("data-id");
        const username = bottone.getAttribute("data-username");

        if (idUtenteElimina) idUtenteElimina.value = id;
        if (usernameElimina) usernameElimina.textContent = username;
        if (modaleEliminaUtente) modaleEliminaUtente.classList.add("attivo");
    };

    window.chiudiModaleEliminaUtente = function () {
        // Chiude la modale eliminazione utente.
        if (modaleEliminaUtente) modaleEliminaUtente.classList.remove("attivo");
    };

    if (btnAnnullaEliminaUtente) {
        btnAnnullaEliminaUtente.addEventListener("click", window.chiudiModaleEliminaUtente);
    }

    // Chiude cliccando fuori.
    if (modaleEliminaUtente) {
        modaleEliminaUtente.addEventListener("click", (e) => {
            if (e.target === modaleEliminaUtente) window.chiudiModaleEliminaUtente();
        });
    }

    // Conferma eliminazione utente.
    if (btnConfermaEliminaUtente) {
        btnConfermaEliminaUtente.addEventListener("click", async () => {
            const id = idUtenteElimina ? idUtenteElimina.value : null;
            if (!id) return;

            try {
                const risposta = await fetch("/api/elimina_utente", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ id_utente: id }),
                });

                if (risposta.ok) {
                    window.location.reload();
                } else {
                    const erroreRisposta = await risposta.json();
                    alert("Errore: " + (erroreRisposta.errore || "Impossibile eliminare utente"));
                }
            } catch (errore) {
                console.error("Errore:", errore);
                alert("Errore di connessione.");
            }

            window.chiudiModaleEliminaUtente();
        });
    }
});
