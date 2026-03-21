import sqlite3

conn = sqlite3.connect("recordatorios.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM recordatorios")
filas = cursor.fetchall()

for fila in filas:
    print(fila)

conn.close()
