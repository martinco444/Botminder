import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import asyncio
import logging
from datetime import datetime, date

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
    chat_id = update.effective_chat.id if update.effective_chat else usuario_id
    recordatorio = context.user_data["recordatorio"]
    fecha_txt = context.user_data["fecha"]
    hora_txt = update.message.text

    try:
        fecha = datetime.strptime(fecha_txt, "%Y-%m-%d").date()
        hora = datetime.strptime(hora_txt, "%H:%M").time()

        await agregar_recordatorio(usuario_id, chat_id, recordatorio, fecha, hora)
        await update.message.reply_text(
            f"✅ Recordatorio guardado para el {fecha} a las {hora_txt}."
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Formato inválido. Usa fecha YYYY-MM-DD y hora HH:MM."
        )
        return HORA
    except Exception as e:
        logger.error(f"Error al guardar recordatorio: {e}")
        await update.message.reply_text("❌ Error al guardar el recordatorio.")
        return ConversationHandler.END

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


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Devuelve el id de Telegram del usuario que ejecuta el comando.

    Útil para comprobar que el `usuario_id` guardado en la BD es el correcto.
    """
    uid = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else None
    logger.info("whoami requested by user=%s chat=%s", uid, chat_id)
    await update.message.reply_text(f"Tu id de Telegram es: {uid}")


async def dump(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los recordatorios guardados para el usuario (debug).

    Lista los recordatorios (recordatorio, fecha, hora). No modifica nada.
    """
    usuario_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else None
    logger.info("dump requested by user=%s chat=%s", usuario_id, chat_id)
    resultados = await obtener_recordatorios_por_usuario(usuario_id)
    if not resultados:
        await update.message.reply_text("No tienes recordatorios guardados.")
        return
    texto = "📋 *Tus recordatorios (debug):*\n\n"
    for r in resultados:
        texto += f"📝 {r['recordatorio']}\n📅 {r['fecha']} 🕒 {r['hora']}\n\n"
    await update.message.reply_text(texto, parse_mode="Markdown")


async def _debug_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Loggea la actualización completa para diagnóstico en Render."""
    try:
        payload = update.to_dict()
    except Exception:
        payload = str(update)
    logger.debug("DEBUG UPDATE: %s", payload)


async def force_send_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para forzar envío manual desde Telegram."""
    await update.message.reply_text("Forzando envío de recordatorios ahora...")
    enviados = await enviar_pendientes_una_vez(context.application, tolerance_seconds=59)
    await update.message.reply_text(f"Procesados {enviados} recordatorios.")


async def test_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envía un mensaje de prueba al chat actual para verificar entrega y token."""
    chat = update.effective_chat.id if update.effective_chat else (update.effective_user.id if update.effective_user else None)
    uid = update.effective_user.id if update.effective_user else None
    logger.info("test_send requested by user=%s chat=%s", uid, chat)
    if not chat:
        await update.message.reply_text("No se pudo determinar el chat donde enviar el test.")
        return
    try:
        await context.bot.send_message(chat_id=chat, text="✅ Test send: Mensaje de prueba desde Botminder.")
        await update.message.reply_text("Test enviado. Revisa tu chat.")
    except Exception as e:
        logger.exception("test_send failed: %s", e)
        await update.message.reply_text(f"Error al enviar test: {e}")


async def force_send_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envía todos tus recordatorios no enviados independientemente de la fecha/hora."""
    usuario_id = update.effective_user.id if update.effective_user else None
    if not usuario_id:
        await update.message.reply_text("No se pudo determinar tu usuario.")
        return
    await update.message.reply_text("Forzando envío de tus recordatorios pendientes...")
    try:
        resultados = await obtener_recordatorios_por_usuario(usuario_id)
        pendientes = [r for r in resultados if not r.get('enviado')]
        if not pendientes:
            await update.message.reply_text("No tienes recordatorios pendientes.")
            return
        enviados = 0
        for r in pendientes:
            rid = r['id']
            chat_id = r.get('chat_id') or usuario_id
            mensaje = r['recordatorio']
            try:
                await context.bot.send_message(chat_id=chat_id, text=f"⏰ Recordatorio:\n{mensaje}")
                await marcar_enviado(rid)
                enviados += 1
            except Exception:
                logger.exception("Error al enviar recordatorio personal id=%s", rid)

        await update.message.reply_text(f"Enviados {enviados} recordatorios.")
    except Exception as e:
        logger.exception("Error en force_send_me: %s", e)
        await update.message.reply_text(f"Error al procesar: {e}")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra conteos de la BD y hasta 20 pendientes para hoy.

    Restringe el acceso si se ha configurado `ADMIN_USER_ID`.
    """
    uid = update.effective_user.id if update.effective_user else None
    admin_allowed = os.getenv("ADMIN_USER_ID")
    if admin_allowed and str(uid) != admin_allowed:
        await update.message.reply_text("No autorizado para /status.")
        return

    try:
        import database as _db
        if not _db.PG_POOL:
            await update.message.reply_text("DB no inicializada (PG_POOL missing)")
            return

        async with _db.PG_POOL.acquire() as conn:
            total = await conn.fetchval("SELECT count(*) FROM recordatorios")
            pending_rows = await conn.fetch(
                "SELECT id, usuario_id, chat_id, recordatorio, fecha, hora FROM recordatorios WHERE fecha=$1 AND enviado=FALSE ORDER BY hora LIMIT 20",
                date.today(),
            )

            lines = [f"DB total={total} pendientes_hoy={len(pending_rows)}"]
            for r in pending_rows:
                rec = (r['recordatorio'] or "").replace("\n", " ")[:120]
                lines.append(f"id={r['id']} uid={r['usuario_id']} chat={r['chat_id']} {r['fecha']} {r['hora']} \"{rec}\"")

            await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logger.exception("Error in /status: %s", e)
        await update.message.reply_text(f"Error al obtener estado: {e}")

async def configurar_comandos(app):
    comandos = [
        BotCommand("start", "Iniciar el bot"),
        BotCommand("agregar", "Agregar un nuevo recordatorio"),
        BotCommand("ver", "Ver recordatorios"),
        BotCommand("whoami", "Mostrar tu id de Telegram (debug)"),
        BotCommand("dump", "Mostrar tus recordatorios (debug)"),
        BotCommand("status", "Mostrar estado DB y pendientes (admin)"),
        BotCommand("force_send_me", "Forzar envío de tus recordatorios pendientes"),
        BotCommand("cancelar", "Cancelar operación"),
    ]
    await app.bot.set_my_commands(comandos)

async def enviar_recordatorios(app):
    while True:
        ahora = datetime.now()
        from datetime import date, time
        fecha_actual = date.today()
        hora_actual = time(ahora.hour, ahora.minute)

        logger.debug("Scheduler wake: fecha=%s hora=%s", fecha_actual, hora_actual)
        try:
            pendientes = await obtener_pendientes(fecha_actual, hora_actual, tolerance_seconds=59)
            logger.info("Pendientes encontrados: %d", len(pendientes))
            for row in pendientes:
                rid = row['id']
                uid = row.get('usuario_id')
                chat_id = row.get('chat_id') or uid
                mensaje = row['recordatorio']
                try:
                    await app.bot.send_message(chat_id=chat_id, text=f"⏰ Recordatorio:\n{mensaje}")
                    await marcar_enviado(rid)
                    logger.info("Enviado recordatorio id=%s a usuario=%s chat=%s", rid, uid, chat_id)
                except Exception:
                    logger.exception("Error al enviar recordatorio id=%s a usuario=%s chat=%s", rid, uid, chat_id)
        except Exception:
            logger.exception("Error al obtener o procesar recordatorios pendientes")

        segundos_restantes = 60 - ahora.second - ahora.microsecond / 1_000_000
        await asyncio.sleep(segundos_restantes)


async def enviar_pendientes_una_vez(app, tolerance_seconds: int = 59) -> int:
    """Procesa y envía recordatorios pendientes una sola vez. Devuelve el número enviado."""
    ahora = datetime.now()
    from datetime import date, time
    fecha_actual = date.today()
    hora_actual = time(ahora.hour, ahora.minute)

    logger.info("Manual send: fecha=%s hora=%s tolerance=%s", fecha_actual, hora_actual, tolerance_seconds)
    enviados = 0
    try:
        pendientes = await obtener_pendientes(fecha_actual, hora_actual, tolerance_seconds=tolerance_seconds)
        logger.info("Pendientes encontrados (manual): %d", len(pendientes))
        for row in pendientes:
            rid = row['id']
            uid = row.get('usuario_id')
            chat_id = row.get('chat_id') or uid
            mensaje = row['recordatorio']
            try:
                await app.bot.send_message(chat_id=chat_id, text=f"⏰ Recordatorio:\n{mensaje}")
                await marcar_enviado(rid)
                enviados += 1
                logger.info("Enviado (manual) recordatorio id=%s a usuario=%s chat=%s", rid, uid, chat_id)
            except Exception:
                logger.exception("Error al enviar (manual) recordatorio id=%s a usuario=%s chat=%s", rid, uid, chat_id)
    except Exception:
        logger.exception("Error en envio manual de pendientes")

    return enviados

async def main():
    await init_db()  # ← CRÍTICO: inicializar el pool de asyncpg primero
    logger.info("init_db completado")
    # DB sanity check: report total rows and pending for today
    try:
        import database as _db
        if _db.PG_POOL:
            async with _db.PG_POOL.acquire() as _conn:
                total = await _conn.fetchval("SELECT count(*) FROM recordatorios")
                pending_today = await _conn.fetchval(
                    "SELECT count(*) FROM recordatorios WHERE fecha=$1 AND enviado=FALSE",
                    date.today(),
                )
                logger.info("DB counts: total=%s pending_today=%s", total, pending_today)
        else:
            logger.error("DB sanity check: PG_POOL not initialized")
    except Exception:
        logger.exception("DB sanity check failed")
    # Sanity checks for environment
    db_env = bool(os.getenv("DATABASE_URL"))
    token_env = bool(os.getenv("TOKEN"))
    logger.info("ENV CHECK: DATABASE_URL present=%s TOKEN present=%s", db_env, token_env)
    if not token_env:
        logger.error("ENV ERROR: TOKEN no está configurado; el bot no podrá arrancar correctamente")

    app = ApplicationBuilder().token(TOKEN).build()
    await configurar_comandos(app)

    # Verify bot token / Telegram connectivity early
    try:
        me = await app.bot.get_me()
        logger.info("Bot get_me: id=%s username=%s", getattr(me, 'id', None), getattr(me, 'username', None))
    except Exception:
        logger.exception("Bot get_me failed; check TOKEN env var and network connectivity")

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
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("dump", dump))
    app.add_handler(CommandHandler("force_send", force_send_cmd))
    app.add_handler(CommandHandler("test_send", test_send))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("force_send_me", force_send_me))
    app.add_handler(MessageHandler(filters.ALL, _debug_log))

    async with app:
        await app.start()
        asyncio.create_task(enviar_recordatorios(app))
        logger.info("Scheduler task creada")
        await app.updater.start_polling()
        logger.info("✅ Bot en ejecución...")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())