# Database access layer with Postgres (asyncpg) and SQLite fallback.
import os
import asyncio
import sqlite3
from typing import List, Dict, Any
from datetime import date, time

DATABASE_URL = os.getenv("DATABASE_URL")
PG_POOL = None
SQLITE_CONN: sqlite3.Connection | None = None


def _row_to_dict_sqlite(row: tuple) -> Dict[str, Any]:
    # sqlite row: (id, usuario_id, chat_id, recordatorio, fecha, hora, enviado)
    return {
        "id": row[0],
        "usuario_id": row[1],
        "chat_id": row[2],
        "recordatorio": row[3],
        "fecha": row[4],
        "hora": row[5],
        "enviado": bool(row[6])
    }


async def init_db():
    """Initialize DB: create pool for Postgres or create sqlite file and ensure schema.

    Also migrates existing data by setting `chat_id = usuario_id` when missing.
    """
    global PG_POOL, SQLITE_CONN
    if DATABASE_URL:
        import asyncpg
        PG_POOL = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=int(os.getenv("DB_POOL_MAX", "5")))
        async with PG_POOL.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS recordatorios (
                    id SERIAL PRIMARY KEY,
                    usuario_id BIGINT NOT NULL,
                    chat_id BIGINT,
                    recordatorio TEXT NOT NULL,
                    fecha DATE NOT NULL,
                    hora TIME NOT NULL,
                    enviado BOOLEAN DEFAULT FALSE
                );
            """)
            # ensure chat_id populated for existing rows
            await conn.execute("UPDATE recordatorios SET chat_id = usuario_id WHERE chat_id IS NULL")
    else:
        # fallback to sqlite for local testing
        SQLITE_CONN = sqlite3.connect("recordatorios.db", check_same_thread=False)
        cur = SQLITE_CONN.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recordatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                chat_id INTEGER,
                recordatorio TEXT NOT NULL,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,
                enviado INTEGER DEFAULT 0
            );
        """)
        SQLITE_CONN.commit()
        # ensure chat_id column exists and is populated
        cur.execute("PRAGMA table_info(recordatorios)")
        cols = [r[1] for r in cur.fetchall()]
        if "chat_id" not in cols:
            cur.execute("ALTER TABLE recordatorios ADD COLUMN chat_id INTEGER")
            cur.execute("UPDATE recordatorios SET chat_id = usuario_id")
            SQLITE_CONN.commit()


async def agregar_recordatorio(usuario_id: int, chat_id: int, recordatorio: str, fecha: date, hora: time):
    """Insert a new reminder. `fecha` and `hora` can be date/time objects.
    """
    if PG_POOL:
        async with PG_POOL.acquire() as conn:
            await conn.execute(
                "INSERT INTO recordatorios (usuario_id, chat_id, recordatorio, fecha, hora) VALUES($1,$2,$3,$4,$5)",
                usuario_id, chat_id, recordatorio, fecha, hora
            )
    else:
        loop = asyncio.get_running_loop()

        def _sync():
            cur = SQLITE_CONN.cursor()
            fecha_s = fecha.isoformat() if isinstance(fecha, date) else str(fecha)
            hora_s = hora.strftime("%H:%M:%S") if isinstance(hora, time) else str(hora)
            cur.execute(
                "INSERT INTO recordatorios (usuario_id, chat_id, recordatorio, fecha, hora) VALUES (?, ?, ?, ?, ?)",
                (usuario_id, chat_id, recordatorio, fecha_s, hora_s)
            )
            SQLITE_CONN.commit()

        await loop.run_in_executor(None, _sync)


async def obtener_recordatorios_por_usuario(usuario_id: int) -> List[Dict[str, Any]]:
    if PG_POOL:
        async with PG_POOL.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, usuario_id, chat_id, recordatorio, fecha, hora, enviado FROM recordatorios WHERE usuario_id=$1 ORDER BY fecha, hora",
                usuario_id,
            )
            return [dict(r) for r in rows]
    else:
        loop = asyncio.get_running_loop()

        def _sync():
            cur = SQLITE_CONN.cursor()
            cur.execute(
                "SELECT id, usuario_id, chat_id, recordatorio, fecha, hora, enviado FROM recordatorios WHERE usuario_id = ? ORDER BY fecha, hora",
                (usuario_id,)
            )
            rows = cur.fetchall()
            return [_row_to_dict_sqlite(r) for r in rows]

        return await loop.run_in_executor(None, _sync)


async def obtener_pendientes(fecha_val: date, hora_val: time) -> List[Dict[str, Any]]:
    """Return pending reminders for given date and time.

    `fecha_val` is a date, `hora_val` is a time object.
    """
    if PG_POOL:
        async with PG_POOL.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, usuario_id, chat_id, recordatorio FROM recordatorios WHERE fecha=$1 AND hora=$2 AND enviado=FALSE",
                fecha_val, hora_val,
            )
            return [dict(r) for r in rows]
    else:
        loop = asyncio.get_running_loop()

        def _sync():
            cur = SQLITE_CONN.cursor()
            fecha_s = fecha_val.isoformat() if isinstance(fecha_val, date) else str(fecha_val)
            hora_s = hora_val.strftime("%H:%M:%S") if isinstance(hora_val, time) else str(hora_val)
            cur.execute(
                "SELECT id, usuario_id, chat_id, recordatorio FROM recordatorios WHERE fecha = ? AND hora = ? AND enviado = 0",
                (fecha_s, hora_s),
            )
            rows = cur.fetchall()
            return [_row_to_dict_sqlite(r) for r in rows]

        return await loop.run_in_executor(None, _sync)


async def marcar_enviado(rid: int):
    if PG_POOL:
        async with PG_POOL.acquire() as conn:
            await conn.execute("UPDATE recordatorios SET enviado=TRUE WHERE id=$1", rid)
    else:
        loop = asyncio.get_running_loop()

        def _sync():
            cur = SQLITE_CONN.cursor()
            cur.execute("UPDATE recordatorios SET enviado = 1 WHERE id = ?", (rid,))
            SQLITE_CONN.commit()

        await loop.run_in_executor(None, _sync)