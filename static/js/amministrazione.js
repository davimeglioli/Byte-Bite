// carica tutte le statistiche dal server
async function caricaStatistiche() {
    const res = await fetch("/api/statistiche/");
    const data = await res.json();
    return data;
}

// aggiorna recap
function aggiornaRecap(totali) {
    const cards = document.querySelectorAll(".recap-card .value");

    cards[0].textContent = totali.ordini_totali;
    cards[1].textContent = totali.ordini_completati;
    cards[2].textContent = totali.totale_incasso.toFixed(2) + " €";
    cards[3].textContent = totali.totale_carta.toFixed(2) + " €";
    cards[4].textContent = totali.totale_contanti.toFixed(2) + " €";
}

// grafico ordini per ora
function creaGraficoOre(ore) {
    new Chart(document.getElementById("grafico1"), {
        type: "line",
        data: {
            labels: ore.map(o => o.ora),
            datasets: [{
                label: "Ordini per ora",
                data: ore.map(o => o.totale),
                borderWidth: 2
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });
}

// grafico categorie dashboard
function creaGraficoCategorie(categorie) {
    new Chart(document.getElementById("grafico2"), {
        type: "pie",
        data: {
            labels: categorie.map(c => c.categoria_dashboard),
            datasets: [{ data: categorie.map(c => c.totale) }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });
}

// completati vs totali
function creaGraficoCompletati(totali) {
    new Chart(document.getElementById("grafico3"), {
        type: "doughnut",
        data: {
            labels: ["Completati", "Non Completati"],
            datasets: [{
                data: [
                    totali.ordini_completati,
                    totali.ordini_totali - totali.ordini_completati
                ]
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });
}

// top 10 prodotti più venduti
function creaGraficoTop10(top10) {
    new Chart(document.getElementById("grafico4"), {
        type: "bar",
        data: {
            labels: top10.map(p => p.nome),
            datasets: [{
                label: "Venduti",
                data: top10.map(p => p.venduti),
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true } }
        }
    });
}

// inizializza la dashboard
document.addEventListener("DOMContentLoaded", async () => {
    const stats = await caricaStatistiche();

    aggiornaRecap(stats.totali);
    creaGraficoOre(stats.ore);
    creaGraficoCategorie(stats.categorie);
    creaGraficoCompletati(stats.totali);
    creaGraficoTop10(stats.top10);
});