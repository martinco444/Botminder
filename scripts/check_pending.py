"""Script de debug: lista recordatorios en Neon Postgres para hoy.

Uso:
    python scripts/check_pending.py [--all] [--usuario <id>]

Requiere `DATABASE_URL` apuntando a la base de datos Neon; no usa SQLite.
"""
import asyncio
import os
import argparse
from datetime import date

from database import init_db


async def list_pending(all_today: bool, usuario: int | None):
    await init_db()
    import database

    pg = database.PG_POOL
    if not pg:
        print("Postgres pool not initialized; DATABASE_URL is required")
        return

    async with pg.acquire() as conn:
        if usuario:
            rows = await conn.fetch(
                "SELECT id, usuario_id, chat_id, recordatorio, fecha, hora, enviado FROM recordatorios WHERE usuario_id=$1 ORDER BY fecha,hora",
                usuario,
            )
        else:
            if all_today:
                rows = await conn.fetch(
                    "SELECT id, usuario_id, chat_id, recordatorio, fecha, hora, enviado FROM recordatorios WHERE fecha=$1 ORDER BY hora",
                    date.today(),
                )
            else:
                rows = await conn.fetch(
                    "SELECT id, usuario_id, chat_id, recordatorio, fecha, hora, enviado FROM recordatorios ORDER BY fecha,hora LIMIT 200",
                )

        for r in rows:
            print(dict(r))
        print(f"Total filas: {len(rows)}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true', help='Listar todos los recordatorios de hoy')
    parser.add_argument('--usuario', type=int, help='Filtrar por usuario_id')
    args = parser.parse_args()
    asyncio.run(list_pending(args.all, args.usuario))
