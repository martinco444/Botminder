import sqlite3
import datetime
import time
from telegram import Bot

TOKEN = "7763947493:AAGNbjziuiPEZTUmRpGGLCJx5Vo4-11Qvrc"  # Reemplaza con tu token real
bot = Bot(token=TOKEN)

def verificar_recordatorios():
    while True:
        ahora = datetime.datetime.now()
        fecha_actual = ahora.strftime("%Y-%m-%d")
        hora_actual = ahora.strftime("%H:%M")

        conn = sqlite3.connect("recordatorios.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, user_id, mensaje FROM recordatorios
            WHERE fecha = ? AND hora = ? AND enviado = 0
        """, (fecha_actual, hora_actual))

        recordatorios = cursor.fetchall()

        for recordatorio in recordatorios:
            id_recordatorio, user_id, mensaje = recordatorio

            try:
                bot.send_message(chat_id=user_id, text=f"📌 Recordatorio:\n{mensaje}")
                print(f"Recordatorio enviado a {user_id}: {mensaje}")

                # Marcar como enviado
                cursor.execute("UPDATE recordatorios SET enviado = 1 WHERE id = ?", (id_recordatorio,))
                conn.commit()
            except Exception as e:
                print(f"Error enviando mensaje: {e}")

        conn.close()
        time.sleep(60)  # Esperar un minuto
