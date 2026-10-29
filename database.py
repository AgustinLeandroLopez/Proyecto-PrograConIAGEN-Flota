import sqlite3
from contextlib import contextmanager
from pathlib import Path
from escenario_flota import PERFILES, validar_configuracion

RUTA_BASE_DATOS = Path(__file__).with_name("flota.db")
VEHICULOS_INICIALES = [(1, "ABC123", 0, 45), (2, "DEF456", 0, 15), (3, "GHI789", 60, 0)]
CAMPOS_CONFIGURACION = ("zona", "tarifa_base", "precio_minimo")


@contextmanager
def conectar():
    conexion = sqlite3.connect(RUTA_BASE_DATOS)
    conexion.row_factory = sqlite3.Row
    try:
        yield conexion
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def inicializar_base_de_datos():
    with conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        es_nueva = conexion.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='vehiculos'").fetchone() is None
        conexion.execute("""CREATE TABLE IF NOT EXISTS vehiculos (
            id INTEGER PRIMARY KEY, patente TEXT NOT NULL UNIQUE,
            velocidad REAL NOT NULL CHECK (velocidad >= 0),
            minutos_detenido INTEGER NOT NULL CHECK (minutos_detenido >= 0),
            esperando_viaje INTEGER NOT NULL DEFAULT 0 CHECK (esperando_viaje IN (0,1)),
            en_viaje INTEGER NOT NULL DEFAULT 0 CHECK (en_viaje IN (0,1) AND NOT (en_viaje=1 AND esperando_viaje=1)),
            zona TEXT NOT NULL DEFAULT 'Centro' CHECK (zona IN ('Centro','Norte','Sur','Oeste')),
            tarifa_base INTEGER NOT NULL DEFAULT 4000
                CHECK (typeof(tarifa_base)='integer' AND tarifa_base BETWEEN 1 AND 1000000),
            precio_minimo INTEGER NOT NULL DEFAULT 3000
                CHECK (typeof(precio_minimo)='integer' AND precio_minimo BETWEEN 1 AND 1000000 AND precio_minimo <= tarifa_base)
        )""")
        columnas = {fila['name'] for fila in conexion.execute('PRAGMA table_info(vehiculos)')}
        if 'esperando_viaje' not in columnas:
            conexion.execute('ALTER TABLE vehiculos ADD COLUMN esperando_viaje INTEGER NOT NULL DEFAULT 0 CHECK (esperando_viaje IN (0,1))')
        if 'en_viaje' not in columnas:
            conexion.execute('ALTER TABLE vehiculos ADD COLUMN en_viaje INTEGER NOT NULL DEFAULT 0 CHECK (en_viaje IN (0,1) AND NOT (en_viaje=1 AND esperando_viaje=1))')
        definiciones = {
            'zona': "TEXT NOT NULL DEFAULT 'Centro' CHECK (zona IN ('Centro','Norte','Sur','Oeste'))",
            'tarifa_base': "INTEGER NOT NULL DEFAULT 4000 CHECK (typeof(tarifa_base)='integer' AND tarifa_base BETWEEN 1 AND 1000000)",
            'precio_minimo': "INTEGER NOT NULL DEFAULT 3000 CHECK (typeof(precio_minimo)='integer' AND precio_minimo BETWEEN 1 AND 1000000 AND precio_minimo <= tarifa_base)",
        }
        nuevas = [campo for campo in CAMPOS_CONFIGURACION if campo not in columnas]
        for campo in nuevas:
            # Nombres y definiciones de una lista cerrada, nunca texto del usuario.
            conexion.execute(f'ALTER TABLE vehiculos ADD COLUMN {campo} {definiciones[campo]}')
        if nuevas:
            for fila in conexion.execute('SELECT id FROM vehiculos').fetchall():
                perfil = dict(zip(CAMPOS_CONFIGURACION, PERFILES[(fila['id'] - 1) % len(PERFILES)]))
                asignaciones = ', '.join(f'{campo} = ?' for campo in nuevas)
                conexion.execute(f'UPDATE vehiculos SET {asignaciones} WHERE id = ?',
                                 (*[perfil[campo] for campo in nuevas], fila['id']))
        if es_nueva:
            for identificador, patente, velocidad, minutos in VEHICULOS_INICIALES:
                zona, base, minimo = PERFILES[(identificador - 1) % len(PERFILES)]
                conexion.execute('INSERT INTO vehiculos (id,patente,velocidad,minutos_detenido,zona,tarifa_base,precio_minimo) VALUES (?,?,?,?,?,?,?)',
                                 (identificador, patente, velocidad, minutos, zona, base, minimo))


def consultar_vehiculos():
    with conectar() as conexion:
        filas = conexion.execute('SELECT * FROM vehiculos ORDER BY id').fetchall()
    return [_convertir_vehiculo(fila) for fila in filas]


def consultar_vehiculo(vehiculo_id):
    with conectar() as conexion:
        fila = conexion.execute('SELECT * FROM vehiculos WHERE id = ?', (vehiculo_id,)).fetchone()
    return _convertir_vehiculo(fila) if fila else None


def actualizar_estado_vehiculo(vehiculo_id, velocidad, minutos_detenido, esperando_viaje,
                              *, zona=None, tarifa_base=None, precio_minimo=None, en_viaje=None):
    with conectar() as conexion:
        conexion.execute('BEGIN IMMEDIATE')
        anterior = conexion.execute('SELECT * FROM vehiculos WHERE id = ?', (vehiculo_id,)).fetchone()
        if anterior is None:
            return False
        if en_viaje is not None and type(en_viaje) is not bool:
            raise ValueError('En viaje debe ser verdadero o falso.')
        if en_viaje is True:
            esperando_viaje = False
        en_viaje = (bool(anterior['en_viaje']) if en_viaje is None else en_viaje) and not esperando_viaje
        zona = anterior['zona'] if zona is None else zona
        tarifa_base = anterior['tarifa_base'] if tarifa_base is None else tarifa_base
        precio_minimo = anterior['precio_minimo'] if precio_minimo is None else precio_minimo
        validar_configuracion(zona, tarifa_base, precio_minimo)
        conexion.execute('UPDATE vehiculos SET velocidad=?, minutos_detenido=?, esperando_viaje=?, zona=?, tarifa_base=?, precio_minimo=?, en_viaje=? WHERE id=?',
                         (velocidad, minutos_detenido, int(esperando_viaje), zona, tarifa_base, precio_minimo, int(en_viaje), vehiculo_id))
    return True


def agregar_vehiculo(patente, velocidad, minutos_detenido, esperando_viaje=False,
                     *, zona='Centro', tarifa_base=4000, precio_minimo=3000, en_viaje=False):
    if type(en_viaje) is not bool:
        raise ValueError('En viaje debe ser verdadero o falso.')
    if en_viaje:
        esperando_viaje = False
    validar_configuracion(zona, tarifa_base, precio_minimo)
    with conectar() as conexion:
        try:
            cursor = conexion.execute('INSERT INTO vehiculos (patente,velocidad,minutos_detenido,esperando_viaje,zona,tarifa_base,precio_minimo,en_viaje) VALUES (?,?,?,?,?,?,?,?)',
                                      (patente,velocidad,minutos_detenido,int(esperando_viaje),zona,tarifa_base,precio_minimo,int(en_viaje)))
        except sqlite3.IntegrityError:
            return None
        vehiculo_id = cursor.lastrowid
    return consultar_vehiculo(vehiculo_id)


def _convertir_vehiculo(fila):
    vehiculo = dict(fila)
    vehiculo['esperando_viaje'] = bool(vehiculo['esperando_viaje'])
    vehiculo['en_viaje'] = bool(vehiculo['en_viaje'])
    return vehiculo


def eliminar_vehiculo(vehiculo_id):
    with conectar() as conexion:
        cursor = conexion.execute('DELETE FROM vehiculos WHERE id = ?', (vehiculo_id,))
        return cursor.rowcount > 0


def aplicar_cambio_confirmado(operacion, anterior, nuevo):
    """Compara todos los campos, escribe y verifica en la misma transaccion."""
    with conectar() as conexion:
        conexion.execute('BEGIN IMMEDIATE')
        if operacion not in ('agregar','actualizar','eliminar'):
            raise ValueError('Operación no permitida.')
        if operacion != 'agregar':
            fila = conexion.execute('SELECT * FROM vehiculos WHERE id = ?', (anterior['id'],)).fetchone()
            if fila is None or _convertir_vehiculo(fila) != anterior:
                raise ValueError('El vehículo cambió o fue eliminado. Volvé a solicitar la operación.')
        if nuevo is not None:
            validar_configuracion(nuevo['zona'], nuevo['tarifa_base'], nuevo['precio_minimo'])
        try:
            if operacion == 'agregar':
                cursor = conexion.execute('INSERT INTO vehiculos (patente,velocidad,minutos_detenido,esperando_viaje,zona,tarifa_base,precio_minimo,en_viaje) VALUES (?,?,?,?,?,?,?,?)',
                                          (nuevo['patente'],nuevo['velocidad'],nuevo['minutos_detenido'],int(nuevo['esperando_viaje']),nuevo['zona'],nuevo['tarifa_base'],nuevo['precio_minimo'],int(nuevo['en_viaje'])))
                identificador = cursor.lastrowid
            elif operacion == 'actualizar':
                identificador = anterior['id']
                conexion.execute('UPDATE vehiculos SET patente=?,velocidad=?,minutos_detenido=?,esperando_viaje=?,zona=?,tarifa_base=?,precio_minimo=?,en_viaje=? WHERE id=?',
                                 (nuevo['patente'],nuevo['velocidad'],nuevo['minutos_detenido'],int(nuevo['esperando_viaje']),nuevo['zona'],nuevo['tarifa_base'],nuevo['precio_minimo'],int(nuevo['en_viaje']),identificador))
            else:
                identificador = anterior['id']
                conexion.execute('DELETE FROM vehiculos WHERE id = ?', (identificador,))
        except sqlite3.IntegrityError:
            raise ValueError('La patente ya existe o los datos no son válidos. No se aplicó el cambio.') from None
        fila = conexion.execute('SELECT * FROM vehiculos WHERE id = ?', (identificador,)).fetchone()
        resultado = _convertir_vehiculo(fila) if fila else None
        if operacion == 'eliminar':
            if resultado is not None:
                raise ValueError('No se pudo verificar la eliminación.')
        elif resultado is None or any(resultado[k] != v for k,v in nuevo.items()):
            raise ValueError('No se pudo verificar el cambio.')
        return resultado
