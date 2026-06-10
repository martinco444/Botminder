# scripts/migrate_sqlite_to_neon.py
import os, sqlite3
from dotenv import load_dotenv
import psycopg

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("Define DATABASE_URL en .env")

sconn = sqlite3.connect("recordatorios.db")
rows = sconn.execute("SELECT usuario_id, recordatorio, fecha, hora, enviado FROM recordatorios").fetchall()
with psycopg.connect(DATABASE_URL, autocommit=True) as pconn:
    with pconn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recordatorios (
                id SERIAL PRIMARY KEY,
                usuario_id BIGINT NOT NULL,
                recordatorio TEXT NOT NULL,
                fecha DATE NOT NULL,
                hora TIME NOT NULL,
                enviado BOOLEAN DEFAULT FALSE
            );
        """)
        for usuario_id, rec, fecha, hora, enviado in rows:
            cur.execute(
                "INSERT INTO recordatorios (usuario_id, recordatorio, fecha, hora, enviado) VALUES (%s,%s,%s,%s,%s)",
                (usuario_id, rec, fecha, hora, bool(enviado))
            )
print("Migración finalizada:", len(rows), "filas.")