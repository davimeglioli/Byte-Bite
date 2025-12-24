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

async function aggiornaTabellaProdotti() {
    const res = await fetch("/api/amministrazione/prodotti_html");
    const html = await res.text();
    // La seconda tabella nella pagina è quella dei prodotti
    // Usiamo un selettore più specifico basato sulla struttura HTML
    const tabelle = document.querySelectorAll(".tabella-ordini tbody");
    if (tabelle.length >= 2) {
        tabelle[1].innerHTML = html;
    }
}

async function toggleDettagli(btn) {
    const ordineId = btn.getAttribute('data-id');
    const tr = btn.closest('tr');
    const nextTr = tr.nextElementSibling;
    const isExpanded = btn.classList.contains('attivo');

    if (isExpanded) {
        // Chiudi
        btn.classList.remove('attivo');
        if (nextTr && nextTr.classList.contains('riga-dettagli')) {
            nextTr.remove();
        }
    } else {
        // Espandi
        // Chiudi eventuali altri dettagli aperti (opzionale, ma mantiene la UI pulita)
        // document.querySelectorAll('.bottone-espandi.attivo').forEach(b => {
        //     if (b !== btn) toggleDettagli(b);
        // });

        btn.classList.add('attivo');
        
        // Rimuovi dettagli esistenti se presenti per errore
        if (nextTr && nextTr.classList.contains('riga-dettagli')) {
            nextTr.remove();
        }

        try {
            const response = await fetch(`/api/ordine/${ordineId}/dettagli`);
            if (!response.ok) throw new Error('Errore nel caricamento dei dettagli');
            const html = await response.text();
            tr.insertAdjacentHTML('afterend', html);
        } catch (error) {
            console.error('Errore:', error);
            alert('Impossibile caricare i dettagli dell\'ordine.');
            btn.classList.remove('attivo');
        }
    }
}

async function refresh() {
    const stats = await caricaStatistiche();
    aggiornaRecap(stats.totali);
    aggiornaCharts(stats);
    joinRooms(stats.categorie);
    aggiornaTabellaOrdini();
    aggiornaTabellaProdotti();
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
                // Ricarica gestita da socket
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
                // Ricarica gestita da socket
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
                // Ricarica gestita da socket
            } else {
                alert('Errore durante l\'eliminazione.');
            }
        } catch (error) {
            console.error('Errore:', error);
            alert('Errore di connessione.');
        }
        chiudiModaleElimina();
    });

    // --- GESTIONE MODALE ELIMINAZIONE ORDINE ---
    const modaleEliminaOrdine = document.getElementById('modaleEliminaOrdine');
    const idOrdineElimina = document.getElementById('idOrdineElimina');
    const idOrdineHidden = document.getElementById('idOrdineHidden');
    const btnAnnullaEliminaOrdine = document.getElementById('btnAnnullaEliminaOrdine');
    const btnConfermaEliminaOrdine = document.getElementById('btnConfermaEliminaOrdine');

    window.apriModaleEliminaOrdine = function(btn) {
        const id = btn.getAttribute('data-id');
        if (idOrdineHidden) idOrdineHidden.value = id;
        if (idOrdineElimina) idOrdineElimina.textContent = id;
        if (modaleEliminaOrdine) modaleEliminaOrdine.classList.add('attivo');
    };

    function chiudiModaleEliminaOrdine() {
        if (modaleEliminaOrdine) modaleEliminaOrdine.classList.remove('attivo');
    }

    if (btnAnnullaEliminaOrdine) {
        btnAnnullaEliminaOrdine.addEventListener('click', chiudiModaleEliminaOrdine);
    }
    
    if (modaleEliminaOrdine) {
        modaleEliminaOrdine.addEventListener('click', (e) => {
            if (e.target === modaleEliminaOrdine) chiudiModaleEliminaOrdine();
        });
    }

    if (btnConfermaEliminaOrdine) {
        btnConfermaEliminaOrdine.addEventListener('click', async () => {
            const id = idOrdineHidden ? idOrdineHidden.value : null;
            if (!id) return;

            try {
                const response = await fetch('/api/elimina_ordine', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: id })
                });

                if (response.ok) {
                    // Ricarica gestita da socket
                } else {
                    alert('Errore durante l\'eliminazione dell\'ordine.');
                }
            } catch (error) {
                console.error('Errore:', error);
                alert('Errore di connessione.');
            }
            chiudiModaleEliminaOrdine();
        });
    }

    // --- GESTIONE MODALE MODIFICA ORDINE ---
    const modaleModificaOrdine = document.getElementById('modaleModificaOrdine');
    const formModificaOrdine = document.getElementById('formModificaOrdine');
    
    // Inputs
    const idOrdineModifica = document.getElementById('idOrdineModifica');
    const clienteModifica = document.getElementById('clienteModifica');
    const tavoloModifica = document.getElementById('tavoloModifica');
    const personeModifica = document.getElementById('personeModifica');
    const pagamentoModifica = document.getElementById('pagamentoModifica');

    window.apriModaleModificaOrdine = function(btn) {
        const tr = btn.closest('tr');
        const cells = tr.querySelectorAll('td');
        
        // Assumo che l'ordine delle colonne sia:
        // 0: ID, 1: Cliente, 2: Tavolo, 3: Persone, 4: Data, 5: Pagamento, 6: Totale, 7: Azioni, 8: Dettagli
        
        const id = tr.getAttribute('data-id');
        const cliente = cells[1].textContent.trim();
        const tavolo = cells[2].textContent.trim();
        const persone = cells[3].textContent.trim();
        const pagamento = cells[5].textContent.trim();

        if (idOrdineModifica) idOrdineModifica.value = id;
        if (clienteModifica) clienteModifica.value = cliente;
        if (tavoloModifica) tavoloModifica.value = (tavolo === '-' || tavolo === '') ? '' : tavolo;
        if (personeModifica) personeModifica.value = (persone === '-' || persone === '') ? '' : persone;
        if (pagamentoModifica) pagamentoModifica.value = pagamento;

        if (modaleModificaOrdine) modaleModificaOrdine.classList.add('attivo');
    };

    window.chiudiModaleModificaOrdine = function() {
        if (modaleModificaOrdine) modaleModificaOrdine.classList.remove('attivo');
    };

    if (modaleModificaOrdine) {
        modaleModificaOrdine.addEventListener('click', (e) => {
            if (e.target === modaleModificaOrdine) chiudiModaleModificaOrdine();
        });
    }

    if (formModificaOrdine) {
        formModificaOrdine.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const data = {
                id_ordine: idOrdineModifica.value,
                nome_cliente: clienteModifica.value,
                numero_tavolo: tavoloModifica.value,
                numero_persone: personeModifica.value,
                metodo_pagamento: pagamentoModifica.value
            };

            try {
                const response = await fetch('/api/modifica_ordine', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (response.ok) {
                    // Ricarica gestita da socket
                } else {
                    const err = await response.json();
                    alert('Errore: ' + (err.errore || 'Impossibile modificare ordine'));
                }
            } catch (error) {
                console.error('Errore:', error);
                alert('Errore di connessione.');
            }
            
            chiudiModaleModificaOrdine();
        });
    }

    // --- GESTIONE MODALE AGGIUNTA PRODOTTO ---
    const modaleAggiunta = document.getElementById('modaleAggiunta');
    const formAggiunta = document.getElementById('formAggiunta');
    const btnAnnullaAggiunta = document.getElementById('btnAnnullaAggiunta');
    
    // Inputs
    const nomeProdottoAggiunta = document.getElementById('nomeProdottoAggiunta');
    const categoriaDashboardAggiunta = document.getElementById('categoriaDashboardAggiunta');
    const categoriaMenuAggiunta = document.getElementById('categoriaMenuAggiunta');
    const prezzoProdottoAggiunta = document.getElementById('prezzoProdottoAggiunta');
    const quantitaProdottoAggiunta = document.getElementById('quantitaProdottoAggiunta');
    const toggleDisponibilitaAggiunta = document.getElementById('toggleDisponibilitaAggiunta');
    const labelStatoAggiunta = document.getElementById('labelStatoAggiunta');

    // Aggiorna label switch
    function aggiornaLabelStatoAggiunta() {
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

    if (toggleDisponibilitaAggiunta) {
        toggleDisponibilitaAggiunta.addEventListener('change', aggiornaLabelStatoAggiunta);
    }

    // Auto-switch disponibilità in base alla quantità
    if (quantitaProdottoAggiunta) {
        quantitaProdottoAggiunta.addEventListener('input', () => {
            const qta = parseInt(quantitaProdottoAggiunta.value) || 0;
            if (qta === 0) {
                toggleDisponibilitaAggiunta.checked = false;
            } else if (qta > 0) {
                toggleDisponibilitaAggiunta.checked = true;
            }
            aggiornaLabelStatoAggiunta();
        });
    }

    window.apriModaleAggiunta = function() {
        if (!modaleAggiunta) return;
        
        // Reset form
        formAggiunta.reset();
        // Default: disponibile
        if (toggleDisponibilitaAggiunta) toggleDisponibilitaAggiunta.checked = true;
        aggiornaLabelStatoAggiunta();
        
        modaleAggiunta.classList.add('attivo');
    };

    function chiudiModaleAggiunta() {
        if (modaleAggiunta) modaleAggiunta.classList.remove('attivo');
    }

    if (btnAnnullaAggiunta) {
        btnAnnullaAggiunta.addEventListener('click', chiudiModaleAggiunta);
    }

    if (modaleAggiunta) {
        modaleAggiunta.addEventListener('click', (e) => {
            if (e.target === modaleAggiunta) chiudiModaleAggiunta();
        });
    }

    if (formAggiunta) {
        formAggiunta.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const payload = {
                nome: nomeProdottoAggiunta.value,
                categoria_dashboard: categoriaDashboardAggiunta.value,
                categoria_menu: categoriaMenuAggiunta.value,
                prezzo: parseFloat(prezzoProdottoAggiunta.value),
                quantita: parseInt(quantitaProdottoAggiunta.value),
                disponibile: toggleDisponibilitaAggiunta.checked
            };

            try {
                const response = await fetch('/api/aggiungi_prodotto', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    // Ricarica gestita da socket
                } else {
                    const err = await response.json();
                    alert('Errore: ' + (err.errore || 'Impossibile aggiungere prodotto'));
                }
            } catch (error) {
                console.error('Errore:', error);
                alert('Errore di connessione.');
            }

            chiudiModaleAggiunta();
        });
    }

    // --- GESTIONE MODALE MODIFICA UTENTE ---
    const modaleModificaUtente = document.getElementById('modaleModificaUtente');
    const formModificaUtente = document.getElementById('formModificaUtente');
    const btnAnnullaModificaUtente = document.getElementById('btnAnnullaModificaUtente');
    
    // Inputs
    const idUtenteModifica = document.getElementById('idUtenteModifica');
    const usernameModifica = document.getElementById('usernameModifica');
    const passwordModifica = document.getElementById('passwordModifica');
    const isAdminModifica = document.getElementById('isAdminModifica');
    const isAttivoModifica = document.getElementById('isAttivoModifica');

    window.apriModaleModificaUtente = function(btn) {
        const id = btn.getAttribute('data-id');
        const username = btn.getAttribute('data-username');
        const isAdmin = btn.getAttribute('data-is-admin') === '1';
        const isAttivo = btn.getAttribute('data-attivo') === '1';
        const permessiStr = btn.getAttribute('data-permessi') || '';
        const permessi = permessiStr.split(',');

        if (idUtenteModifica) idUtenteModifica.value = id;
        if (usernameModifica) usernameModifica.value = username;
        if (passwordModifica) passwordModifica.value = ''; // Reset password
        
        if (isAdminModifica) {
            isAdminModifica.checked = isAdmin;
            // Trigger change event to update label style
            isAdminModifica.dispatchEvent(new Event('change'));
        }
        
        if (isAttivoModifica) {
            isAttivoModifica.checked = isAttivo;
            // Trigger change event
            isAttivoModifica.dispatchEvent(new Event('change'));
        }

        // Reset and set permissions
        document.querySelectorAll('input[name="permessi"]').forEach(cb => {
            cb.checked = permessi.includes(cb.value);
        });

        if (modaleModificaUtente) modaleModificaUtente.classList.add('attivo');
    };

    window.chiudiModaleModificaUtente = function() {
        if (modaleModificaUtente) modaleModificaUtente.classList.remove('attivo');
    };

    if (btnAnnullaModificaUtente) {
        btnAnnullaModificaUtente.addEventListener('click', chiudiModaleModificaUtente);
    }

    if (modaleModificaUtente) {
        modaleModificaUtente.addEventListener('click', (e) => {
            if (e.target === modaleModificaUtente) chiudiModaleModificaUtente();
        });
    }

    if (formModificaUtente) {
        formModificaUtente.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const permessiSelezionati = Array.from(document.querySelectorAll('input[name="permessi"]:checked')).map(cb => cb.value);

            const data = {
                id_utente: idUtenteModifica.value,
                username: usernameModifica.value,
                password: passwordModifica.value, // Can be empty
                is_admin: isAdminModifica.checked,
                attivo: isAttivoModifica.checked,
                permessi: permessiSelezionati
            };

            try {
                const response = await fetch('/api/modifica_utente', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (response.ok) {
                    // Reload page to show changes
                    window.location.reload(); 
                } else {
                    const err = await response.json();
                    alert('Errore: ' + (err.errore || 'Impossibile modificare utente'));
                }
            } catch (error) {
                console.error('Errore:', error);
                alert('Errore di connessione.');
            }
            
            chiudiModaleModificaUtente();
        });
    }

    // --- GESTIONE MODALE AGGIUNTA UTENTE ---
    const modaleAggiuntaUtente = document.getElementById('modaleAggiuntaUtente');
    const formAggiuntaUtente = document.getElementById('formAggiuntaUtente');
    const btnAnnullaAggiuntaUtente = document.getElementById('btnAnnullaAggiuntaUtente');

    // Inputs
    const usernameAggiunta = document.getElementById('usernameAggiunta');
    const passwordAggiunta = document.getElementById('passwordAggiunta');
    const isAdminAggiunta = document.getElementById('isAdminAggiunta');
    const isAttivoAggiunta = document.getElementById('isAttivoAggiunta');

    window.apriModaleAggiuntaUtente = function() {
        if (!modaleAggiuntaUtente) return;
        
        // Reset form
        formAggiuntaUtente.reset();
        
        // Default: Utente Standard, Attivo
        if (isAdminAggiunta) {
            isAdminAggiunta.checked = false;
            isAdminAggiunta.dispatchEvent(new Event('change'));
        }
        if (isAttivoAggiunta) {
            isAttivoAggiunta.checked = true;
            isAttivoAggiunta.dispatchEvent(new Event('change'));
        }

        modaleAggiuntaUtente.classList.add('attivo');
    };

    window.chiudiModaleAggiuntaUtente = function() {
        if (modaleAggiuntaUtente) modaleAggiuntaUtente.classList.remove('attivo');
    };

    if (btnAnnullaAggiuntaUtente) {
        btnAnnullaAggiuntaUtente.addEventListener('click', chiudiModaleAggiuntaUtente);
    }

    if (modaleAggiuntaUtente) {
        modaleAggiuntaUtente.addEventListener('click', (e) => {
            if (e.target === modaleAggiuntaUtente) chiudiModaleAggiuntaUtente();
        });
    }

    if (formAggiuntaUtente) {
        formAggiuntaUtente.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            // Collect checked permissions inside the add modal
            const permessiSelezionati = Array.from(formAggiuntaUtente.querySelectorAll('input[name="permessi"]:checked')).map(cb => cb.value);

            const data = {
                username: usernameAggiunta.value,
                password: passwordAggiunta.value,
                is_admin: isAdminAggiunta.checked,
                attivo: isAttivoAggiunta.checked,
                permessi: permessiSelezionati
            };

            try {
                const response = await fetch('/api/aggiungi_utente', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (response.ok) {
                    window.location.reload();
                } else {
                    const err = await response.json();
                    alert('Errore: ' + (err.errore || 'Impossibile aggiungere utente'));
                }
            } catch (error) {
                console.error('Errore:', error);
                alert('Errore di connessione.');
            }

            chiudiModaleAggiuntaUtente();
        });
    }

    // --- GESTIONE MODALE ELIMINAZIONE UTENTE ---
    const modaleEliminaUtente = document.getElementById('modaleEliminaUtente');
    const usernameElimina = document.getElementById('usernameElimina');
    const idUtenteElimina = document.getElementById('idUtenteElimina');
    const btnAnnullaEliminaUtente = document.getElementById('btnAnnullaEliminaUtente');
    const btnConfermaEliminaUtente = document.getElementById('btnConfermaEliminaUtente');

    window.apriModaleEliminaUtente = function(btn) {
        const id = btn.getAttribute('data-id');
        const username = btn.getAttribute('data-username');
        
        if (idUtenteElimina) idUtenteElimina.value = id;
        if (usernameElimina) usernameElimina.textContent = username;
        
        if (modaleEliminaUtente) modaleEliminaUtente.classList.add('attivo');
    };

    window.chiudiModaleEliminaUtente = function() {
        if (modaleEliminaUtente) modaleEliminaUtente.classList.remove('attivo');
    };

    if (btnAnnullaEliminaUtente) {
        btnAnnullaEliminaUtente.addEventListener('click', chiudiModaleEliminaUtente);
    }
    
    if (modaleEliminaUtente) {
        modaleEliminaUtente.addEventListener('click', (e) => {
            if (e.target === modaleEliminaUtente) chiudiModaleEliminaUtente();
        });
    }

    if (btnConfermaEliminaUtente) {
        btnConfermaEliminaUtente.addEventListener('click', async () => {
            const id = idUtenteElimina ? idUtenteElimina.value : null;
            if (!id) return;

            try {
                const response = await fetch('/api/elimina_utente', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id_utente: id })
                });

                if (response.ok) {
                    window.location.reload();
                } else {
                    const err = await response.json();
                    alert('Errore: ' + (err.errore || 'Impossibile eliminare utente'));
                }
            } catch (error) {
                console.error('Errore:', error);
                alert('Errore di connessione.');
            }
            chiudiModaleEliminaUtente();
        });
    }
});
