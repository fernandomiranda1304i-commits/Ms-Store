import sqlite3

conexion = sqlite3.connect("tienda.db")
cursor = conexion.cursor()

# Borramos cualquier producto viejo para que no se repita
cursor.execute("DELETE FROM productos")

# Insertamos el nuevo producto
cursor.execute("INSERT INTO productos (nombre, precio) VALUES ('Perfume Tommy Girl', 15000)")
conexion.commit()
conexion.close()

print("¡Lista limpiada y Perfume Tommy Girl agregado con éxito!")