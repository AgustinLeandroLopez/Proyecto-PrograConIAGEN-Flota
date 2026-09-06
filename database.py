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
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS vehiculos (
                id INTEGER PRIMARY KEY,
                patente TEXT NOT NULL UNIQUE,
                velocidad REAL NOT NULL CHECK (velocidad >= 0),
                minutos_detenido INTEGER NOT NULL CHECK (minutos_detenido >= 0)
            )
            """
        )
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
            SELECT id, patente, velocidad, minutos_detenido
            FROM vehiculos
            ORDER BY id
            """
        ).fetchall()

    return [dict(fila) for fila in filas]


def consultar_vehiculo(vehiculo_id):
    with conectar() as conexion:
        fila = conexion.execute(
            """
            SELECT id, patente, velocidad, minutos_detenido
            FROM vehiculos
            WHERE id = ?
            """,
            (vehiculo_id,),
        ).fetchone()

    return dict(fila) if fila else None


def actualizar_estado_vehiculo(vehiculo_id, velocidad, minutos_detenido):
    with conectar() as conexion:
        cursor = conexion.execute(
            """
            UPDATE vehiculos
            SET velocidad = ?, minutos_detenido = ?
            WHERE id = ?
            """,
            (velocidad, minutos_detenido, vehiculo_id),
        )

    return cursor.rowcount > 0


def agregar_vehiculo(patente, velocidad, minutos_detenido):
    with conectar() as conexion:
        try:
            cursor = conexion.execute(
                """
                INSERT INTO vehiculos (patente, velocidad, minutos_detenido)
                VALUES (?, ?, ?)
                """,
                (patente, velocidad, minutos_detenido),
            )
        except sqlite3.IntegrityError:
            return None

        vehiculo_id = cursor.lastrowid

    return consultar_vehiculo(vehiculo_id)
