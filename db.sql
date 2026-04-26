-- ==================== Utenti ====================
CREATE TABLE IF NOT EXISTS utenti (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    attivo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS permessi_pagine (
    utente_id INTEGER NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
    pagina TEXT NOT NULL,
    PRIMARY KEY (utente_id, pagina)
);

-- ==================== Prodotti ====================
CREATE TABLE IF NOT EXISTS prodotti (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    prezzo NUMERIC(10, 2) NOT NULL,
    categoria_menu TEXT NOT NULL,
    categoria_dashboard TEXT NOT NULL CHECK (categoria_dashboard IN ('Bar', 'Cucina', 'Gnoccheria', 'Griglia', 'Coperto')),
    disponibile BOOLEAN NOT NULL DEFAULT FALSE,
    quantita INTEGER NOT NULL,
    venduti INTEGER NOT NULL
);

-- ==================== Ordini ====================
CREATE TABLE IF NOT EXISTS ordini (
    id SERIAL PRIMARY KEY,
    asporto BOOLEAN NOT NULL,
    data_ordine TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    nome_cliente TEXT NOT NULL,
    numero_tavolo INTEGER CHECK (numero_tavolo > 0),
    numero_persone INTEGER CHECK (numero_persone > 0),
    metodo_pagamento TEXT NOT NULL CHECK (metodo_pagamento IN ('Contanti', 'Carta')),
    completato BOOLEAN NOT NULL DEFAULT FALSE
);

-- ==================== Ordini / Prodotti ====================
CREATE TABLE IF NOT EXISTS ordini_prodotti (
    ordine_id INTEGER NOT NULL REFERENCES ordini(id) ON DELETE CASCADE,
    prodotto_id INTEGER NOT NULL REFERENCES prodotti(id),
    quantita INTEGER NOT NULL CHECK (quantita > 0),
    stato TEXT NOT NULL DEFAULT 'In Attesa' CHECK (stato IN ('In Attesa', 'In Preparazione', 'Pronto', 'Completato')),
    PRIMARY KEY (ordine_id, prodotto_id)
);
