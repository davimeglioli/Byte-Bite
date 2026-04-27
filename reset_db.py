import os
import psycopg2

from create_db import PRODOTTI_DEFAULT


def reset_db():
    connessione = None
    try:
        connessione = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_NAME", "byte_bite"),
            user=os.getenv("DB_USER", "byte_bite_user"),
            password=os.getenv("DB_PASSWORD", "secure_password_change_me"),
            connect_timeout=30,
        )
        cursore = connessione.cursor()

        cursore.execute("TRUNCATE ordini, prodotti RESTART IDENTITY CASCADE")

        cursore.executemany(
            "INSERT INTO prodotti"
            " (nome, prezzo, categoria_menu, categoria_dashboard, disponibile, quantita, venduti)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            PRODOTTI_DEFAULT,
        )

        connessione.commit()
    except psycopg2.Error:
        if connessione:
            connessione.rollback()
    finally:
        if connessione:
            connessione.close()


if __name__ == "__main__":
    reset_db()
