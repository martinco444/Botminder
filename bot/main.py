import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import asyncio
import logging
from datetime import datetime

from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from config import TOKEN
from database import init_db, agregar_recordatorio, obtener_recordatorios_por_usuario, obtener_pendientes, marcar_enviado

PORT = int(os.getenv("PORT", "8000"))

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def iniciar_servidor_health(port: int = PORT):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

iniciar_servidor_health()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]  # ← Sin FileHandler para evitar crash en cloud
)
logger = logging.getLogger(__name__)

RECORDATORIO, FECHA, HORA = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Soy Botminder 🤖 tu bot de recordatorios 🕓.\nUsa /agregar para registrar uno o /ver para consultarlos."
    )

async def agregar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¿Qué deseas recordar?")
    return RECORDATORIO

async def recibir_recordatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["recordatorio"] = update.message.text
    await update.message.reply_text("¿Para qué fecha? (formato: YYYY-MM-DD)")
    return FECHA

async def recibir_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["fecha"] = update.message.text
    await update.message.reply_text("¿A qué hora? (formato: HH:MM)")
    return HORA

async def recibir_hora(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = update.effective_user.id
    recordatorio = context.user_data["recordatorio"]
    fecha = context.user_data["fecha"]
    hora = update.message.text
    try:
        await agregar_recordatorio(usuario_id, recordatorio, fecha, hora)
        await update.message.reply_text(f"✅ Recordatorio guardado para el {fecha} a las {hora}.")
    except Exception as e:
        logger.error(f"Error al guardar recordatorio: {e}")
        await update.message.reply_text("❌ Error al guardar. Verifica el formato de fecha (YYYY-MM-DD) y hora (HH:MM).")
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

async def ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = update.effective_user.id
    resultados = await obtener_recordatorios_por_usuario(usuario_id)
    if not resultados:
        await update.message.reply_text("No tienes recordatorios guardados.")
    else:
        texto = "📋 *Tus recordatorios:*\n\n"
        for r in resultados:
            texto += f"📝 {r['recordatorio']}\n📅 {r['fecha']} 🕒 {r['hora']}\n\n"
        await update.message.reply_text(texto, parse_mode="Markdown")

async def configurar_comandos(app):
    comandos = [
        BotCommand("start", "Iniciar el bot"),
        BotCommand("agregar", "Agregar un nuevo recordatorio"),
        BotCommand("ver", "Ver recordatorios"),
        BotCommand("cancelar", "Cancelar operación"),
    ]
    await app.bot.set_my_commands(comandos)

async def enviar_recordatorios(app):
    while True:
        ahora = datetime.now()
        from datetime import date, time
        fecha_actual = date.today()
        hora_actual = time(ahora.hour, ahora.minute)

        pendientes = await obtener_pendientes(fecha_actual, hora_actual)
        for row in pendientes:
            try:
                await app.bot.send_message(chat_id=row['usuario_id'], text=f"⏰ Recordatorio:\n{row['recordatorio']}")
                await marcar_enviado(row['id'])
            except Exception as e:
                logger.error(f"Error al enviar recordatorio: {e}")

        segundos_restantes = 60 - ahora.second - ahora.microsecond / 1_000_000
        await asyncio.sleep(segundos_restantes)

async def main():
    await init_db()  # ← CRÍTICO: inicializar el pool de asyncpg primero

    app = ApplicationBuilder().token(TOKEN).build()
    await configurar_comandos(app)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("agregar", agregar)],
        states={
            RECORDATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_recordatorio)],
            FECHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fecha)],
            HORA: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_hora)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("ver", ver))

    async with app:
        await app.start()
        asyncio.create_task(enviar_recordatorios(app))
        await app.updater.start_polling()
        logger.info("✅ Bot en ejecución...")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())