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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)
bot: Bot | None = None


async def verificar_recordatorios():
    await init_db()
    logger.info("Notifier inicializado")
    global bot
    if not TOKEN:
        logger.error("TOKEN no está configurado; el notifier no podrá enviar mensajes")
        return
    try:
        bot = Bot(token=TOKEN)
        logger.info("Bot inicializado en notificador")
    except Exception:
        logger.exception("No se pudo inicializar el Bot en notificador")
        return
    while True:
        ahora = datetime.now()
        fecha_actual = date.today()
        hora_actual = time(ahora.hour, ahora.minute)

        logger.info("Notifier wake: %s %s", fecha_actual, hora_actual)

        try:
            pendientes = await obtener_pendientes(fecha_actual, hora_actual, tolerance_seconds=59)
            logger.info("Pendientes encontrados: %d", len(pendientes))

            for row in pendientes:
                rid = row['id']
                uid = row.get('usuario_id')
                chat_id = row.get('chat_id') or uid
                mensaje = row['recordatorio']
                try:
                    if not bot:
                        logger.error("Bot no inicializado; saltando envio id=%s", rid)
                        continue
                    await bot.send_message(chat_id=chat_id, text=f"📌 Recordatorio:\n{mensaje}")
                    await marcar_enviado(rid)
                    logger.info("Enviado recordatorio id=%s a usuario=%s chat=%s", rid, uid, chat_id)
                except Exception:
                    logger.exception("Error al enviar recordatorio id=%s a usuario=%s chat=%s", rid, uid, chat_id)
        except Exception:
            logger.exception("Error comprobando recordatorios")

        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(verificar_recordatorios())
