"""Worker opcional para enviar recordatorios usando el pool de `database.py`.

Este script puede usarse como proceso separado si no quieres ejecutar
el worker dentro de `bot/main.py`. Usa las mismas funciones async del
módulo `database` para evitar discrepancias.
"""
import asyncio
import logging
from datetime import datetime, date, time

from telegram import Bot
from config import TOKEN
from database import init_db, obtener_pendientes, marcar_enviado

logger = logging.getLogger(__name__)
bot = Bot(token=TOKEN)


async def verificar_recordatorios():
    await init_db()
    while True:
        ahora = datetime.now()
        fecha_actual = date.today()
        hora_actual = time(ahora.hour, ahora.minute)

        logger.debug("Notifier wake: %s %s", fecha_actual, hora_actual)

        try:
            pendientes = await obtener_pendientes(fecha_actual, hora_actual)
            logger.info("Pendientes encontrados: %d", len(pendientes))

            for row in pendientes:
                rid = row['id']
                uid = row['usuario_id']
                mensaje = row['recordatorio']
                try:
                    await bot.send_message(chat_id=uid, text=f"📌 Recordatorio:\n{mensaje}")
                    await marcar_enviado(rid)
                    logger.info("Enviado recordatorio id=%s a usuario=%s", rid, uid)
                except Exception:
                    logger.exception("Error al enviar recordatorio id=%s a usuario=%s", rid, uid)
        except Exception:
            logger.exception("Error comprobando recordatorios")

        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(verificar_recordatorios())
