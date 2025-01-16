from telegram import Update
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackContext
from database import agregar_recordatorio
import datetime

PEDIR_MENSAJE, PEDIR_FECHA = range(2)

def start(update: Update, context: CallbackContext):
    update.message.reply_text("¡Hola! Soy tu bot de recordatorios. Usa /recordatorio para guardar uno.")

def pedir_mensaje(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("¿Qué necesitas recordar?")
    return PEDIR_FECHA

def pedir_fecha(update: Update, context: CallbackContext) -> int:
    context.user_data['mensaje'] = update.message.text
    update.message.reply_text("¿Cuándo quieres que te lo recuerde? Formato: YYYY-MM-DD HH:MM")
    return PEDIR_MENSAJE

def guardar_recordatorio(update: Update, context: CallbackContext) -> int:
    try:
        fecha_hora = datetime.datetime.strptime(update.message.text, "%Y-%m-%d %H:%M")
        mensaje = context.user_data['mensaje']
        usuario_id = update.message.from_user.id
        
        agregar_recordatorio(usuario_id, mensaje, fecha_hora)
        update.message.reply_text("¡Recordatorio guardado!")
    except ValueError:
        update.message.reply_text("Fecha/hora inválida. Inténtalo de nuevo.")
        return PEDIR_FECHA

    return ConversationHandler.END


conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('recordatorio', pedir_mensaje)],
    states={
        PEDIR_FECHA: [MessageHandler(Filters.text & ~Filters.command, pedir_fecha)],
        PEDIR_MENSAJE: [MessageHandler(Filters.text & ~Filters.command, guardar_recordatorio)],
    },
    fallbacks=[]
)
