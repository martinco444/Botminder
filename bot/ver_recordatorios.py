import asyncio
from database import init_db


async def main():
    await init_db()
    import database

    pg = database.PG_POOL
    if not pg:
        print("Postgres pool not initialized; DATABASE_URL is required")
        return

    async with pg.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, usuario_id, chat_id, recordatorio, fecha, hora, enviado FROM recordatorios ORDER BY fecha,hora"
        )
        for r in rows:
            print(dict(r))
        print(f"Total filas: {len(rows)}")


if __name__ == '__main__':
    asyncio.run(main())
