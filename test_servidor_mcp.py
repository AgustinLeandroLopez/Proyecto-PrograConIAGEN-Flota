import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database
from mcp import Client, StdioServerParameters

from database import conectar
from servidor_mcp import mcp


def obtener_resultado_estructurado(resultado):
    contenido = resultado.structured_content
    if isinstance(contenido, dict) and set(contenido) == {"result"}:
        return contenido["result"]
    if contenido is not None:
        return contenido
    return json.loads(resultado.content[0].text)


class ServidorMCPTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        cambio = patch.object(database, "RUTA_BASE_DATOS", Path(self.temp.name) / "test.db")
        cambio.start()
        self.addCleanup(cambio.stop)
        database.inicializar_base_de_datos()

    async def test_transporte_stdio_publica_las_herramientas(self):
        servidor = StdioServerParameters(
            command=sys.executable,
            args=["-c", (
                "import database, runpy; from pathlib import Path; "
                f"database.RUTA_BASE_DATOS = Path({str(database.RUTA_BASE_DATOS)!r}); "
                f"runpy.run_path({str(Path(__file__).with_name('servidor_mcp.py'))!r}, run_name='__main__')"
            )],
        )

        async with Client(servidor) as cliente:
            resultado = await cliente.list_tools()

        nombres = {herramienta.name for herramienta in resultado.tools}
        self.assertEqual(
            nombres,
            {
                "consultar_vehiculos",
                "consultar_estado_vehiculo",
                "consultar_alertas",
                "agregar_vehiculo",
                "actualizar_estado_vehiculo",
                "eliminar_vehiculo",
            },
        )

    async def test_consultar_vehiculos(self):
        async with Client(mcp, raise_exceptions=True) as cliente:
            resultado = await cliente.call_tool("consultar_vehiculos", {})

        vehiculos = obtener_resultado_estructurado(resultado)
        self.assertFalse(resultado.is_error)
        ids = {vehiculo["id"] for vehiculo in vehiculos}
        self.assertTrue({1, 2, 3}.issubset(ids))

    async def test_eliminar_y_verificar(self):
        async with Client(mcp, raise_exceptions=True) as cliente:
            resultado = await cliente.call_tool("eliminar_vehiculo", {"vehiculo_id": 1})
            self.assertFalse(resultado.is_error)
            self.assertTrue(obtener_resultado_estructurado(resultado)["eliminado"])
            consulta = await cliente.call_tool("consultar_vehiculos", {})
            self.assertNotIn(1, [v["id"] for v in obtener_resultado_estructurado(consulta)])
            resultado = await cliente.call_tool("eliminar_vehiculo", {"vehiculo_id": 1})
            self.assertTrue(resultado.is_error)
        database.inicializar_base_de_datos()
        self.assertIsNone(database.consultar_vehiculo(1))

    async def test_consultar_alertas(self):
        async with Client(mcp, raise_exceptions=True) as cliente:
            resultado = await cliente.call_tool("consultar_alertas", {})

        alertas = obtener_resultado_estructurado(resultado)
        self.assertFalse(resultado.is_error)
        self.assertIn(1, [alerta["id"] for alerta in alertas])

    async def test_agregar_vehiculo(self):
        patente = "MCP999"
        with conectar() as conexion:
            conexion.execute("DELETE FROM vehiculos WHERE patente = ?", (patente,))

        try:
            async with Client(mcp, raise_exceptions=True) as cliente:
                resultado = await cliente.call_tool(
                    "agregar_vehiculo",
                    {
                        "patente": patente.lower(),
                        "velocidad": 35,
                        "minutos_detenido": 0,
                        "esperando_viaje": False,
                    },
                )

            vehiculo = obtener_resultado_estructurado(resultado)
            self.assertFalse(resultado.is_error)
            self.assertEqual(vehiculo["patente"], patente)
            self.assertEqual(vehiculo["velocidad"], 35)
            self.assertIn("movimiento", vehiculo["estado"])
        finally:
            with conectar() as conexion:
                conexion.execute("DELETE FROM vehiculos WHERE patente = ?", (patente,))

    async def test_consultar_vehiculo_inexistente(self):
        async with Client(mcp, raise_exceptions=True) as cliente:
            resultado = await cliente.call_tool(
                "consultar_estado_vehiculo",
                {"vehiculo_id": 999},
            )

        self.assertTrue(resultado.is_error)
        self.assertIn("No existe un vehiculo", resultado.content[0].text)

    async def test_actualizar_y_restaurar_estado(self):
        async with Client(mcp, raise_exceptions=True) as cliente:
            estado_anterior = await cliente.call_tool(
                "consultar_estado_vehiculo",
                {"vehiculo_id": 2},
            )
            self.assertFalse(estado_anterior.is_error, estado_anterior.content[0].text)
            vehiculo_anterior = obtener_resultado_estructurado(estado_anterior)

            try:
                resultado = await cliente.call_tool(
                    "actualizar_estado_vehiculo",
                    {
                        "vehiculo_id": 2,
                        "velocidad": 25,
                        "minutos_detenido": 0,
                        "esperando_viaje": False,
                    },
                )
                vehiculo_actualizado = obtener_resultado_estructurado(resultado)

                self.assertFalse(resultado.is_error)
                self.assertEqual(vehiculo_actualizado["velocidad"], 25)
                self.assertIn("movimiento", vehiculo_actualizado["estado"])
            finally:
                await cliente.call_tool(
                    "actualizar_estado_vehiculo",
                    {
                        "vehiculo_id": 2,
                        "velocidad": vehiculo_anterior["velocidad"],
                        "minutos_detenido": vehiculo_anterior["minutos_detenido"],
                        "esperando_viaje": vehiculo_anterior["esperando_viaje"],
                    },
                )

    async def test_esperando_viaje_no_genera_alertas_y_vuelve_a_reglas_normales(self):
        async with Client(mcp, raise_exceptions=True) as cliente:
            estado_anterior = await cliente.call_tool(
                "consultar_estado_vehiculo",
                {"vehiculo_id": 2},
            )
            vehiculo_anterior = obtener_resultado_estructurado(estado_anterior)

            try:
                esperando_menos_de_30 = await cliente.call_tool(
                    "actualizar_estado_vehiculo",
                    {
                        "vehiculo_id": 2,
                        "velocidad": 0,
                        "minutos_detenido": 15,
                        "esperando_viaje": True,
                    },
                )
                vehiculo = obtener_resultado_estructurado(esperando_menos_de_30)
                self.assertTrue(vehiculo["esperando_viaje"])
                self.assertIn("esperando viaje", vehiculo["estado"])

                esperando_mas_de_30 = await cliente.call_tool(
                    "actualizar_estado_vehiculo",
                    {
                        "vehiculo_id": 2,
                        "velocidad": 0,
                        "minutos_detenido": 45,
                        "esperando_viaje": True,
                    },
                )
                vehiculo = obtener_resultado_estructurado(esperando_mas_de_30)
                self.assertTrue(vehiculo["esperando_viaje"])
                self.assertIn("esperando viaje", vehiculo["estado"])

                alertas = await cliente.call_tool("consultar_alertas", {})
                self.assertNotIn(
                    2,
                    [alerta["id"] for alerta in obtener_resultado_estructurado(alertas)],
                )

                fuera_de_espera = await cliente.call_tool(
                    "actualizar_estado_vehiculo",
                    {
                        "vehiculo_id": 2,
                        "velocidad": 0,
                        "minutos_detenido": 45,
                        "esperando_viaje": False,
                    },
                )
                vehiculo = obtener_resultado_estructurado(fuera_de_espera)
                self.assertFalse(vehiculo["esperando_viaje"])
                self.assertIn("ALERTA", vehiculo["estado"])
            finally:
                await cliente.call_tool(
                    "actualizar_estado_vehiculo",
                    {
                        "vehiculo_id": 2,
                        "velocidad": vehiculo_anterior["velocidad"],
                        "minutos_detenido": vehiculo_anterior["minutos_detenido"],
                        "esperando_viaje": vehiculo_anterior["esperando_viaje"],
                    },
                )

    async def test_velocidad_positiva_desactiva_esperando_viaje(self):
        async with Client(mcp, raise_exceptions=True) as cliente:
            estado_anterior = await cliente.call_tool(
                "consultar_estado_vehiculo",
                {"vehiculo_id": 2},
            )
            vehiculo_anterior = obtener_resultado_estructurado(estado_anterior)

            try:
                resultado = await cliente.call_tool(
                    "actualizar_estado_vehiculo",
                    {
                        "vehiculo_id": 2,
                        "velocidad": 20,
                        "minutos_detenido": 0,
                        "esperando_viaje": True,
                    },
                )
                vehiculo = obtener_resultado_estructurado(resultado)
                self.assertFalse(vehiculo["esperando_viaje"])
                self.assertIn("movimiento", vehiculo["estado"])
            finally:
                await cliente.call_tool(
                    "actualizar_estado_vehiculo",
                    {
                        "vehiculo_id": 2,
                        "velocidad": vehiculo_anterior["velocidad"],
                        "minutos_detenido": vehiculo_anterior["minutos_detenido"],
                        "esperando_viaje": vehiculo_anterior["esperando_viaje"],
                    },
                )

    async def test_agregar_vehiculo_esperando_viaje(self):
        patente = "MCP888"
        with conectar() as conexion:
            conexion.execute("DELETE FROM vehiculos WHERE patente = ?", (patente,))

        try:
            async with Client(mcp, raise_exceptions=True) as cliente:
                resultado = await cliente.call_tool(
                    "agregar_vehiculo",
                    {
                        "patente": patente,
                        "velocidad": 0,
                        "minutos_detenido": 45,
                        "esperando_viaje": True,
                    },
                )

            vehiculo = obtener_resultado_estructurado(resultado)
            self.assertTrue(vehiculo["esperando_viaje"])
            self.assertIn("esperando viaje", vehiculo["estado"])
        finally:
            with conectar() as conexion:
                conexion.execute("DELETE FROM vehiculos WHERE patente = ?", (patente,))


class MigracionBaseDeDatosTest(unittest.TestCase):
    def test_migra_base_existente_sin_perder_vehiculos(self):
        ruta_original = database.RUTA_BASE_DATOS
        with tempfile.TemporaryDirectory() as directorio_temporal:
            ruta_prueba = Path(directorio_temporal) / "flota_antigua.db"
            conexion = sqlite3.connect(ruta_prueba)
            conexion.execute(
                """
                CREATE TABLE vehiculos (
                    id INTEGER PRIMARY KEY,
                    patente TEXT NOT NULL UNIQUE,
                    velocidad REAL NOT NULL CHECK (velocidad >= 0),
                    minutos_detenido INTEGER NOT NULL CHECK (minutos_detenido >= 0)
                )
                """
            )
            conexion.execute(
                """
                INSERT INTO vehiculos (id, patente, velocidad, minutos_detenido)
                VALUES (99, 'MIG999', 0, 45)
                """
            )
            conexion.commit()
            conexion.close()

            try:
                database.RUTA_BASE_DATOS = ruta_prueba
                database.inicializar_base_de_datos()
                vehiculo = database.consultar_vehiculo(99)
                self.assertEqual(vehiculo["patente"], "MIG999")
                self.assertEqual(vehiculo["velocidad"], 0)
                self.assertEqual(vehiculo["minutos_detenido"], 45)
                self.assertFalse(vehiculo["esperando_viaje"])

                database.inicializar_base_de_datos()
                self.assertEqual(database.consultar_vehiculo(99)["patente"], "MIG999")
            finally:
                database.RUTA_BASE_DATOS = ruta_original


if __name__ == "__main__":
    unittest.main()
