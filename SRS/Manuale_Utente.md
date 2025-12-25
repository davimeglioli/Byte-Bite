# Manuale Utente - Byte-Bite

Benvenuti in **Byte-Bite**, il sistema digitale per la gestione degli ordini della nostra sagra.
Questo manuale vi guiderà nell'utilizzo delle funzionalità principali del sistema, divise per ruolo.

---

## 1. Accesso al Sistema

Per iniziare a lavorare, aprite il browser (Chrome, Safari, o Firefox) e navigate all'indirizzo del server.

1.  Vi troverete di fronte alla schermata di **Login**.
2.  Inserite il vostro **Username** e la **Password** forniti dall'amministratore.
3.  Premete "Accedi".

> **Nota:** Se sbagliate password o il vostro account è disattivato, vedrete un messaggio di errore rosso. Contattate l'amministratore se il problema persiste.



## 2. Area Cassa (Per i Cassieri)

L'area Cassa è progettata per essere veloce e ridurre gli errori. Qui prenderete le ordinazioni dei clienti.

### 2.1 Panoramica Interfaccia
*   **Colonna Sinistra (Menu):** Qui trovate tutti i prodotti divisi per categoria (es. *Primi*, *Secondi*, *Bevande*). Cliccate sulle linguette in alto per cambiare categoria.
*   **Colonna Destra (Riepilogo):** Qui vedete il carrello con i prodotti selezionati, il totale e i dati del cliente.

### 2.2 Creare un Nuovo Ordine
1.  **Dati Cliente:**
    *   **Asporto:** Se il cliente porta via il cibo, spuntate la casella "Ordine da Asporto". I campi "Tavolo" e "Persone" spariranno.
    *   **Tavolo:** Se il cliente mangia qui, inserite il **Nome Cliente**, il **Numero Tavolo** e il **Numero Persone**.
2.  **Aggiungere Prodotti:**
    *   Toccate il pulsante **+** sulla scheda del prodotto per aggiungerlo al carrello.
    *   **Feedback Visivo:** Quando un prodotto è nel carrello, la sua scheda apparirà con un **bordo rosa** per indicare che è selezionato.
    *   Se un prodotto è esaurito o non disponibile, **non apparirà** nella lista (il sistema lo nasconde automaticamente).
3.  **Modificare le Quantità:**
    *   Nel riepilogo a destra, usate i tasti **+** e **-** per cambiare la quantità.
    *   Usate la **X** per rimuovere completamente un prodotto.
4.  **Pagamento:**
    *   Chiedete al cliente come vuole pagare.
    *   Selezionate **Contanti** o **Carta** dal menu a tendina.
5.  **Inviare l'Ordine:**
    *   Controllate il totale.
    *   Premete il pulsante verde **Invia Ordine**.

> **Importante:** Una volta inviato, l'ordine viene stampato nelle cucine competenti. Non è possibile modificarlo dalla cassa dopo l'invio (serve l'intervento dell'amministratore o della cucina).

---

## 3. Area Cucina e Bar (Dashboard)

Ogni postazione (Cucina, Griglia, Bar, Gnoccheria) ha la sua **Dashboard** che mostra solo gli ordini di competenza.

### 3.1 Come leggere la Dashboard
Gli ordini appaiono come "cartellini" (card).
*   **Nuovi Ordini:** Appaiono in alto nella sezione bianca.
*   **Ordini Completati:** Scendono in basso nella sezione grigia "Ordini Completati".

Ogni cartellino mostra:
*   Nome Cliente, Numero Persone e Tavolo.
*   Ora dell'ordine.
*   Elenco dei prodotti da preparare (con le quantità, es. `x2`).

### 3.2 Gestire gli Stati (Il Flusso di Lavoro)
Ogni ordine ha un pulsante colorato in basso. Dovete premerlo per segnalare a che punto siete:

1.  **IN ATTESA (Grigio):** L'ordine è appena arrivato. Nessuno lo sta ancora preparando.
2.  **IN PREPARAZIONE (Giallo):** Premete questo tasto quando iniziate a cucinare/versare. Segnala agli altri che ve ne state occupando.
3.  **PRONTO (Verde):** Premete quando il piatto è sul pass o il drink è sul bancone.
    *   *Attenzione:* Quando mettete "Pronto", parte un **timer automatico**. Se non fate nulla, dopo un po' l'ordine passerà da solo a "Completato".
4.  **COMPLETATO (Blu):** L'ordine è stato ritirato o portato al tavolo. Sparisce dalla lista attiva e va nello storico.

> **Annullare un Timer:** Se avete messo "Pronto" per sbaglio, o il cameriere tarda, potete premere di nuovo il pulsante per tornare a "In Preparazione" o fermare il timer.

---

## 4. Area Amministrazione (Per i Gestori)

Accessibile solo agli utenti autorizzati tramite il link "Amministrazione" in alto a destra o nella home. La pagina è organizzata a scorrimento verticale, con le seguenti sezioni in ordine:

### 4.1 Riepilogo (In alto)
Qui trovate i "cartellini" con i numeri chiave della serata:
*   **Ordixni Totali e Completati.**
*   **Guadagno Totale** (con dettaglio Contanti vs Carta).

### 4.2 Grafici
Subito sotto, trovate 4 grafici visivi per capire l'andamento:
*   **Ordini per categoria** (Bar vs Cucina, ecc.).
*   **Andamento orario** (Picchi di affluenza).
*   **Stato ordini** (Quanti in attesa vs pronti).
*   **Prodotti più venduti** (La Top 10).

### 4.3 Dettaglio Ordini
Una tabella completa con lo storico di tutti gli ordini della serata.
*   Potete vedere chi ha ordinato, cosa e quando.
*   Utile per controlli su tavoli o asporto.

### 4.4 Dettaglio Prodotti (Gestione Menu)
Qui controllate il menu e il magazzino.
*   **Aggiungere:** Premete il tasto **+** nell'intestazione della sezione per creare un nuovo piatto.
*   **Navigazione:** Usate le linguette per filtrare le categorie (Bar, Cucina, ecc.).
*   **Rifornimento:** Cliccate sul tasto **+** nella riga del prodotto per aggiungere scorte rapidamente.
*   **Modifiche:** Cliccate sulla matita (**✎**) per cambiare prezzo, nome o categoria.
*   **Disponibilità:** Togliete la spunta "Disponibile" nella modifica se un ingrediente è finito. Il prodotto sparirà dalle casse immediatamente.

### 4.5 Dettaglio Utenti
In fondo alla pagina, la gestione dello staff.
*   **Aggiungere:** Premete il tasto **+** nell'intestazione per creare un nuovo account.
*   **Permessi:** Assegnate con attenzione i ruoli (es. non date il permesso `AMMINISTRAZIONE` a chi deve fare solo scontrini).

---

## 5. Risoluzione Problemi

*   **"La Dashboard non si aggiorna!"**
    *   Controllate se siete connessi al Wi-Fi del locale.
    *   Provate a ricaricare la pagina (F5 o trascina giù su tablet). Se il problema persiste, chiamate il tecnico.
*   **"Ho sbagliato a fare uno scontrino!"**
    *   La cassa non può cancellare ordini inviati. Segnalatelo subito alla cucina a voce per non far preparare cibo inutile, poi ditelo al responsabile per stornare l'incasso.
