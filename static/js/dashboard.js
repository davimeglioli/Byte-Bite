function escapaHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

function costruisciSchedeOrdini(ordini, completati) {
    return ordini.map((o) => {
        const tavolo = o.numero_tavolo !== null ? o.numero_tavolo : "ASPORTO";
        const persone = o.numero_persone !== null ? o.numero_persone : "ASPORTO";
        const classeDivisore = completati ? "divisore-ordine-completato" : "divisore-ordine";
        const prodotti = o.prodotti.map((p) => `
          <div class="riga-articolo-ordine">
            <span>${escapaHtml(p.nome)}</span>
            <span class="etichetta-quantita">x${p.quantita}</span>
          </div>`).join("");
        const bottone = completati ? "" : `
          <div class="stato-ordine">
            <button
              class="tasto-azione-ordine"
              data-status="${escapaHtml(o.stato)}"
              data-id="${o.id}"
              data-categoria="${escapaHtml(categoriaCorrente)}"
              onclick="cambiaStato(this)"
            >${escapaHtml(o.stato)}</button>
          </div>`;
        return `
          <div class="scheda-ordine ${completati ? "completato" : ""}" data-status="${escapaHtml(o.stato)}" data-id="${o.id}">
            <h2 class="titolo-ordine">${escapaHtml(o.nome_cliente)}</h2>
            <div class="info-ordine">
              <div>Tavolo: ${tavolo}</div>
              <div>${o.data_ordine}</div>
              <div>Persone: ${persone}</div>
            </div>
            <div class="${classeDivisore}"></div>
            <div class="lista-articoli-ordine">${prodotti}</div>
            ${bottone}
          </div>`;
    }).join("");
}

(function () {
    const el = document.getElementById('orologio-live');
    function aggiorna() {
        el.textContent = new Date().toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
    }
    aggiorna();
    setInterval(aggiorna, 1000);
})();

const socket = io({ transports: ["websocket"], upgrade: false });

const categoriaCorrente = document
    .querySelector("h2")
    .textContent
    .replace("Dashboard ", "")
    .trim();

socket.emit("join", { categoria: categoriaCorrente });

socket.on("aggiorna_dashboard", (dati) => {
    if (dati.categoria === categoriaCorrente) {
        aggiornaDashboard();
    }
});

function cambiaStato(bottone) {
    const ordine_id = bottone.dataset.id;
    const categoria = bottone.dataset.categoria;
    const statoAttuale = bottone.dataset.status;

    const stati = ["In Attesa", "In Preparazione", "Pronto", "Completato"];
    const indiceStato = stati.indexOf(statoAttuale);

    let statoSuccessivo = statoAttuale;
    // "Pronto" steps back to "In Preparazione" (cancels the auto-complete timer on the backend).
    if (statoAttuale === "Pronto") {
        statoSuccessivo = "In Preparazione";
    } else if (indiceStato !== -1 && indiceStato < stati.length - 1) {
        statoSuccessivo = stati[indiceStato + 1];
    }

    const testoOriginale = bottone.textContent;
    const statoOriginale = bottone.dataset.status;

    bottone.textContent = statoSuccessivo;
    bottone.dataset.status = statoSuccessivo;

    const schedaOrdine = bottone.closest(".scheda-ordine");
    if (schedaOrdine) {
        schedaOrdine.dataset.status = statoSuccessivo;
        if (statoSuccessivo === "Completato") {
            schedaOrdine.style.opacity = "0.5";
            schedaOrdine.style.pointerEvents = "none";
        }
    }

    fetch(`/api/ordini/${ordine_id}/stato/${encodeURIComponent(categoria)}`, { method: "PATCH" })
        .then((res) => res.json())
        .then((datiRisposta) => {
            if (datiRisposta.nuovo_stato && datiRisposta.nuovo_stato !== statoSuccessivo) {
                bottone.textContent = datiRisposta.nuovo_stato;
                bottone.dataset.status = datiRisposta.nuovo_stato;
                if (schedaOrdine) {
                    schedaOrdine.dataset.status = datiRisposta.nuovo_stato;
                    if (datiRisposta.nuovo_stato !== "Completato") {
                        schedaOrdine.style.opacity = "";
                        schedaOrdine.style.pointerEvents = "";
                    }
                }
            }
        })
        .catch((errore) => {
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
    fetch(`/api/ordini/categoria/${categoriaCorrente}`)
        .then((res) => res.json())
        .then((dati) => {
            const griglie = document.querySelectorAll(".griglia-ordini");
            if (griglie.length < 2) return;
            griglie[0].innerHTML = costruisciSchedeOrdini(dati.non_completati, false);
            griglie[1].innerHTML = costruisciSchedeOrdini(dati.completati, true);
        })
        .catch((errore) => console.error("Errore aggiornamento:", errore));
}
