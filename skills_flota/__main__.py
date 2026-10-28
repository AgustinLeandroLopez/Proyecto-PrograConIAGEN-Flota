"""Catálogo exportable y demostración offline con una base descartable."""
import argparse
import json
from pathlib import Path
import tempfile

import database
from . import catalogo, confirmar, invocar


def demo():
    """Usa las tres Skills desde otro consumidor, sin HTTP, Gemini ni flota.db."""
    original = database.RUTA_BASE_DATOS
    resultados = []
    with tempfile.TemporaryDirectory() as carpeta:
        try:
            database.RUTA_BASE_DATOS = Path(carpeta) / "demo.db"
            database.inicializar_base_de_datos()
            resultados.append(invocar("consultar_flota", {"operacion": "resumen", "patentes": [], "ids": []}))
            propuesta = invocar("gestionar_vehiculos", {
                "operacion": "agregar", "patentes": [], "ids": [],
                "cambios": {"patente": "DEMO123", "velocidad": 0, "minutos_detenido": 0, "esperando_viaje": True},
            })
            resultados.append(propuesta)
            alta = confirmar(propuesta["propuesta"]["token"], True)
            resultados.append(alta)
            identificador = alta["datos"]["vehiculo"]["id"]
            propuesta = invocar("gestionar_vehiculos", {
                "operacion": "actualizar", "patentes": [], "ids": [identificador],
                "cambios": {"patente": None, "velocidad": 60, "minutos_detenido": 0, "esperando_viaje": None},
            })
            resultados.extend([propuesta, confirmar(propuesta["propuesta"]["token"], True)])
            propuesta = invocar("eliminar_vehiculo", {
                "operacion": "eliminar", "patentes": [], "ids": [identificador],
                "cambios": dict.fromkeys(("patente", "velocidad", "minutos_detenido", "esperando_viaje")),
            })
            resultados.extend([propuesta, confirmar(propuesta["propuesta"]["token"], True)])
            resultados.append(invocar("consultar_flota", {"operacion": "resumen", "patentes": [], "ids": []}))
        finally:
            database.RUTA_BASE_DATOS = original
    return resultados


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accion", choices=("catalogo", "demo"))
    argumentos = parser.parse_args()
    resultado = catalogo() if argumentos.accion == "catalogo" else demo()
    print(json.dumps(resultado, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
