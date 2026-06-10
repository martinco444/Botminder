# ejemplo: bot/database.py
import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")
_pool = None

async def init_db():
    global _pool
    if not DATABASE_URL:
        return
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=int(os.getenv("DB_POOL_MAX","5")))
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS recordatorios (
                id SERIAL PRIMARY KEY,
                usuario_id BIGINT NOT NULL,
                recordatorio TEXT NOT NULL,
                fecha DATE NOT NULL,
                hora TIME NOT NULL,
                enviado BOOLEAN DEFAULT FALSE
            );
        """)

async def agregar_recordatorio(usuario_id, recordatorio, fecha, hora):
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO recordatorios (usuario_id, recordatorio, fecha, hora) VALUES($1,$2,$3,$4)",
            usuario_id, recordatorio, fecha, hora
        )

async def obtener_recordatorios_por_usuario(usuario_id):
    async with _pool.acquire() as conn:
        return await conn.fetch("SELECT recordatorio, fecha, hora FROM recordatorios WHERE usuario_id=$1 ORDER BY fecha, hora", usuario_id)

async def obtener_pendientes(fecha, hora):
    async with _pool.acquire() as conn:
        return await conn.fetch("SELECT id, usuario_id, recordatorio FROM recordatorios WHERE fecha=$1 AND hora=$2 AND enviado=FALSE", fecha, hora)

async def marcar_enviado(rid):
    async with _pool.acquire() as conn:
        await conn.execute("UPDATE recordatorios SET enviado=TRUE WHERE id=$1", rid)