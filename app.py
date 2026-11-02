import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'ms_store_clave_secreta_segura'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def init_db():
    conn = sqlite3.connect('tienda.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio REAL NOT NULL,
            descripcion TEXT,
            imagen TEXT,
            categoria TEXT DEFAULT 'Otros',
            ventas INTEGER DEFAULT 0,
            insignia TEXT DEFAULT ''
        )
    ''')
    try:
        cursor.execute("ALTER TABLE productos ADD COLUMN categoria TEXT DEFAULT 'Otros'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE productos ADD COLUMN ventas INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE productos ADD COLUMN insignia TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def actualizar_mas_vendido():
    """Función automática que calcula el producto con más ventas (mínimo 4 o el mayor)"""
    conn = sqlite3.connect('tienda.db')
    cursor = conn.cursor()
    
    # Quitar insignia de más vendido a todos temporalmente
    cursor.execute("UPDATE productos SET insignia = '' WHERE insignia = '🔥 Más Vendido'")
    
    # Buscar el producto con mayor cantidad de ventas (que tenga al menos 3 ventas)
    cursor.execute("SELECT id, ventas FROM productos WHERE ventas >= 3 ORDER BY ventas DESC LIMIT 1")
    top_producto = cursor.fetchone()
    
    if top_producto:
        prod_id = top_producto[0]
        cursor.execute("UPDATE productos SET insignia = '🔥 Más Vendido' WHERE id = ?", (prod_id,))
        
    conn.commit()
    conn.close()

@app.route('/')
def index():
    actualizar_mas_vendido() # Se actualiza automáticamente al cargar la tienda
    
    conn = sqlite3.connect('tienda.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM productos")
    productos = cursor.fetchall()
    conn.close()
    
    categorias = {}
    for p in productos:
        cat = p[5] if len(p) > 5 and p[5] and p[5].strip() != '' else 'Otros'
        if cat not in categorias:
            categorias[cat] = []
        categorias[cat].append(p)
        
    cantidad_carrito = len(session.get('carrito', []))
    return render_template('index.html', categorias=categorias, cantidad_carrito=cantidad_carrito)

@app.route('/admin')
def admin():
    conn = sqlite3.connect('tienda.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM productos")
    productos = cursor.fetchall()
    conn.close()
    return render_template('admin.html', productos=productos)

@app.route('/agregar', methods=['POST'])
def agregar():
    nombre = request.form['nombre']
    precio = request.form['precio']
    descripcion = request.form['descripcion']
    categoria = request.form['categoria']
    file = request.files['imagen']
    
    filename = ''
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
    conn = sqlite3.connect('tienda.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO productos (nombre, precio, descripcion, imagen, categoria, ventas, insignia) VALUES (?, ?, ?, ?, ?, 0, '')",
                   (nombre, precio, descripcion, filename, categoria))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    conn = sqlite3.connect('tienda.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM productos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/agregar-carrito/<int:id>', methods=['POST'])
def agregar_carrito(id):
    if 'carrito' not in session:
        session['carrito'] = []
    session['carrito'].append(id)
    session.modified = True
    
    # Sumar una venta automáticamente al producto cuando lo agregan al carrito / compran
    conn = sqlite3.connect('tienda.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE productos SET ventas = ventas + 1 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'cantidad_carrito': len(session['carrito'])})
    
    return redirect(request.referrer or url_for('index'))

@app.route('/comprar-directo/<int:id>')
def comprar_directo(id):
    session['carrito'] = [id]
    session.modified = True
    
    # Sumar venta por compra directa
    conn = sqlite3.connect('tienda.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE productos SET ventas = ventas + 1 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('checkout'))

def calcular_total_carrito(session_carrito):
    if not session_carrito:
        return [], 0
    
    conn = sqlite3.connect('tienda.db')
    cursor = conn.cursor()
    
    productos_carrito = []
    for prod_id in session_carrito:
        cursor.execute("SELECT * FROM productos WHERE id = ?", (prod_id,))
        p = cursor.fetchone()
        if p:
            productos_carrito.append(p)
    conn.close()
    
    poleras = [p for p in productos_carrito if len(p) > 5 and p[5] == 'Poleras']
    cinturones = [p for p in productos_carrito if len(p) > 5 and p[5] == 'Cinturones']
    otros_productos = [p for p in productos_carrito if len(p) > 5 and p[5] not in ('Poleras', 'Cinturones')]
    
    total = 0
    
    pares_poleras = len(poleras) // 2
    sueltas_poleras = len(poleras) % 2
    total += pares_poleras * 25000
    for i in range(sueltas_poleras):
        total += poleras[i][2]
        
    pares_cinturones = len(cinturones) // 2
    sueltos_cinturones = len(cinturones) % 2
    total += pares_cinturones * 25000
    for i in range(sueltos_cinturones):
        total += cinturones[i][2]
        
    for p in otros_productos:
        total += p[2]
        
    return productos_carrito, total

@app.route('/carrito')
def ver_carrito():
    if 'carrito' not in session or not session['carrito']:
        return render_template('carrito.html', productos=[], total=0)
    
    productos_carrito, total = calcular_total_carrito(session['carrito'])
    return render_template('carrito.html', productos=productos_carrito, total=total)

@app.route('/eliminar-item-carrito/<int:index>', methods=['POST'])
def eliminar_item_carrito(index):
    if 'carrito' in session:
        if 0 <= index < len(session['carrito']):
            session['carrito'].pop(index)
            session.modified = True
    return redirect(url_for('ver_carrito'))

@app.route('/checkout')
def checkout():
    if 'carrito' not in session or not session['carrito']:
        return redirect(url_for('index'))
    
    productos_carrito, total = calcular_total_carrito(session['carrito'])
    return render_template('checkout.html', productos=productos_carrito, total=total)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', debug=True) 