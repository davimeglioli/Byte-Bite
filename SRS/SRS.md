# Specifica dei Requisiti Software (SRS) - Byte-Bite

**Data:** 25 Dicembre 2025  
**Versione:** 1.1  
**Stato:** Bozza Avanzata

---

## 1. Introduzione

### 1.1 Obiettivo
Il presente documento ha lo scopo di definire in maniera dettagliata e completa le specifiche dei requisiti software (SRS) per il sistema **Byte-Bite**. Esso descrive le funzionalità, le interfacce utente, il modello dati, le prestazioni e i vincoli del sistema. Il documento serve come riferimento primario per il team di sviluppo per l'implementazione e la manutenzione, e per il committente per la verifica della conformità del prodotto finale.

### 1.2 Campo d’applicazione
Il prodotto software è denominato **Byte-Bite**.
È un sistema gestionale integrato per la ristorazione (sagre, feste, piccoli ristoranti) progettato per ottimizzare il flusso operativo tramite la digitalizzazione delle comande.

Il sistema copre i seguenti ambiti:
*   **Front-end Cassa (POS):** Interfaccia per l'inserimento rapido degli ordini da parte degli operatori.
*   **Back-end Cucina (KDS):** Sistema di visualizzazione ordini (Kitchen Display System) suddiviso per reparti (Bar, Cucina, Griglia, Gnoccheria).
*   **Gestione Operativa:** Coordinamento in tempo reale tramite comunicazione WebSocket.
*   **Back-office Amministrativo:** Gestione anagrafiche prodotti, utenti, permessi e analisi statistiche.

I benefici attesi sono: eliminazione degli errori di trascrizione comande, riduzione dei tempi di attesa grazie all'invio istantaneo degli ordini ai reparti, e controllo preciso delle giacenze di magazzino.

### 1.3 Definizioni, acronimi e abbreviazioni
*   **SRS:** Software Requirements Specification.
*   **POS:** Point of Sale (Punto Vendita/Cassa).
*   **KDS:** Kitchen Display System (Schermo per la cucina).
*   **Socket.IO:** Libreria per la comunicazione bidirezionale real-time.
*   **Asporto:** Modalità di ordine in cui il cliente non consuma al tavolo.
*   **Routing:** Processo automatico di smistamento dei prodotti verso la dashboard di competenza (es. Birra -> Bar).
*   **Admin:** Utente con privilegi di amministratore.
*   **Slug:** Identificativo leggibile nell'URL (es. 'bar', 'cucina').

### 1.4 Fonti
*   IEEE Std 830-1998: IEEE Recommended Practice for Software Requirements Specification.
*   Codice sorgente del progetto (Python/Flask, JavaScript, SQL).

### 1.5 Struttura del documento
Il documento segue lo standard IEEE 830 rivisitato:
1.  **Introduzione**
2.  **Descrizione Generale** (Contesto, Utenti, Vincoli)
3.  **Specifica dei Requisiti** (Dettaglio funzionale, Interfacce, Dati)

---

## 2. Descrizione Generale

### 2.1 Inquadramento
Byte-Bite è un'applicazione web *standalone* che opera su una rete Intranet (LAN). Non richiede connessione internet esterna per le funzionalità core. Il server centrale ospita il database e l'applicazione Flask, mentre i client (Cassa e Dashboard) accedono tramite browser web standard.

### 2.2 Macro funzionalità del sistema
*   **Autenticazione Sicura:** Accesso tramite username/password con hashing, gestione sessioni e logout.
*   **Gestione Ordini (POS):**
    *   Selezione prodotti da catalogo visivo.
    *   Gestione carrello con modifica quantità.
    *   Differenziazione Tavolo/Asporto.
    *   Controllo disponibilità magazzino in tempo reale.
*   **Smistamento e Produzione (KDS):**
    *   Visualizzazione ordini in tempo reale su dashboard specifiche.
    *   Workflow a stati: *In Attesa* -> *In Preparazione* -> *Pronto* -> *Completato*.
    *   Gestione automatica "Timer" per il completamento ordini.
*   **Amministrazione:**
    *   CRUD (Create, Read, Update, Delete) Prodotti e Utenti.
    *   Gestione granulare dei permessi (ACL) per pagina.
    *   Visualizzazione storico ordini e incassi.

### 2.3 Caratteristiche degli utenti
*   **Cassieri (Operatori POS):**
    *   *Competenze:* Basse/Medie.
    *   *Esigenze:* Velocità, chiarezza, prevenzione errori (es. non ordinare più prodotti di quelli disponibili).
*   **Personale di Cucina/Bar (Operatori KDS):**
    *   *Competenze:* Basse (interazione limitata al touch).
    *   *Esigenze:* Leggibilità a distanza, notifiche visive immediate, interazione semplice (un tocco per cambiare stato).
*   **Amministratore (Gestore):**
    *   *Competenze:* Medie.
    *   *Esigenze:* Controllo totale sul sistema, accesso ai dati sensibili (incassi).

### 2.4 Vincoli generali
*   **Architettura:** Client-Server su protocollo HTTP/WebSocket.
*   **Database:** Relazionale (SQLite) per garantire integrità referenziale.
*   **Hardware Client:** Qualsiasi dispositivo dotato di browser moderno (Chrome, Safari, Firefox). Risoluzione minima raccomandata tablet (1024x768).

---

## 3. Specifica dei Requisiti

### 3.1 Requisiti Interfaccia Esterna

#### 3.1.1 Interfacce Utente
*   **Schermata di Login:**
    *   Campi: Username, Password.
    *   Feedback: Messaggi di errore per credenziali errate o account disattivo.
*   **Interfaccia Cassa (POS):**
    *   **Layout:** A due colonne. Sinistra: categorie prodotti (tab) e griglia prodotti. Destra: riepilogo carrello e form dati cliente.
    *   **Interazione:** Click su prodotto aggiunge al carrello. Pulsanti +/- nel carrello modificano quantità.
    *   **Dinamicità:** Checkbox "Asporto" nasconde i campi "Numero Tavolo" e "Numero Persone".
*   **Interfaccia Dashboard (KDS):**
    *   **Layout:** Griglia di "card" ordini.
    *   **Card Ordine:** Mostra ID, Tavolo/Cliente, Ora, Lista prodotti con quantità.
    *   **Azione:** Pulsante di stato prominente che cambia colore e testo al click.
*   **Interfaccia Amministrazione:**
    *   Tabelle dati per Prodotti, Utenti, Ordini.
    *   Modali o form in-line per la modifica dei dati.

#### 3.1.2 Interfacce di Comunicazione
*   **Protocollo HTTP:** Utilizzato per il caricamento risorse e le chiamate API REST (es. cambio stato, login).
*   **Protocollo WebSocket (Socket.IO):** Utilizzato per il push server-to-client.
    *   Evento `join`: Il client si registra a una "stanza" (es. 'Cucina').
    *   Evento `aggiorna_dashboard`: Il server notifica ai client di ricaricare i dati parziali.

### 3.2 Requisiti Funzionali

#### 3.2.1 Modulo Autenticazione (AUTH)
*   **AUTH-01:** Il sistema deve verificare le credenziali confrontando l'hash della password (Bcrypt).
*   **AUTH-02:** Il sistema deve verificare che l'utente sia "attivo" (campo `attivo=1`).
*   **AUTH-03:** Il sistema deve decorare le route critiche verificando la presenza di `id_utente` in sessione.
*   **AUTH-04:** Il sistema deve gestire un sistema di permessi basato su tabella `permessi_pagine` (es. permesso 'CASSA' richiesto per accedere a `/cassa/`).

#### 3.2.2 Modulo Cassa e Ordini (POS)
*   **POS-01 Inserimento Prodotti:** L'utente seleziona prodotti raggruppati per `categoria_menu`. Il sistema verifica lato client e server che `quantita_richiesta <= quantita_disponibile`.
*   **POS-02 Validazione Ordine:**
    *   Se "Asporto" è attivo: Tavolo e Persone sono opzionali (o nascosti).
    *   Se "Tavolo" è attivo: Tavolo e Persone sono obbligatori.
*   **POS-03 Salvataggio Ordine:**
    *   Creazione record in `ordini`.
    *   Creazione record multipli in `ordini_prodotti`.
    *   Decremento atomico del campo `quantita` in tabella `prodotti`.
    *   Incremento del campo `venduti`.
*   **POS-04 Notifica:** Al salvataggio, il sistema identifica le categorie dashboard coinvolte e invia un evento socket `aggiorna_dashboard` solo alle stanze interessate.

#### 3.2.3 Modulo Dashboard e Workflow (KDS)
*   **KDS-01 Visualizzazione:** Ogni dashboard mostra solo i prodotti di sua competenza (es. Dashboard Bar mostra solo prodotti con `categoria_dashboard = 'Bar'`).
*   **KDS-02 Avanzamento Stato:**
    *   Click su pulsante stato -> Chiamata API `/cambia_stato/`.
    *   Sequenza: *In Attesa* -> *In Preparazione* -> *Pronto* -> *Completato*.
*   **KDS-03 Gestione Timer "Pronto":**
    *   Quando un ordine passa a "Pronto", il server avvia un timer (background task).
    *   Se l'ordine non viene modificato entro X secondi/minuti, il sistema lo passa automaticamente a "Completato".
    *   Se l'operatore clicca prima del timer, il timer viene annullato.
*   **KDS-04 Sincronizzazione:** Ogni cambio di stato innesca un ricalcolo delle statistiche e un aggiornamento via socket di tutte le dashboard della stessa categoria.

#### 3.2.4 Modulo Amministrazione e Statistiche (ADMIN)
*   **ADM-01 Gestione Prodotti:** Possibilità di modificare `prezzo`, `disponibile`, `quantita` (stock) e `categoria_dashboard` per ogni prodotto.
*   **ADM-02 Statistiche Real-time:**
    *   Calcolo incasso totale (somma `prezzo * quantita`).
    *   Calcolo distribuzione ordini per ora (0-23).
    *   Calcolo item venduti per categoria.
    *   Le statistiche vengono ricalcolate a ogni chiusura ordine o cambio stato rilevante.

### 3.3 Requisiti Dati (Data Dictionary)

Il sistema si basa su un database SQLite relazionale (`db.sqlite3`).

#### 3.3.1 Tabella `ordini`
| Campo | Tipo | Descrizione |
|---|---|---|
| `id` | INTEGER PK | Identificativo univoco ordine. |
| `nome_cliente` | TEXT | Nome di riferimento per la chiamata. |
| `numero_tavolo` | INTEGER | Numero del tavolo (NULL se asporto). |
| `numero_persone` | INTEGER | Coperti (NULL se asporto). |
| `asporto` | BOOLEAN | 1 se asporto, 0 se tavolo. |
| `data_ordine` | DATETIME | Timestamp creazione (default CURRENT_TIMESTAMP). |
| `metodo_pagamento`| TEXT | 'Contanti' o 'Carta'. |
| `completato` | BOOLEAN | 1 se tutte le righe ordine sono completate. |

#### 3.3.2 Tabella `prodotti`
| Campo | Tipo | Descrizione |
|---|---|---|
| `id` | INTEGER PK | Identificativo prodotto. |
| `nome` | TEXT | Nome visualizzato nel menu. |
| `prezzo` | REAL | Prezzo unitario in Euro. |
| `categoria_menu` | TEXT | Categoria per la visualizzazione in Cassa (es. 'Primi'). |
| `categoria_dashboard`| TEXT | Destinazione KDS (es. 'Cucina', 'Bar'). |
| `quantita` | INTEGER | Giacenza di magazzino attuale. |
| `disponibile` | BOOLEAN | Flag per nascondere il prodotto se non disponibile. |

#### 3.3.3 Tabella `ordini_prodotti` (Associazione)
| Campo | Tipo | Descrizione |
|---|---|---|
| `ordine_id` | INTEGER FK | Riferimento all'ordine. |
| `prodotto_id` | INTEGER FK | Riferimento al prodotto. |
| `quantita` | INTEGER | Quantità ordinata per questo prodotto. |
| `stato` | TEXT | Stato corrente ('In Attesa', 'In Preparazione', 'Pronto', 'Completato'). |

----------- sono arivato qui --------------


#### 3.3.4 Tabella `utenti` e `permessi_pagine`
Gestiscono l'accesso. `utenti` contiene username e password hashata. `permessi_pagine` mappa `utente_id` a stringhe di permesso (es. 'AMMINISTRAZIONE', 'CASSA', 'DASHBOARD_BAR').

### 3.4 Requisiti Non Funzionali

#### 3.4.1 Prestazioni
*   **Latenza Aggiornamento:** Il tempo tra l'invio dell'ordine e l'apparizione sulla dashboard deve essere inferiore a 1 secondo in rete locale.
*   **Capacità:** Il sistema deve gestire fino a 500 ordini attivi simultaneamente senza rallentamenti percettibili nell'interfaccia.

#### 3.4.2 Sicurezza
*   **Protezione Dati:** Le password non devono mai essere memorizzate in chiaro.
*   **Sessioni:** I cookie di sessione devono essere firmati con una chiave segreta robusta (`app.secret_key`).
*   **Access Control:** Nessuna API operativa deve essere accessibile senza autenticazione.

#### 3.4.3 Affidabilità
*   **Robustezza Socket:** Il client deve tentare la riconnessione automatica al WebSocket in caso di perdita temporanea di rete.
*   **Transazionalità:** Le operazioni di inserimento ordine e aggiornamento magazzino devono avvenire in un'unica transazione atomica DB.

#### 3.4.4 Manutenibilità
*   **Codice:** Il codice backend deve seguire lo standard PEP 8 per Python.
*   **Frontend:** Uso di template parziali Jinja2 (es. `_ordini.html`) per evitare duplicazione di codice tra caricamento iniziale e aggiornamenti AJAX.
