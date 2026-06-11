import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import asyncio
import logging
from datetime import datetime

import psycopg2
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from config import TOKEN

PORT = int(os.getenv("PORT", "8000"))
DATABASE_URL = os.getenv("DATABASE_URL")


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
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)

logger = logging.getLogger(__name__)
logger.info("Arrancando Botminder")

RECORDATORIO, FECHA, HORA = range(3)

if not DATABASE_URL:
    raise ValueError("Falta la variable de entorno DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS recordatorios (
    id SERIAL PRIMARY KEY,
    usuario_id BIGINT NOT NULL,
    recordatorio TEXT NOT NULL,
    fecha TEXT NOT NULL,
    hora TEXT NOT NULL,
    enviado INTEGER DEFAULT 0
);
""")

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

    cursor.execute(
        "INSERT INTO recordatorios (usuario_id, recordatorio, fecha, hora) VALUES (%s, %s, %s, %s)",
        (usuario_id, recordatorio, fecha, hora)
    )

    await update.message.reply_text(f"✅ Recordatorio guardado para el {fecha} a las {hora}.")
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

async def ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = update.effective_user.id
    cursor.execute(
        "SELECT recordatorio, fecha, hora FROM recordatorios WHERE usuario_id = %s ORDER BY fecha, hora",
        (usuario_id,)
    )
    resultados = cursor.fetchall()

    if not resultados:
        await update.message.reply_text("No tienes recordatorios guardados.")
    else:
        texto = "📋 *Tus recordatorios:*\n\n"
        for r in resultados:
            texto += f"📝 {r[0]}\n📅 {r[1]} 🕒 {r[2]}\n\n"
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
        fecha_actual = ahora.strftime("%Y-%m-%d")
        hora_actual = ahora.strftime("%H:%M")

        cursor.execute("""
            SELECT id, usuario_id, recordatorio
            FROM recordatorios
            WHERE fecha = %s AND hora = %s AND enviado = 0
        """, (fecha_actual, hora_actual))

        pendientes = cursor.fetchall()

        for rid, uid, mensaje in pendientes:
            try:
                await app.bot.send_message(chat_id=uid, text=f"⏰ Recordatorio:\n{mensaje}")
                cursor.execute(
                    "UPDATE recordatorios SET enviado = 1 WHERE id = %s",
                    (rid,)
                )
            except Exception as e:
                logger.error(f"Error al enviar recordatorio al usuario {uid}: {e}")

        ahora = datetime.now()
        segundos_restantes = 60 - ahora.second - ahora.microsecond / 1_000_000
        await asyncio.sleep(segundos_restantes)

async def main():
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