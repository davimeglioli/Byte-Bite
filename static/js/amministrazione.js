// ==================== Utilità ====================
function escapaHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

function aggiornaToggleLabelDisponibilita(toggle, label) {
    if (!toggle || !label) return;
    const disponibile = toggle.checked;
    label.textContent = disponibile ? "Disponibile" : "Non disponibile";
    label.classList.toggle("testo-attivo", disponibile);
    label.classList.toggle("testo-inattivo", !disponibile);
}

// ==================== Icone SVG condivise ====================
const SVG_MODIFICA = `<svg viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>`;
const SVG_ELIMINA = `<svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/></svg>`;
const SVG_RIFORNIMENTO = `<svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`;

// ==================== Stato pagina ====================
let grafici = {
    categorie: null,
    ore: null,
    completati: null,
    top10: null,
};

let socket = null;
let stanzeIscritte = new Set();

// ==================== Statistiche e grafici ====================
async function caricaStatistiche() {
    const risposta = await fetch("/api/statistiche");
    return await risposta.json();
}

function aggiornaRecap(totali) {
    const schede = document.querySelectorAll(".scheda-statistica .valore-statistica");
    schede[0].textContent = totali.ordini_totali;
    schede[1].textContent = totali.ordini_completati;
    schede[2].textContent = totali.totale_incasso.toFixed(2) + " €";
    schede[3].textContent = totali.totale_carta.toFixed(2) + " €";
    schede[4].textContent = totali.totale_contanti.toFixed(2) + " €";
}

function inizializzaGrafici(statistiche) {
    grafici.categorie = new Chart(document.getElementById("grafico1"), {
        type: "pie",
        data: {
            labels: statistiche.categorie.map((c) => c.categoria_dashboard),
            datasets: [{ data: statistiche.categorie.map((c) => c.totale) }],
        },
        options: { responsive: true, maintainAspectRatio: true, aspectRatio: 1 },
    });

    grafici.ore = new Chart(document.getElementById("grafico2"), {
        type: "line",
        data: {
            labels: statistiche.ore.map((o) => o.ora),
            datasets: [{ label: "Ordini per ora", data: statistiche.ore.map((o) => o.totale), borderWidth: 2 }],
        },
        options: { responsive: true, maintainAspectRatio: true, aspectRatio: 1.2 },
    });

    grafici.completati = new Chart(document.getElementById("grafico3"), {
        type: "doughnut",
        data: {
            labels: ["Completati", "Non Completati"],
            datasets: [{
                data: [
                    statistiche.totali.ordini_completati,
                    statistiche.totali.ordini_totali - statistiche.totali.ordini_completati,
                ],
            }],
        },
        options: { responsive: true, maintainAspectRatio: true, aspectRatio: 1 },
    });

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
    grafici.categorie.data.labels = statistiche.categorie.map((c) => c.categoria_dashboard);
    grafici.categorie.data.datasets[0].data = statistiche.categorie.map((c) => c.totale);
    grafici.categorie.update();

    grafici.ore.data.labels = statistiche.ore.map((o) => o.ora);
    grafici.ore.data.datasets[0].data = statistiche.ore.map((o) => o.totale);
    grafici.ore.update();

    grafici.completati.data.datasets[0].data = [
        statistiche.totali.ordini_completati,
        statistiche.totali.ordini_totali - statistiche.totali.ordini_completati,
    ];
    grafici.completati.update();

    grafici.top10.data.labels = statistiche.top10.map((p) => p.nome);
    grafici.top10.data.datasets[0].data = statistiche.top10.map((p) => p.venduti);
    grafici.top10.update();
}

// ==================== Realtime ====================
function iscrivitiStanze(_categorie) {
    if (!socket) return;
    const stanza = "amministrazione";
    if (stanzeIscritte.has(stanza)) return;
    socket.emit("join", { categoria: stanza });
    stanzeIscritte.add(stanza);
}

// ==================== Tabelle e filtri ====================
function renderizzaTabellaOrdini(ordini) {
    const righe = ordini.map((o) => `
      <tr class="riga-ordine" data-id="${o.id}">
        <td>${o.id}</td>
        <td>${escapaHtml(o.nome_cliente)}</td>
        <td>${o.numero_tavolo ?? "-"}</td>
        <td>${o.numero_persone ?? "-"}</td>
        <td>${o.data_ordine}</td>
        <td>${escapaHtml(o.metodo_pagamento)}</td>
        <td>${o.totale.toFixed(2)} €</td>
        <td>
          <button class="bottone-modifica" onclick="apriModaleModificaOrdine(this)" aria-label="Modifica">${SVG_MODIFICA}</button>
          <button class="bottone-cancella" data-id="${o.id}" onclick="apriModaleEliminaOrdine(this)" aria-label="Elimina">${SVG_ELIMINA}</button>
        </td>
        <td>
          <button class="bottone-espandi" data-id="${o.id}" onclick="toggleDettagli(this)">
            <span class="espandi"></span>
          </button>
        </td>
      </tr>`).join("");
    document.querySelector(".tabella-dati tbody").innerHTML = righe;
}

async function aggiornaTabellaOrdini() {
    const risposta = await fetch("/api/ordini");
    const dati = await risposta.json();
    renderizzaTabellaOrdini(dati.ordini);
}

function filtraProdotti(categoria) {
    const righe = document.querySelectorAll(".tabella-dati tbody tr[data-categoria]");
    righe.forEach((riga) => {
        const categoriaRiga = riga.getAttribute("data-categoria");
        riga.classList.toggle("nascosto", categoria !== "Tutte" && categoriaRiga !== categoria);
    });
}

function renderizzaTabellaProdotti(prodotti) {
    const righe = prodotti.map((p) => `
      <tr data-categoria="${escapaHtml(p.categoria_menu)}">
        <td>${p.id}</td>
        <td>${escapaHtml(p.nome)}</td>
        <td>${escapaHtml(p.categoria_dashboard)}</td>
        <td>${p.prezzo.toFixed(2)} €</td>
        <td>${p.disponibile ? "Disponibile" : "Non disponibile"}</td>
        <td>${p.quantita}</td>
        <td>${p.venduti}</td>
        <td>
          <button class="bottone-rifornimento" onclick="apriModaleRifornimento('${p.id}', '${escapaHtml(p.nome)}')" aria-label="Rifornisci">${SVG_RIFORNIMENTO}</button>
          <button class="bottone-modifica" data-id="${p.id}" data-nome="${escapaHtml(p.nome)}" data-cat="${escapaHtml(p.categoria_dashboard)}" data-prezzo="${p.prezzo}" data-qta="${p.quantita}" data-disp="${p.disponibile ? 1 : 0}" onclick="apriModaleModifica(this)" aria-label="Modifica">${SVG_MODIFICA}</button>
          <button class="bottone-cancella" data-id="${p.id}" data-nome="${escapaHtml(p.nome)}" onclick="apriModaleElimina(this)" aria-label="Elimina">${SVG_ELIMINA}</button>
        </td>
      </tr>`).join("");

    // The page has two tbody elements with the same class: [0]=ordini, [1]=prodotti.
    const tbodyTabelle = document.querySelectorAll(".tabella-dati tbody");
    if (tbodyTabelle.length < 2) return;
    tbodyTabelle[1].innerHTML = righe;

    const tabAttiva = document.querySelector(".contenitore-menu .linguetta.attiva");
    if (!tabAttiva) return;
    filtraProdotti(tabAttiva.getAttribute("data-categoria") || tabAttiva.textContent.trim());
}

async function aggiornaTabellaProdotti() {
    const risposta = await fetch("/api/prodotti");
    const dati = await risposta.json();
    renderizzaTabellaProdotti(dati.prodotti);
}

async function toggleDettagli(bottone) {
    const idOrdine = bottone.getAttribute("data-id");
    const rigaOrdine = bottone.closest("tr");
    const rigaSuccessiva = rigaOrdine.nextElementSibling;
    const espanso = bottone.classList.contains("attivo");

    if (espanso) {
        bottone.classList.remove("attivo");
        if (rigaSuccessiva && rigaSuccessiva.classList.contains("riga-dettagli")) {
            rigaSuccessiva.remove();
        }
        return;
    }

    bottone.classList.add("attivo");
    if (rigaSuccessiva && rigaSuccessiva.classList.contains("riga-dettagli")) {
        rigaSuccessiva.remove();
    }

    try {
        const risposta = await fetch(`/api/ordini/${idOrdine}`);
        if (!risposta.ok) throw new Error("Errore nel caricamento dei dettagli");
        const dati = await risposta.json();

        const badgeClass = (stato) => ({
            "In Attesa": "etichetta-in-attesa",
            "In Preparazione": "etichetta-in-preparazione",
            "Pronto": "etichetta-pronto",
            "Completato": "etichetta-completato",
        }[stato] || "etichetta-base");

        const righeDettagli = dati.prodotti.map((p) => `
          <tr>
            <td>${escapaHtml(p.nome)}</td>
            <td>${escapaHtml(p.categoria_menu)}</td>
            <td>${p.quantita}</td>
            <td>€${p.prezzo.toFixed(2)}</td>
            <td>€${p.subtotale.toFixed(2)}</td>
            <td><span class="etichetta-dettaglio ${badgeClass(p.stato)}">${escapaHtml(p.stato)}</span></td>
          </tr>`).join("");

        const html = `
          <tr class="riga-dettagli" id="dettagli-${dati.id}">
            <td colspan="10" class="cella-dettagli-ordine">
              <div class="dettagli-ordine-contenitore">
                <h4 class="dettagli-ordine-titolo">Prodotti dell'ordine:</h4>
                <table class="dettagli-ordine-tabella">
                  <thead class="dettagli-ordine-intestazione">
                    <tr>
                      <th>Prodotto</th><th>Categoria</th><th>Quantità</th>
                      <th>Prezzo</th><th>Subtotale</th><th>Stato</th>
                    </tr>
                  </thead>
                  <tbody>${righeDettagli}</tbody>
                </table>
                <div class="dettagli-ordine-totale">
                  <span class="dettagli-ordine-totale-testo">Totale ordine: €${dati.totale.toFixed(2)}</span>
                </div>
              </div>
            </td>
          </tr>`;
        rigaOrdine.insertAdjacentHTML("afterend", html);
    } catch (errore) {
        console.error("Errore:", errore);
        alert("Impossibile caricare i dettagli dell'ordine.");
        bottone.classList.remove("attivo");
    }
}

// ==================== Aggiornamento pagina ====================
async function aggiornaTutto() {
    const statistiche = await caricaStatistiche();
    aggiornaRecap(statistiche.totali);
    aggiornaGrafici(statistiche);
    iscrivitiStanze(statistiche.categorie);
    aggiornaTabellaOrdini();
    aggiornaTabellaProdotti();
}


document.addEventListener("DOMContentLoaded", () => {
    // ==================== Filtri prodotti (linguette categorie) ====================
    const linguetteCategorie = document.querySelectorAll(".contenitore-menu .linguetta");
    if (linguetteCategorie.length > 0) {
        linguetteCategorie[0].classList.add("attiva");
        filtraProdotti(linguetteCategorie[0].getAttribute("data-categoria") || linguetteCategorie[0].textContent.trim());

        linguetteCategorie.forEach((linguetta) => {
            linguetta.addEventListener("click", () => {
                linguetteCategorie.forEach((t) => t.classList.remove("attiva"));
                linguetta.classList.add("attiva");
                filtraProdotti(linguetta.getAttribute("data-categoria") || linguetta.textContent.trim());
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
        nomeProdottoTarget.textContent = nome;
        idProdottoTarget.value = id;
        modaleRifornimento.classList.add("attivo");
        setTimeout(() => {
            modaleRifornimento.querySelector('input[type="number"]').focus();
        }, 100);
    };

    function chiudiModaleRifornimento() {
        modaleRifornimento.classList.remove("attivo");
        formRifornimento.reset();
    }

    btnAnnulla.addEventListener("click", chiudiModaleRifornimento);
    modaleRifornimento.addEventListener("click", (e) => {
        if (e.target === modaleRifornimento) chiudiModaleRifornimento();
    });

    formRifornimento.addEventListener("submit", async (e) => {
        e.preventDefault();
        const id = idProdottoTarget.value;
        const quantita = document.getElementById("quantitaInput").value;
        try {
            const risposta = await fetch(`/api/prodotti/${id}/rifornimento`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ quantita: quantita }),
            });
            if (!risposta.ok) alert("Errore durante il rifornimento.");
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

    const idProdottoModifica = document.getElementById("idProdottoModifica");
    const nomeProdottoModifica = document.getElementById("nomeProdottoModifica");
    const categoriaDashboardModifica = document.getElementById("categoriaDashboardModifica");
    const prezzoProdottoModifica = document.getElementById("prezzoProdottoModifica");
    const quantitaProdottoModifica = document.getElementById("quantitaProdottoModifica");
    const toggleDisponibilitaModifica = document.getElementById("toggleDisponibilitaModifica");
    const labelStatoModifica = document.getElementById("labelStatoModifica");

    toggleDisponibilitaModifica.addEventListener("change", () =>
        aggiornaToggleLabelDisponibilita(toggleDisponibilitaModifica, labelStatoModifica)
    );
    quantitaProdottoModifica.addEventListener("input", () => {
        toggleDisponibilitaModifica.checked = (parseInt(quantitaProdottoModifica.value) || 0) > 0;
        aggiornaToggleLabelDisponibilita(toggleDisponibilitaModifica, labelStatoModifica);
    });

    window.apriModaleModifica = function (bottone) {
        idProdottoModifica.value = bottone.getAttribute("data-id");
        nomeProdottoModifica.value = bottone.getAttribute("data-nome");
        categoriaDashboardModifica.value = bottone.getAttribute("data-cat");
        prezzoProdottoModifica.value = bottone.getAttribute("data-prezzo");
        quantitaProdottoModifica.value = bottone.getAttribute("data-qta");
        toggleDisponibilitaModifica.checked = bottone.getAttribute("data-disp") === "1";
        aggiornaToggleLabelDisponibilita(toggleDisponibilitaModifica, labelStatoModifica);
        modaleModifica.classList.add("attivo");
    };

    function chiudiModaleModifica() {
        modaleModifica.classList.remove("attivo");
    }

    btnAnnullaModifica.addEventListener("click", chiudiModaleModifica);
    modaleModifica.addEventListener("click", (e) => {
        if (e.target === modaleModifica) chiudiModaleModifica();
    });

    formModifica.addEventListener("submit", async (e) => {
        e.preventDefault();
        const id = idProdottoModifica.value;
        const dati = {
            nome: nomeProdottoModifica.value,
            categoria_dashboard: categoriaDashboardModifica.value,
            prezzo: parseFloat(prezzoProdottoModifica.value),
            quantita: parseInt(quantitaProdottoModifica.value),
            disponibile: toggleDisponibilitaModifica.checked,
        };
        try {
            const risposta = await fetch(`/api/prodotti/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(dati),
            });
            if (!risposta.ok) alert("Errore durante la modifica.");
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
        idProdottoElimina.value = bottone.getAttribute("data-id");
        nomeProdottoElimina.textContent = bottone.getAttribute("data-nome");
        modaleElimina.classList.add("attivo");
    };

    function chiudiModaleElimina() {
        modaleElimina.classList.remove("attivo");
    }

    btnAnnullaElimina.addEventListener("click", chiudiModaleElimina);
    modaleElimina.addEventListener("click", (e) => {
        if (e.target === modaleElimina) chiudiModaleElimina();
    });

    btnConfermaElimina.addEventListener("click", async () => {
        const id = idProdottoElimina.value;
        if (!id) return;
        try {
            const risposta = await fetch(`/api/prodotti/${id}`, { method: "DELETE" });
            if (!risposta.ok) alert("Errore durante l'eliminazione.");
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
        const id = bottone.getAttribute("data-id");
        if (idOrdineHidden) idOrdineHidden.value = id;
        if (idOrdineElimina) idOrdineElimina.textContent = id;
        if (modaleEliminaOrdine) modaleEliminaOrdine.classList.add("attivo");
    };

    function chiudiModaleEliminaOrdine() {
        if (modaleEliminaOrdine) modaleEliminaOrdine.classList.remove("attivo");
    }

    if (btnAnnullaEliminaOrdine) {
        btnAnnullaEliminaOrdine.addEventListener("click", chiudiModaleEliminaOrdine);
    }
    if (modaleEliminaOrdine) {
        modaleEliminaOrdine.addEventListener("click", (e) => {
            if (e.target === modaleEliminaOrdine) chiudiModaleEliminaOrdine();
        });
    }

    if (btnConfermaEliminaOrdine) {
        btnConfermaEliminaOrdine.addEventListener("click", async () => {
            const id = idOrdineHidden ? idOrdineHidden.value : null;
            if (!id) return;
            try {
                const risposta = await fetch(`/api/ordini/${id}`, { method: "DELETE" });
                if (!risposta.ok) alert("Errore durante l'eliminazione dell'ordine.");
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

    const idOrdineModifica = document.getElementById("idOrdineModifica");
    const clienteModifica = document.getElementById("clienteModifica");
    const tavoloModifica = document.getElementById("tavoloModifica");
    const personeModifica = document.getElementById("personeModifica");
    const pagamentoModifica = document.getElementById("pagamentoModifica");

    window.apriModaleModificaOrdine = function (bottone) {
        const riga = bottone.closest("tr");
        const celle = riga.querySelectorAll("td");
        const id = riga.getAttribute("data-id");
        const tavolo = celle[2].textContent.trim();
        const persone = celle[3].textContent.trim();

        if (idOrdineModifica) idOrdineModifica.value = id;
        if (clienteModifica) clienteModifica.value = celle[1].textContent.trim();
        if (tavoloModifica) tavoloModifica.value = tavolo === "-" ? "" : tavolo;
        if (personeModifica) personeModifica.value = persone === "-" ? "" : persone;
        if (pagamentoModifica) pagamentoModifica.value = celle[5].textContent.trim();
        if (modaleModificaOrdine) modaleModificaOrdine.classList.add("attivo");
    };

    window.chiudiModaleModificaOrdine = function () {
        if (modaleModificaOrdine) modaleModificaOrdine.classList.remove("attivo");
    };

    if (modaleModificaOrdine) {
        modaleModificaOrdine.addEventListener("click", (e) => {
            if (e.target === modaleModificaOrdine) window.chiudiModaleModificaOrdine();
        });
    }

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
                const risposta = await fetch(`/api/ordini/${idOrdineModifica.value}`, {
                    method: "PUT",
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

    const nomeProdottoAggiunta = document.getElementById("nomeProdottoAggiunta");
    const categoriaDashboardAggiunta = document.getElementById("categoriaDashboardAggiunta");
    const categoriaMenuAggiunta = document.getElementById("categoriaMenuAggiunta");
    const prezzoProdottoAggiunta = document.getElementById("prezzoProdottoAggiunta");
    const quantitaProdottoAggiunta = document.getElementById("quantitaProdottoAggiunta");
    const toggleDisponibilitaAggiunta = document.getElementById("toggleDisponibilitaAggiunta");
    const labelStatoAggiunta = document.getElementById("labelStatoAggiunta");

    if (toggleDisponibilitaAggiunta) {
        toggleDisponibilitaAggiunta.addEventListener("change", () =>
            aggiornaToggleLabelDisponibilita(toggleDisponibilitaAggiunta, labelStatoAggiunta)
        );
    }
    if (quantitaProdottoAggiunta) {
        quantitaProdottoAggiunta.addEventListener("input", () => {
            toggleDisponibilitaAggiunta.checked = (parseInt(quantitaProdottoAggiunta.value) || 0) > 0;
            aggiornaToggleLabelDisponibilita(toggleDisponibilitaAggiunta, labelStatoAggiunta);
        });
    }

    window.apriModaleAggiunta = function () {
        if (!modaleAggiunta) return;
        formAggiunta.reset();
        if (toggleDisponibilitaAggiunta) toggleDisponibilitaAggiunta.checked = true;
        aggiornaToggleLabelDisponibilita(toggleDisponibilitaAggiunta, labelStatoAggiunta);
        modaleAggiunta.classList.add("attivo");
    };

    function chiudiModaleAggiunta() {
        if (modaleAggiunta) modaleAggiunta.classList.remove("attivo");
    }

    if (btnAnnullaAggiunta) {
        btnAnnullaAggiunta.addEventListener("click", chiudiModaleAggiunta);
    }
    if (modaleAggiunta) {
        modaleAggiunta.addEventListener("click", (e) => {
            if (e.target === modaleAggiunta) chiudiModaleAggiunta();
        });
    }

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
                const risposta = await fetch("/api/prodotti", {
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

    const idUtenteModifica = document.getElementById("idUtenteModifica");
    const usernameModifica = document.getElementById("usernameModifica");
    const passwordModifica = document.getElementById("passwordModifica");
    const isAdminModifica = document.getElementById("isAdminModifica");
    const isAttivoModifica = document.getElementById("isAttivoModifica");

    window.apriModaleModificaUtente = function (bottone) {
        const id = bottone.getAttribute("data-id");
        const isAdmin = bottone.getAttribute("data-is-admin") === "1";
        const isAttivo = bottone.getAttribute("data-attivo") === "1";
        const permessiStr = bottone.getAttribute("data-permessi") || "";
        const permessiSet = new Set(permessiStr ? permessiStr.split(",").filter(Boolean) : []);

        if (idUtenteModifica) idUtenteModifica.value = id;
        if (usernameModifica) usernameModifica.value = bottone.getAttribute("data-username");
        if (passwordModifica) passwordModifica.value = "";

        if (isAdminModifica) {
            isAdminModifica.checked = isAdmin;
            isAdminModifica.dispatchEvent(new Event("change"));
        }
        if (isAttivoModifica) {
            isAttivoModifica.checked = isAttivo;
            isAttivoModifica.dispatchEvent(new Event("change"));
        }

        const checkboxPermessi = formModificaUtente ? formModificaUtente.querySelectorAll('input[name="permessi"]') : [];
        checkboxPermessi.forEach((cb) => {
            cb.checked = permessiSet.has(cb.value);
        });

        if (modaleModificaUtente) modaleModificaUtente.classList.add("attivo");
    };

    window.chiudiModaleModificaUtente = function () {
        if (modaleModificaUtente) modaleModificaUtente.classList.remove("attivo");
    };

    if (btnAnnullaModificaUtente) {
        btnAnnullaModificaUtente.addEventListener("click", window.chiudiModaleModificaUtente);
    }
    if (modaleModificaUtente) {
        modaleModificaUtente.addEventListener("click", (e) => {
            if (e.target === modaleModificaUtente) window.chiudiModaleModificaUtente();
        });
    }

    if (formModificaUtente) {
        formModificaUtente.addEventListener("submit", async (e) => {
            e.preventDefault();
            const permessiUnici = Array.from(
                new Set(
                    Array.from(formModificaUtente.querySelectorAll('input[name="permessi"]:checked')).map((cb) => cb.value)
                )
            );
            const dati = {
                id_utente: idUtenteModifica.value,
                username: usernameModifica.value,
                password: passwordModifica.value,
                is_admin: isAdminModifica.checked,
                attivo: isAttivoModifica.checked,
                permessi: permessiUnici,
            };
            try {
                const risposta = await fetch(`/api/utenti/${dati.id_utente}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(dati),
                });
                if (risposta.ok) {
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

    const usernameAggiunta = document.getElementById("usernameAggiunta");
    const passwordAggiunta = document.getElementById("passwordAggiunta");
    const isAdminAggiunta = document.getElementById("isAdminAggiunta");
    const isAttivoAggiunta = document.getElementById("isAttivoAggiunta");

    window.apriModaleAggiuntaUtente = function () {
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
        if (modaleAggiuntaUtente) modaleAggiuntaUtente.classList.remove("attivo");
    };

    if (btnAnnullaAggiuntaUtente) {
        btnAnnullaAggiuntaUtente.addEventListener("click", window.chiudiModaleAggiuntaUtente);
    }
    if (modaleAggiuntaUtente) {
        modaleAggiuntaUtente.addEventListener("click", (e) => {
            if (e.target === modaleAggiuntaUtente) window.chiudiModaleAggiuntaUtente();
        });
    }

    if (formAggiuntaUtente) {
        formAggiuntaUtente.addEventListener("submit", async (e) => {
            e.preventDefault();
            const permessiSelezionati = Array.from(
                formAggiuntaUtente.querySelectorAll('input[name="permessi"]:checked')
            ).map((cb) => cb.value);
            const dati = {
                username: usernameAggiunta.value,
                password: passwordAggiunta.value,
                is_admin: isAdminAggiunta.checked,
                attivo: isAttivoAggiunta.checked,
                permessi: permessiSelezionati,
            };
            try {
                const risposta = await fetch("/api/utenti", {
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
        if (idUtenteElimina) idUtenteElimina.value = bottone.getAttribute("data-id");
        if (usernameElimina) usernameElimina.textContent = bottone.getAttribute("data-username");
        if (modaleEliminaUtente) modaleEliminaUtente.classList.add("attivo");
    };

    window.chiudiModaleEliminaUtente = function () {
        if (modaleEliminaUtente) modaleEliminaUtente.classList.remove("attivo");
    };

    if (btnAnnullaEliminaUtente) {
        btnAnnullaEliminaUtente.addEventListener("click", window.chiudiModaleEliminaUtente);
    }
    if (modaleEliminaUtente) {
        modaleEliminaUtente.addEventListener("click", (e) => {
            if (e.target === modaleEliminaUtente) window.chiudiModaleEliminaUtente();
        });
    }

    if (btnConfermaEliminaUtente) {
        btnConfermaEliminaUtente.addEventListener("click", async () => {
            const id = idUtenteElimina ? idUtenteElimina.value : null;
            if (!id) return;
            try {
                const risposta = await fetch(`/api/utenti/${id}`, { method: "DELETE" });
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

    avviaDati();
});

async function avviaDati() {
    const statistiche = await caricaStatistiche();
    aggiornaRecap(statistiche.totali);
    inizializzaGrafici(statistiche);
    iscrivitiStanze(statistiche.categorie);

    if (typeof io !== "undefined") {
        socket = io("/admin", { transports: ["websocket"], upgrade: false });
        socket.on("connect", () => {
            iscrivitiStanze(statistiche.categorie);
        });
        socket.on("aggiorna_admin", (dati) => {
            renderizzaTabellaOrdini(dati.ordini);
            renderizzaTabellaProdotti(dati.prodotti);
        });
        socket.on("aggiorna_statistiche", (statistiche) => {
            aggiornaRecap(statistiche.totali);
            aggiornaGrafici(statistiche);
        });
    }
}
