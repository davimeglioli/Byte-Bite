document.addEventListener("DOMContentLoaded", () => {
    // ==================== Categorie (linguette) ====================
    const linguetteCategorie = document.querySelectorAll(".linguetta");
    const sezioniProdotti = document.querySelectorAll(".prodotti");

    function mostraCategoria(nomeCategoria) {
        sezioniProdotti.forEach((sezione) => sezione.classList.remove("attivi"));
        const sezioneDaMostrare = document.querySelector(`.prodotti[data-categoria="${nomeCategoria}"]`);
        if (sezioneDaMostrare) sezioneDaMostrare.classList.add("attivi");
        linguetteCategorie.forEach((linguetta) => {
            linguetta.classList.toggle("attiva", linguetta.dataset.categoria === nomeCategoria);
        });
    }

    if (linguetteCategorie.length > 0) mostraCategoria(linguetteCategorie[0].dataset.categoria);
    linguetteCategorie.forEach((linguetta) => {
        linguetta.addEventListener("click", () => mostraCategoria(linguetta.dataset.categoria));
    });

    // ==================== Carrello e riepilogo ====================
    const carrello = [];
    const contenitoreRiepilogo = document.querySelector(".contenitore-lista-ordine");
    const totaleElemento = document.querySelector(".totale-carrello h2:last-child");
    const campoProdotti = document.getElementById("prodotti-json");

    function aggiornaRiepilogo() {
        contenitoreRiepilogo.innerHTML = "";
        let totale = 0;

        carrello.forEach((prodotto) => {
            const subtotale = prodotto.prezzo * prodotto.quantita;
            totale += subtotale;

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

        totaleElemento.textContent = `€${totale.toFixed(2)}`;
        campoProdotti.value = JSON.stringify(carrello);
        aggiornaQuantitaProdotti();
    }

    function aggiungiProdotto(id, nome, prezzo, maxDisponibile) {
        const esistente = carrello.find((p) => p.id === id);
        if (esistente) {
            if (esistente.quantita < maxDisponibile) esistente.quantita++;
        } else {
            carrello.push({ id, nome, prezzo, quantita: 1 });
        }
        aggiornaRiepilogo();
    }

    function rimuoviProdotto(id) {
        const indice = carrello.findIndex((p) => p.id === id);
        if (indice !== -1) {
            carrello[indice].quantita--;
            if (carrello[indice].quantita <= 0) carrello.splice(indice, 1);
        }
        aggiornaRiepilogo();
    }

    document.addEventListener("click", (evento) => {
        if (evento.target.classList.contains("tasto-piu")) {
            const prodottoDiv = evento.target.closest(".prodotto");
            aggiungiProdotto(
                parseInt(prodottoDiv.dataset.id),
                prodottoDiv.querySelector("h4").textContent,
                parseFloat(prodottoDiv.dataset.prezzo),
                parseInt(prodottoDiv.dataset.quantita),
            );
        }

        if (evento.target.classList.contains("tasto-meno")) {
            rimuoviProdotto(parseInt(evento.target.closest(".prodotto").dataset.id));
        }

        if (evento.target.classList.contains("tasto-aumenta")) {
            const id = parseInt(evento.target.dataset.id);
            const prodottoCarrello = carrello.find((p) => p.id === id);
            const prodottoDiv = document.querySelector(`.prodotto[data-id="${id}"]`);
            const maxDisponibile = prodottoDiv ? parseInt(prodottoDiv.dataset.quantita) : Infinity;
            if (prodottoCarrello && prodottoCarrello.quantita < maxDisponibile) {
                prodottoCarrello.quantita++;
                aggiornaRiepilogo();
            }
        }

        if (evento.target.classList.contains("tasto-diminuisci")) {
            rimuoviProdotto(parseInt(evento.target.dataset.id));
        }

        if (evento.target.classList.contains("tasto-rimuovi")) {
            const indice = carrello.findIndex((p) => p.id === parseInt(evento.target.dataset.id));
            if (indice !== -1) carrello.splice(indice, 1);
            aggiornaRiepilogo();
        }
    });

    function aggiornaQuantitaProdotti() {
        document.querySelectorAll(".prodotto").forEach((prodottoDiv) => {
            const id = parseInt(prodottoDiv.dataset.id);
            const prodottoCarrello = carrello.find((p) => p.id === id);
            const testoQuantita = prodottoDiv.querySelector(".selettore-quantita p");
            const btnPiu = prodottoDiv.querySelector(".tasto-piu");
            const btnMeno = prodottoDiv.querySelector(".tasto-meno");
            const maxDisponibile = parseInt(prodottoDiv.dataset.quantita);

            if (prodottoCarrello) {
                testoQuantita.textContent = prodottoCarrello.quantita;
                prodottoDiv.classList.add("prodotto-selezionato");
                btnPiu.disabled = prodottoCarrello.quantita >= maxDisponibile;
                btnMeno.disabled = prodottoCarrello.quantita <= 0;

                const riepilogoPiu = document.querySelector(`.tasto-aumenta[data-id="${id}"]`);
                const riepilogoMeno = document.querySelector(`.tasto-diminuisci[data-id="${id}"]`);
                if (riepilogoPiu) riepilogoPiu.disabled = prodottoCarrello.quantita >= maxDisponibile;
                if (riepilogoMeno) riepilogoMeno.disabled = prodottoCarrello.quantita <= 1;
            } else {
                testoQuantita.textContent = 0;
                prodottoDiv.classList.remove("prodotto-selezionato");
                btnPiu.disabled = false;
                btnMeno.disabled = true;
            }

            [btnPiu, btnMeno].forEach((bottone) => {
                bottone.style.opacity = bottone.disabled ? "0.5" : "1";
                bottone.style.cursor = bottone.disabled ? "not-allowed" : "pointer";
            });
        });
    }

    aggiornaQuantitaProdotti();

    // ==================== Asporto / tavolo / persone ====================
    const checkboxAsporto = document.getElementById("checkbox-asporto");
    const wrapperTavolo = document.getElementById("contenitore-tavolo");
    const wrapperPersone = document.getElementById("contenitore-persone");
    const campoTavolo = document.getElementById("numero-tavolo");
    const campoPersone = document.getElementById("numero-persone");

    function aggiornaVisibilitaCampi() {
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

    checkboxAsporto.addEventListener("change", aggiornaVisibilitaCampi);
    aggiornaVisibilitaCampi();

    // ==================== Invio ordine via fetch ====================
    const formOrdine = document.querySelector(".riepilogo-carrello form");
    const modaleConfermaOrdine = document.getElementById("modaleConfermaOrdine");
    const btnChiudiConfermaOrdine = document.getElementById("btnChiudiConfermaOrdine");

    if (formOrdine) {
        formOrdine.addEventListener("submit", async (e) => {
            e.preventDefault();

            if (carrello.length === 0) {
                alert("Impossibile inviare l'ordine: nessun prodotto selezionato.");
                return;
            }

            const asporto = checkboxAsporto.checked;
            const dati = {
                asporto: asporto,
                nome_cliente: document.getElementById("nome-cliente").value,
                numero_tavolo: asporto ? null : (parseInt(document.getElementById("numero-tavolo").value) || null),
                numero_persone: asporto ? null : (parseInt(document.getElementById("numero-persone").value) || null),
                metodo_pagamento: document.getElementById("metodo-pagamento").value,
                prodotti: carrello.map((p) => ({ id: p.id, nome: p.nome, quantita: p.quantita })),
            };

            try {
                const risposta = await fetch("/api/ordini", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(dati),
                });

                if (risposta.status === 201) {
                    carrello.length = 0;
                    formOrdine.reset();
                    aggiornaRiepilogo();
                    aggiornaVisibilitaCampi();
                    if (modaleConfermaOrdine) modaleConfermaOrdine.classList.add("attivo");
                } else {
                    const errore = await risposta.json();
                    alert("Errore: " + (errore.errore || "Impossibile inviare l'ordine."));
                }
            } catch (_) {
                alert("Errore di connessione.");
            }
        });
    }

    // ==================== Modale conferma ordine ====================
    if (btnChiudiConfermaOrdine && modaleConfermaOrdine) {
        btnChiudiConfermaOrdine.addEventListener("click", () => {
            modaleConfermaOrdine.classList.remove("attivo");
        });
        modaleConfermaOrdine.addEventListener("click", (e) => {
            if (e.target === modaleConfermaOrdine) modaleConfermaOrdine.classList.remove("attivo");
        });
    }
});
