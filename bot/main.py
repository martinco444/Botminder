import sqlite3
import asyncio
from datetime import datetime
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters, filters
)
from config import TOKEN
import logging

logging.basicConfig(
    level=logging.DEBUG,  # DEBUG mientras depuras; cambiar a INFO en producción
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),               # muestra en terminal
        logging.FileHandler("bot.log", encoding="utf-8")  # guarda en archivo
    ]
)
logger = logging.getLogger(__name__)
logger.info("Arrancando Botminder")

# Estados de la conversación
RECORDATORIO, FECHA, HORA = range(3)

# Conexión SQLite
conn = sqlite3.connect("recordatorios.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS recordatorios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    recordatorio TEXT NOT NULL,
    fecha TEXT NOT NULL,
    hora TEXT NOT NULL,
    enviado INTEGER DEFAULT 0
);
''')
conn.commit()

# Asegurar columna `enviado` si la tabla ya existía sin esa columna
cursor.execute("PRAGMA table_info(recordatorios)")
cols = [row[1] for row in cursor.fetchall()]
if "enviado" not in cols:
    cursor.execute("ALTER TABLE recordatorios ADD COLUMN enviado INTEGER DEFAULT 0")
    conn.commit()

# Comandos
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
        "INSERT INTO recordatorios (usuario_id, recordatorio, fecha, hora) VALUES (?, ?, ?, ?)",
        (usuario_id, recordatorio, fecha, hora)
    )
    conn.commit()

    await update.message.reply_text(f"✅ Recordatorio guardado para el {fecha} a las {hora}.")
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

async def ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = update.effective_user.id
    cursor.execute(
        "SELECT recordatorio, fecha, hora FROM recordatorios WHERE usuario_id = ? ORDER BY fecha, hora",
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


# Función que envía los recordatorios pendientes en segundo plano
async def enviar_recordatorios(app):
    while True:
        ahora = datetime.now()
        fecha_actual = ahora.strftime("%Y-%m-%d")
        hora_actual = ahora.strftime("%H:%M")

        cursor.execute("""
            SELECT id, usuario_id, recordatorio FROM recordatorios
            WHERE fecha = ? AND hora = ? AND enviado = 0
        """, (fecha_actual, hora_actual))

        pendientes = cursor.fetchall()
        for rid, uid, mensaje in pendientes:
            try:
                await app.bot.send_message(chat_id=uid, text=f"⏰ Recordatorio:\n{mensaje}")
                cursor.execute("UPDATE recordatorios SET enviado = 1 WHERE id = ?", (rid,))
                conn.commit()
            except Exception as e:
                print(f"Error al enviar recordatorio al usuario {uid}: {e}")

        ahora = datetime.now()
        segundos_restantes = 60 - ahora.second - ahora.microsecond / 1_000_000
        await asyncio.sleep(segundos_restantes)

# Función principal
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

    async def _debug_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
        print("DEBUG UPDATE:", update)
    app.add_handler(MessageHandler(filters.ALL, _debug_log))

    async with app:
        await app.start()
        asyncio.ensure_future(enviar_recordatorios(app))
        await app.updater.start_polling()
        print("✅ Bot en ejecución...")
        await asyncio.Event().wait()

# Arranque seguro
if __name__ == "__main__":
    asyncio.run(main())

