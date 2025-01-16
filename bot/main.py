from telegram.ext import Updater, CommandHandler
from config import TOKEN
from bot_logic import start, conversation_handler
from database import crear_base_datos

def start(update, context):
    update.message.reply_text("¡Hola! Estoy funcionando.")

def main():
    # Inicializar la base de datos
    crear_base_datos()

    # Configurar el bot
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Agregar manejadores de comandos
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(conversation_handler)

    # Iniciar el bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()