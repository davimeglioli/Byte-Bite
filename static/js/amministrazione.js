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
    const cards = document.querySelectorAll(".recap-card .value");
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

async function refresh() {
    const stats = await caricaStatistiche();
    aggiornaRecap(stats.totali);
    aggiornaCharts(stats);
    joinRooms(stats.categorie);
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
});
