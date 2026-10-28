import sqlite3
from contextlib import contextmanager
from pathlib import Path


RUTA_BASE_DATOS = Path(__file__).with_name("flota.db")

VEHICULOS_INICIALES = [
    (1, "ABC123", 0, 45),
    (2, "DEF456", 0, 15),
    (3, "GHI789", 60, 0),
]


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
        es_nueva = conexion.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'vehiculos'"
        ).fetchone() is None
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS vehiculos (
                id INTEGER PRIMARY KEY,
                patente TEXT NOT NULL UNIQUE,
                velocidad REAL NOT NULL CHECK (velocidad >= 0),
                minutos_detenido INTEGER NOT NULL CHECK (minutos_detenido >= 0),
                esperando_viaje INTEGER NOT NULL DEFAULT 0
                    CHECK (esperando_viaje IN (0, 1))
            )
            """
        )
        columnas = {
            fila["name"]
            for fila in conexion.execute("PRAGMA table_info(vehiculos)").fetchall()
        }
        if "esperando_viaje" not in columnas:
            conexion.execute(
                """
                ALTER TABLE vehiculos
                ADD COLUMN esperando_viaje INTEGER NOT NULL DEFAULT 0
                    CHECK (esperando_viaje IN (0, 1))
                """
            )
        if es_nueva:
            conexion.executemany(
                """
                INSERT OR IGNORE INTO vehiculos
                    (id, patente, velocidad, minutos_detenido)
                VALUES (?, ?, ?, ?)
                """,
                VEHICULOS_INICIALES,
            )


def consultar_vehiculos():
    with conectar() as conexion:
        filas = conexion.execute(
            """
            SELECT id, patente, velocidad, minutos_detenido, esperando_viaje
            FROM vehiculos
            ORDER BY id
            """
        ).fetchall()

    return [_convertir_vehiculo(fila) for fila in filas]


def consultar_vehiculo(vehiculo_id):
    with conectar() as conexion:
        fila = conexion.execute(
            """
            SELECT id, patente, velocidad, minutos_detenido, esperando_viaje
            FROM vehiculos
            WHERE id = ?
            """,
            (vehiculo_id,),
        ).fetchone()

    return _convertir_vehiculo(fila) if fila else None


def actualizar_estado_vehiculo(
    vehiculo_id,
    velocidad,
    minutos_detenido,
    esperando_viaje,
):
    with conectar() as conexion:
        cursor = conexion.execute(
            """
            UPDATE vehiculos
            SET velocidad = ?, minutos_detenido = ?, esperando_viaje = ?
            WHERE id = ?
            """,
            (velocidad, minutos_detenido, int(esperando_viaje), vehiculo_id),
        )

    return cursor.rowcount > 0


def agregar_vehiculo(patente, velocidad, minutos_detenido, esperando_viaje=False):
    with conectar() as conexion:
        try:
            cursor = conexion.execute(
                """
                INSERT INTO vehiculos
                    (patente, velocidad, minutos_detenido, esperando_viaje)
                VALUES (?, ?, ?, ?)
                """,
                (patente, velocidad, minutos_detenido, int(esperando_viaje)),
            )
        except sqlite3.IntegrityError:
            return None

        vehiculo_id = cursor.lastrowid

    return consultar_vehiculo(vehiculo_id)


def _convertir_vehiculo(fila):
    vehiculo = dict(fila)
    vehiculo["esperando_viaje"] = bool(vehiculo["esperando_viaje"])
    return vehiculo


def eliminar_vehiculo(vehiculo_id):
    with conectar() as conexion:
        cursor = conexion.execute("DELETE FROM vehiculos WHERE id = ?", (vehiculo_id,))
        return cursor.rowcount > 0


def aplicar_cambio_confirmado(operacion, anterior, nuevo):
    """Aplica una propuesta validada y comprueba el resultado en una transacción.

    El bloqueo de escritura impide modificar una unidad que cambió desde que
    el operador revisó la propuesta. El SQL y las columnas son siempre fijos.
    """
    with conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        if operacion not in ("agregar", "actualizar", "eliminar"):
            raise ValueError("Operación no permitida.")
        if operacion != "agregar":
            fila = conexion.execute("SELECT * FROM vehiculos WHERE id = ?", (anterior["id"],)).fetchone()
            if fila is None or _convertir_vehiculo(fila) != anterior:
                raise ValueError("El vehículo cambió o fue eliminado. Volvé a solicitar la operación.")
        try:
            if operacion == "agregar":
                cursor = conexion.execute(
                    "INSERT INTO vehiculos (patente, velocidad, minutos_detenido, esperando_viaje) VALUES (?, ?, ?, ?)",
                    (nuevo["patente"], nuevo["velocidad"], nuevo["minutos_detenido"], int(nuevo["esperando_viaje"])),
                )
                identificador = cursor.lastrowid
            elif operacion == "actualizar":
                identificador = anterior["id"]
                conexion.execute(
                    "UPDATE vehiculos SET patente = ?, velocidad = ?, minutos_detenido = ?, esperando_viaje = ? WHERE id = ?",
                    (nuevo["patente"], nuevo["velocidad"], nuevo["minutos_detenido"], int(nuevo["esperando_viaje"]), identificador),
                )
            else:
                identificador = anterior["id"]
                conexion.execute("DELETE FROM vehiculos WHERE id = ?", (identificador,))
        except sqlite3.IntegrityError:
            raise ValueError("La patente ya existe o los datos no son válidos. No se aplicó el cambio.") from None
        fila = conexion.execute("SELECT * FROM vehiculos WHERE id = ?", (identificador,)).fetchone()
        resultado = _convertir_vehiculo(fila) if fila else None
        if operacion == "eliminar":
            if resultado is not None:
                raise ValueError("No se pudo verificar la eliminación.")
        elif resultado is None or any(resultado[k] != v for k, v in nuevo.items()):
            raise ValueError("No se pudo verificar el cambio.")
        return resultado
