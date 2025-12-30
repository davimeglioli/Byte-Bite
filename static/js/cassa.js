// ==================== Cassa ====================
// Gestisce: categorie, carrello, validazione ordine e modale conferma.

document.addEventListener("DOMContentLoaded", () => {
    // ==================== Categorie (linguette) ====================
    const linguetteCategorie = document.querySelectorAll(".linguetta");
    const sezioniProdotti = document.querySelectorAll(".prodotti");

    function mostraCategoria(nomeCategoria) {
        // Nasconde tutte le sezioni e mostra solo quella selezionata.
        sezioniProdotti.forEach((sezione) => sezione.classList.remove("attivi"));

        const sezioneDaMostrare = document.querySelector(`.prodotti[data-categoria="${nomeCategoria}"]`);
        if (sezioneDaMostrare) sezioneDaMostrare.classList.add("attivi");

        // Aggiorna lo stato grafico delle linguette.
        linguetteCategorie.forEach((linguetta) => {
            linguetta.classList.toggle("attiva", linguetta.dataset.categoria === nomeCategoria);
        });
    }

    // Prima categoria attiva di default.
    if (linguetteCategorie.length > 0) mostraCategoria(linguetteCategorie[0].dataset.categoria);

    // Cambio categoria al click.
    linguetteCategorie.forEach((linguetta) => {
        linguetta.addEventListener("click", () => mostraCategoria(linguetta.dataset.categoria));
    });

    // ==================== Carrello e riepilogo ====================
    const carrello = [];
    const contenitoreRiepilogo = document.querySelector(".contenitore-lista-ordine");
    const totaleElemento = document.querySelector(".totale-carrello h2:last-child");
    const campoProdotti = document.getElementById("prodotti-json");

    function aggiornaRiepilogo() {
        // Rigenera completamente la lista riepilogo e ricalcola il totale.
        contenitoreRiepilogo.innerHTML = "";
        let totale = 0;

        carrello.forEach((prodotto) => {
            // Somma e mostra subtotale prodotto.
            const subtotale = prodotto.prezzo * prodotto.quantita;
            totale += subtotale;

            // Crea riga prodotto nel riepilogo.
            const riga = document.createElement("div");
            riga.classList.add("articolo-carrello");
            riga.innerHTML = `
                <h5>${prodotto.nome}</h5>
                <div class="controlli-articolo">
                    <button class="tasto-diminuisci" data-id="${prodotto.id}">-</button>
                    <p>${prodotto.quantita}</p>
                    <button class="tasto-aumenta" data-id="${prodotto.id}">+</button>
                    <button class="tasto-rimuovi" data-id="${prodotto.id}">×</button>
                    <p>€${subtotale.toFixed(2)}</p>
                </div>
            `;
            contenitoreRiepilogo.appendChild(riga);
        });

        // Aggiorna totale e campo hidden per l'invio al backend.
        totaleElemento.textContent = `€${totale.toFixed(2)}`;
        campoProdotti.value = JSON.stringify(carrello);

        // Sincronizza i contatori e lo stato dei pulsanti nelle card.
        aggiornaQuantitaProdotti();
    }

    function aggiungiProdotto(id, nome, prezzo, maxDisponibile) {
        // Aumenta quantità se già presente, altrimenti inserisce una nuova riga nel carrello.
        const esistente = carrello.find((p) => p.id === id);

        if (esistente) {
            if (esistente.quantita < maxDisponibile) esistente.quantita++;
        } else {
            carrello.push({ id, nome, prezzo, quantita: 1 });
        }

        aggiornaRiepilogo();
    }

    function rimuoviProdotto(id) {
        // Riduce la quantità; se arriva a 0 rimuove la riga dal carrello.
        const indice = carrello.findIndex((p) => p.id === id);
        if (indice !== -1) {
            carrello[indice].quantita--;
            if (carrello[indice].quantita <= 0) carrello.splice(indice, 1);
        }

        aggiornaRiepilogo();
    }

    // Event delegation: gestisce click su card prodotto e riepilogo.
    document.addEventListener("click", (evento) => {
        // ==================== Pulsanti nelle card prodotto ====================
        if (evento.target.classList.contains("tasto-piu")) {
            const prodottoDiv = evento.target.closest(".prodotto");
            const id = parseInt(prodottoDiv.dataset.id);
            const nome = prodottoDiv.querySelector("h4").textContent;
            const prezzo = parseFloat(prodottoDiv.dataset.prezzo);
            const maxDisponibile = parseInt(prodottoDiv.dataset.quantita);

            aggiungiProdotto(id, nome, prezzo, maxDisponibile);
        }

        if (evento.target.classList.contains("tasto-meno")) {
            const prodottoDiv = evento.target.closest(".prodotto");
            const id = parseInt(prodottoDiv.dataset.id);
            rimuoviProdotto(id);
        }

        // ==================== Pulsanti nel riepilogo ====================
        if (evento.target.classList.contains("tasto-aumenta")) {
            const id = parseInt(evento.target.dataset.id);
            const prodottoCarrello = carrello.find((p) => p.id === id);

            // Limite massimo ricavato dalla card prodotto (se presente).
            const prodottoDiv = document.querySelector(`.prodotto[data-id="${id}"]`);
            const maxDisponibile = prodottoDiv ? parseInt(prodottoDiv.dataset.quantita) : Infinity;

            if (prodottoCarrello && prodottoCarrello.quantita < maxDisponibile) {
                prodottoCarrello.quantita++;
                aggiornaRiepilogo();
            }
        }

        if (evento.target.classList.contains("tasto-diminuisci")) {
            const id = parseInt(evento.target.dataset.id);
            rimuoviProdotto(id);
        }

        if (evento.target.classList.contains("tasto-rimuovi")) {
            const id = parseInt(evento.target.dataset.id);
            const indice = carrello.findIndex((p) => p.id === id);

            if (indice !== -1) carrello.splice(indice, 1);
            aggiornaRiepilogo();
        }
    });

    function aggiornaQuantitaProdotti() {
        // Sincronizza quantità e abilitazione pulsanti per ogni card prodotto.
        document.querySelectorAll(".prodotto").forEach((prodottoDiv) => {
            const id = parseInt(prodottoDiv.dataset.id);
            const prodottoCarrello = carrello.find((p) => p.id === id);

            const testoQuantita = prodottoDiv.querySelector(".selettore-quantita p");
            const btnPiu = prodottoDiv.querySelector(".tasto-piu");
            const btnMeno = prodottoDiv.querySelector(".tasto-meno");
            const maxDisponibile = parseInt(prodottoDiv.dataset.quantita);

            if (prodottoCarrello) {
                // Prodotto presente: mostra quantità e aggiorna stile selezionato.
                testoQuantita.textContent = prodottoCarrello.quantita;
                prodottoDiv.classList.add("prodotto-selezionato");

                // Disabilita + quando si raggiunge il massimo.
                btnPiu.disabled = prodottoCarrello.quantita >= maxDisponibile;
                btnMeno.disabled = prodottoCarrello.quantita <= 0;

                // Disabilita anche i pulsanti nel riepilogo (se esistono).
                const riepilogoPiu = document.querySelector(`.tasto-aumenta[data-id="${id}"]`);
                const riepilogoMeno = document.querySelector(`.tasto-diminuisci[data-id="${id}"]`);

                if (riepilogoPiu) riepilogoPiu.disabled = prodottoCarrello.quantita >= maxDisponibile;
                if (riepilogoMeno) riepilogoMeno.disabled = prodottoCarrello.quantita <= 1;
            } else {
                // Prodotto assente: reset UI della card.
                testoQuantita.textContent = 0;
                prodottoDiv.classList.remove("prodotto-selezionato");

                btnPiu.disabled = false;
                btnMeno.disabled = true;
            }

            // Feedback visivo pulsanti disabilitati.
            [btnPiu, btnMeno].forEach((bottone) => {
                bottone.style.opacity = bottone.disabled ? "0.5" : "1";
                bottone.style.cursor = bottone.disabled ? "not-allowed" : "pointer";
            });
        });
    }

    // Inizializzazione UI carrello.
    aggiornaQuantitaProdotti();

    // ==================== Asporto / tavolo / persone ====================
    const checkboxAsporto = document.getElementById("checkbox-asporto");
    const wrapperTavolo = document.getElementById("contenitore-tavolo");
    const wrapperPersone = document.getElementById("contenitore-persone");
    const campoTavolo = document.getElementById("numero-tavolo");
    const campoPersone = document.getElementById("numero-persone");

    function aggiornaVisibilitaCampi() {
        // Se asporto è selezionato, nasconde i campi tavolo/persone e rimuove required.
        const asporto = checkboxAsporto.checked;
        wrapperTavolo.style.display = asporto ? "none" : "block";
        wrapperPersone.style.display = asporto ? "none" : "block";

        if (asporto) {
            campoTavolo.removeAttribute("required");
            campoPersone.removeAttribute("required");
            campoTavolo.value = "";
            campoPersone.value = "";
        } else {
            campoTavolo.setAttribute("required", "required");
            campoPersone.setAttribute("required", "required");
        }
    }

    // Aggiorna UI al cambio checkbox e al caricamento.
    checkboxAsporto.addEventListener("change", aggiornaVisibilitaCampi);
    aggiornaVisibilitaCampi();

    // ==================== Validazione invio ordine ====================
    const formOrdine = document.querySelector(".riepilogo-carrello form");
    if (formOrdine) {
        // Impedisce invio se il carrello è vuoto.
        formOrdine.addEventListener("submit", (e) => {
            if (carrello.length === 0) {
                e.preventDefault();
                alert("Impossibile inviare l'ordine: nessun prodotto selezionato.");
            }
        });
    }

    // ==================== Modale conferma ordine ====================
    const modaleConfermaOrdine = document.getElementById("modaleConfermaOrdine");
    const numeroOrdineConfermato = document.getElementById("numeroOrdineConfermato");
    const btnChiudiConfermaOrdine = document.getElementById("btnChiudiConfermaOrdine");

    // L'id ultimo ordine viene passato dal backend come attributo sul body.
    const lastOrderId = document.body.getAttribute("data-last-order-id");

    if (lastOrderId && modaleConfermaOrdine && numeroOrdineConfermato) {
        numeroOrdineConfermato.textContent = lastOrderId;
        modaleConfermaOrdine.classList.add("attivo");
    }

    if (btnChiudiConfermaOrdine && modaleConfermaOrdine) {
        // Chiude con click sul bottone.
        btnChiudiConfermaOrdine.addEventListener("click", () => {
            modaleConfermaOrdine.classList.remove("attivo");
        });

        // Chiude cliccando fuori dalla finestra.
        modaleConfermaOrdine.addEventListener("click", (e) => {
            if (e.target === modaleConfermaOrdine) {
                modaleConfermaOrdine.classList.remove("attivo");
            }
        });
    }
});

// ==================== Touch (legacy) ====================
// Codice lasciato per compatibilità con comportamenti touch precedenti.
let lastTouchEnd = 0;
document.removeEventListener("touchend", function () {});
document.removeEventListener("touchmove", function () {});
