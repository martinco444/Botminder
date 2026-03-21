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
