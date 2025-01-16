import sqlite3

def crear_base_datos():
    conn = sqlite3.connect('recordatorios.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recordatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            mensaje TEXT,
            fecha_hora DATETIME
        )
    ''')
    conn.commit()
    conn.close()

def agregar_recordatorio(usuario_id, mensaje, fecha_hora):
    conn = sqlite3.connect('recordatorios.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO recordatorios (usuario_id, mensaje, fecha_hora)
        VALUES (?, ?, ?)
    ''', (usuario_id, mensaje, fecha_hora))
    conn.commit()
    conn.close()

def obtener_recordatorios():
    conn = sqlite3.connect('recordatorios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM recordatorios')
    datos = cursor.fetchall()
    conn.close()
    return datos


# def save_reminder(reminder):
#     # Conectar a la base de datos (o crearla si no existe)
#     conn = sqlite3.connect('recordatorios.db')
#     cursor = conn.cursor()
    
#     # Crear tabla si no existe
#     cursor.execute('''CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY, reminder TEXT)''')
    
#     # Insertar recordatorio
#     cursor.execute("INSERT INTO reminders (reminder) VALUES (?)", (reminder,))
#     conn.commit()

#     print(f"Recordatorio guardado: {reminder}")  # Esto imprimirá en la terminal

#     conn.close()

# # Para usar la función
# save_reminder("Mi primer recordatorio")