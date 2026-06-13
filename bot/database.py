"""Database access layer — Postgres (Neon) only.

This module requires the environment variable `DATABASE_URL` to be set.
It intentionally removes any SQLite fallback so production always uses Neon Postgres.
"""
import os
import logging
from typing import List, Dict, Any
from datetime import date, time

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
PG_POOL = None


async def init_db():
    """Initialize Postgres pool and ensure schema exists.

    Raises RuntimeError if `DATABASE_URL` is not configured.
    """
    global PG_POOL
    logger.info("init_db starting; DATABASE_URL present=%s", bool(DATABASE_URL))
    if not DATABASE_URL:
        logger.error("DATABASE_URL is not set. Aborting: Neon Postgres is required.")
        raise RuntimeError("DATABASE_URL env var is required; configure Neon Postgres URL")

    import asyncpg

    try:
        PG_POOL = await asyncpg.create_pool(
            DATABASE_URL, min_size=1, max_size=int(os.getenv("DB_POOL_MAX", "5"))
        )
        logger.info("Postgres pool created")

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
            # Ensure `chat_id` column exists and populate it for existing rows.
            await conn.execute("ALTER TABLE recordatorios ADD COLUMN IF NOT EXISTS chat_id BIGINT")
            await conn.execute("UPDATE recordatorios SET chat_id = usuario_id WHERE chat_id IS NULL")
            logger.info("Postgres table ensured and chat_id populated")
    except Exception as e:
        logger.exception("Error creating Postgres pool or ensuring schema: %s", e)
        raise


async def agregar_recordatorio(usuario_id: int, chat_id: int, recordatorio: str, fecha: date, hora: time):
    """Insert a new reminder into Postgres.
    """
    if not PG_POOL:
        raise RuntimeError("Postgres pool not initialized; DATABASE_URL is required")

    async with PG_POOL.acquire() as conn:
        await conn.execute(
            "INSERT INTO recordatorios (usuario_id, chat_id, recordatorio, fecha, hora) VALUES($1,$2,$3,$4,$5)",
            usuario_id,
            chat_id,
            recordatorio,
            fecha,
            hora,
        )


async def obtener_recordatorios_por_usuario(usuario_id: int) -> List[Dict[str, Any]]:
    if not PG_POOL:
        raise RuntimeError("Postgres pool not initialized; DATABASE_URL is required")

    async with PG_POOL.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, usuario_id, chat_id, recordatorio, fecha, hora, enviado FROM recordatorios WHERE usuario_id=$1 ORDER BY fecha, hora",
            usuario_id,
        )
        return [dict(r) for r in rows]


async def obtener_pendientes(fecha_val: date, hora_val: time, tolerance_seconds: int = 0) -> List[Dict[str, Any]]:
    """Return pending reminders for given date and time.

    If `tolerance_seconds` > 0, return reminders within +/- that many seconds
    from `hora_val` (useful to tolerate small clock differences).
    """
    if not PG_POOL:
        raise RuntimeError("Postgres pool not initialized; DATABASE_URL is required")

    async with PG_POOL.acquire() as conn:
        if tolerance_seconds and tolerance_seconds > 0:
            rows = await conn.fetch(
                """
                SELECT id, usuario_id, chat_id, recordatorio
                FROM recordatorios
                WHERE fecha=$1
                  AND ABS(EXTRACT(EPOCH FROM (hora - $2::time))) <= $3
                  AND enviado=FALSE
                """,
                fecha_val,
                hora_val,
                tolerance_seconds,
            )
        else:
            rows = await conn.fetch(
                "SELECT id, usuario_id, chat_id, recordatorio FROM recordatorios WHERE fecha=$1 AND hora=$2 AND enviado=FALSE",
                fecha_val,
                hora_val,
            )
        return [dict(r) for r in rows]


async def marcar_enviado(rid: int):
    if not PG_POOL:
        raise RuntimeError("Postgres pool not initialized; DATABASE_URL is required")

    async with PG_POOL.acquire() as conn:
        await conn.execute("UPDATE recordatorios SET enviado=TRUE WHERE id=$1", rid)
