let charts = {
    categorie: null,
    ore: null,
    completati: null,
    top10: null
};

let socket = null;
let joined = new Set();
let refreshScheduled = false;

async function caricaStatistiche() {
    const res = await fetch("/api/statistiche/");
    return await res.json();
}

function aggiornaRecap(totali) {
    const cards = document.querySelectorAll(".scheda-statistica .valore-statistica");
    cards[0].textContent = totali.ordini_totali;
    cards[1].textContent = totali.ordini_completati;
    cards[2].textContent = totali.totale_incasso.toFixed(2) + " €";
    cards[3].textContent = totali.totale_carta.toFixed(2) + " €";
    cards[4].textContent = totali.totale_contanti.toFixed(2) + " €";
}

function initCharts(stats) {
    charts.categorie = new Chart(document.getElementById("grafico1"), {
        type: "pie",
        data: {
            labels: stats.categorie.map(c => c.categoria_dashboard),
            datasets: [{ data: stats.categorie.map(c => c.totale) }]
        },
        options: { responsive: true, maintainAspectRatio: true, aspectRatio: 1 }
    });

    charts.ore = new Chart(document.getElementById("grafico2"), {
        type: "line",
        data: {
            labels: stats.ore.map(o => o.ora),
            datasets: [{ label: "Ordini per ora", data: stats.ore.map(o => o.totale), borderWidth: 2 }]
        },
        options: { responsive: true, maintainAspectRatio: true, aspectRatio: 1.2 }
    });

    charts.completati = new Chart(document.getElementById("grafico3"), {
        type: "doughnut",
        data: {
            labels: ["Completati", "Non Completati"],
            datasets: [{ data: [stats.totali.ordini_completati, stats.totali.ordini_totali - stats.totali.ordini_completati] }]
        },
        options: { responsive: true, maintainAspectRatio: true, aspectRatio: 1 }
    });

    charts.top10 = new Chart(document.getElementById("grafico4"), {
        type: "bar",
        data: {
            labels: stats.top10.map(p => p.nome),
            datasets: [{ label: "Venduti", data: stats.top10.map(p => p.venduti), borderWidth: 2 }]
        },
        options: { responsive: true, maintainAspectRatio: true, aspectRatio: 1.2, scales: { y: { beginAtZero: true } } }
    });
}

function aggiornaCharts(stats) {
    charts.categorie.data.labels = stats.categorie.map(c => c.categoria_dashboard);
    charts.categorie.data.datasets[0].data = stats.categorie.map(c => c.totale);
    charts.categorie.update();

    charts.ore.data.labels = stats.ore.map(o => o.ora);
    charts.ore.data.datasets[0].data = stats.ore.map(o => o.totale);
    charts.ore.update();

    charts.completati.data.datasets[0].data = [stats.totali.ordini_completati, stats.totali.ordini_totali - stats.totali.ordini_completati];
    charts.completati.update();

    charts.top10.data.labels = stats.top10.map(p => p.nome);
    charts.top10.data.datasets[0].data = stats.top10.map(p => p.venduti);
    charts.top10.update();
}

function joinRooms(categorie) {
    if (!socket) return;
    categorie.forEach(c => {
        const nome = c.categoria_dashboard;
        if (!joined.has(nome)) {
            socket.emit("join", { categoria: nome });
            joined.add(nome);
        }
    });
}

async function aggiornaTabellaOrdini() {
    const res = await fetch("/api/amministrazione/ordini_html");
    const html = await res.text();
    document.querySelector(".tabella-ordini tbody").innerHTML = html;
}

async function refresh() {
    const stats = await caricaStatistiche();
    aggiornaRecap(stats.totali);
    aggiornaCharts(stats);
    joinRooms(stats.categorie);
    aggiornaTabellaOrdini();
}

function scheduleRefresh() {
    if (refreshScheduled) return;
    refreshScheduled = true;
    setTimeout(async () => {
        await refresh();
        refreshScheduled = false;
    }, 300);
}

document.addEventListener("DOMContentLoaded", async () => {
    const stats = await caricaStatistiche();
    aggiornaRecap(stats.totali);
    initCharts(stats);
    joinRooms(stats.categorie);

    if (typeof io !== "undefined") {
        socket = io();
        socket.on("connect", () => {
            joinRooms(stats.categorie);
        });
        socket.on("aggiorna_dashboard", () => {
            scheduleRefresh();
        });
    }

    // Gestione tab categorie
    const tabs = document.querySelectorAll(".contenitore-menu .linguetta");
    if (tabs.length > 0) {
        // Funzione per filtrare i prodotti
        function filtraProdotti(categoria) {
            const righe = document.querySelectorAll(".tabella-ordini tbody tr[data-categoria]");
            righe.forEach(riga => {
                const catRiga = riga.getAttribute("data-categoria");
                // Se la categoria selezionata è "Tutte" (o simile) o corrisponde, mostra. Altrimenti nascondi.
                // Nota: Assumo che la tab cliccata contenga il nome esatto della categoria dashboard
                if (categoria === "Tutte" || catRiga === categoria) {
                    riga.classList.remove("nascosto");
                } else {
                    riga.classList.add("nascosto");
                }
            });
        }

        // Attiva la prima tab di default e filtra
        tabs[0].classList.add("attiva");
        filtraProdotti(tabs[0].getAttribute("data-categoria") || tabs[0].textContent.trim());
        
        tabs.forEach(tab => {
            tab.addEventListener("click", () => {
                // Rimuovi attiva da tutte
                tabs.forEach(t => t.classList.remove("attiva"));
                // Aggiungi attiva alla cliccata
                tab.classList.add("attiva");
                
                // Filtra la tabella
                const categoria = tab.getAttribute("data-categoria") || tab.textContent.trim();
                filtraProdotti(categoria);
            });
        });
    }

    // --- GESTIONE MODALE RIFORNIMENTO ---
    const modale = document.getElementById('modaleRifornimento');
    const nomeProdottoTarget = document.getElementById('nomeProdottoTarget');
    const idProdottoTarget = document.getElementById('idProdottoTarget');
    const btnAnnulla = document.getElementById('btnAnnulla');
    const formRifornimento = document.getElementById('formRifornimento');

    window.apriModaleRifornimento = function(id, nome) {
        nomeProdottoTarget.textContent = nome;
        idProdottoTarget.value = id;
        modale.classList.add('attivo');
        setTimeout(() => {
            modale.querySelector('input[type="number"]').focus();
        }, 100);
    };

    function chiudiModale() {
        modale.classList.remove('attivo');
        formRifornimento.reset();
    }

    btnAnnulla.addEventListener('click', chiudiModale);

    // Chiudi cliccando fuori
    modale.addEventListener('click', (e) => {
        if (e.target === modale) chiudiModale();
    });

    // Gestione invio form
    formRifornimento.addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = idProdottoTarget.value;
        const quantita = document.getElementById('quantitaInput').value;

        try {
            const response = await fetch('/api/rifornisci_prodotto', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ id: id, quantita: quantita })
            });

            if (response.ok) {
                // Ricarica la tabella o aggiorna la UI
                location.reload(); // Semplice refresh per vedere il nuovo valore
            } else {
                alert('Errore durante il rifornimento.');
            }
        } catch (error) {
            console.error('Errore:', error);
            alert('Errore di connessione.');
        }

        chiudiModale();
    });

    // --- GESTIONE MODALE MODIFICA ---
    const modaleModifica = document.getElementById('modaleModifica');
    const formModifica = document.getElementById('formModifica');
    const btnAnnullaModifica = document.getElementById('btnAnnullaModifica');
    
    // Elementi del form
    const idProdottoModifica = document.getElementById('idProdottoModifica');
    const nomeProdottoModifica = document.getElementById('nomeProdottoModifica');
    const categoriaDashboardModifica = document.getElementById('categoriaDashboardModifica');
    const quantitaProdottoModifica = document.getElementById('quantitaProdottoModifica');
    const toggleDisponibilitaModifica = document.getElementById('toggleDisponibilitaModifica');
    const labelStatoModifica = document.getElementById('labelStatoModifica');

    // Aggiorna label switch
    function aggiornaLabelStato() {
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

    toggleDisponibilitaModifica.addEventListener('change', aggiornaLabelStato);

    // Auto-switch disponibilità in base alla quantità
    quantitaProdottoModifica.addEventListener('input', () => {
        const qta = parseInt(quantitaProdottoModifica.value) || 0;
        if (qta === 0) {
            toggleDisponibilitaModifica.checked = false;
        } else if (qta > 0) {
            toggleDisponibilitaModifica.checked = true;
        }
        aggiornaLabelStato();
    });

    window.apriModaleModifica = function(btn) {
        const id = btn.getAttribute('data-id');
        const nome = btn.getAttribute('data-nome');
        const cat = btn.getAttribute('data-cat');
        const qta = btn.getAttribute('data-qta');
        const disp = btn.getAttribute('data-disp') === '1';

        idProdottoModifica.value = id;
        nomeProdottoModifica.value = nome;
        categoriaDashboardModifica.value = cat;
        quantitaProdottoModifica.value = qta;
        toggleDisponibilitaModifica.checked = disp;
        aggiornaLabelStato();

        modaleModifica.classList.add('attivo');
    };

    function chiudiModaleModifica() {
        modaleModifica.classList.remove('attivo');
    }

    btnAnnullaModifica.addEventListener('click', chiudiModaleModifica);

    // Chiudi cliccando fuori
    modaleModifica.addEventListener('click', (e) => {
        if (e.target === modaleModifica) chiudiModaleModifica();
    });

    // Gestione invio form modifica
    formModifica.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const payload = {
            id: idProdottoModifica.value,
            nome: nomeProdottoModifica.value,
            categoria_dashboard: categoriaDashboardModifica.value,
            quantita: parseInt(quantitaProdottoModifica.value),
            disponibile: toggleDisponibilitaModifica.checked
        };

        try {
            const response = await fetch('/api/modifica_prodotto', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                location.reload();
            } else {
                alert('Errore durante la modifica.');
            }
        } catch (error) {
            console.error('Errore:', error);
            alert('Errore di connessione.');
        }

        chiudiModaleModifica();
    });

    // --- GESTIONE MODALE ELIMINAZIONE ---
    const modaleElimina = document.getElementById('modaleElimina');
    const nomeProdottoElimina = document.getElementById('nomeProdottoElimina');
    const idProdottoElimina = document.getElementById('idProdottoElimina');
    const btnAnnullaElimina = document.getElementById('btnAnnullaElimina');
    const btnConfermaElimina = document.getElementById('btnConfermaElimina');

    window.apriModaleElimina = function(btn) {
        const id = btn.getAttribute('data-id');
        const nome = btn.getAttribute('data-nome');
        
        idProdottoElimina.value = id;
        nomeProdottoElimina.textContent = nome;
        
        modaleElimina.classList.add('attivo');
    };

    function chiudiModaleElimina() {
        modaleElimina.classList.remove('attivo');
    }

    btnAnnullaElimina.addEventListener('click', chiudiModaleElimina);
    
    modaleElimina.addEventListener('click', (e) => {
        if (e.target === modaleElimina) chiudiModaleElimina();
    });

    btnConfermaElimina.addEventListener('click', async () => {
        const id = idProdottoElimina.value;
        if (!id) return;

        try {
            const response = await fetch('/api/elimina_prodotto', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id })
            });

            if (response.ok) {
                location.reload();
            } else {
                alert('Errore durante l\'eliminazione.');
            }
        } catch (error) {
            console.error('Errore:', error);
            alert('Errore di connessione.');
        }
        chiudiModaleElimina();
    });
});
