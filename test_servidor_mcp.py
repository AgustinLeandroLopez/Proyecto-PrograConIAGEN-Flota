import json
import sys
import unittest
from pathlib import Path

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
    async def test_transporte_stdio_publica_las_herramientas(self):
        servidor = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__).with_name("servidor_mcp.py"))],
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
            },
        )

    async def test_consultar_vehiculos(self):
        async with Client(mcp, raise_exceptions=True) as cliente:
            resultado = await cliente.call_tool("consultar_vehiculos", {})

        vehiculos = obtener_resultado_estructurado(resultado)
        self.assertFalse(resultado.is_error)
        ids = {vehiculo["id"] for vehiculo in vehiculos}
        self.assertTrue({1, 2, 3}.issubset(ids))

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
                    },
                )


if __name__ == "__main__":
    unittest.main()
