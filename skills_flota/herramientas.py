"""Herramienta de lectura compartida por Skills, HTTP y MCP."""
from datetime import datetime

import database
from monitor import LIMITE_MINUTOS_DETENIDO, esta_en_alerta, esta_esperando_viaje, obtener_estado


def obtener_snapshot():
    vehiculos = [{**v, "estado": obtener_estado(v), "alerta": esta_en_alerta(v),
                  "esperando_viaje": esta_esperando_viaje(v)} for v in database.consultar_vehiculos()]
    return {
        "actualizado": datetime.now().astimezone().isoformat(timespec="seconds"),
        "limite_minutos_detenido": LIMITE_MINUTOS_DETENIDO,
        "resumen": resumir(vehiculos), "vehiculos": vehiculos,
    }


def resumir(vehiculos):
    return {
        "total": len(vehiculos),
        "en_movimiento": sum(v["velocidad"] > 0 for v in vehiculos),
        "detenidos": sum(v["velocidad"] == 0 and not v["esperando_viaje"] and not v["alerta"] for v in vehiculos),
        "esperando_viaje": sum(v["esperando_viaje"] for v in vehiculos),
        "alertas": sum(v["alerta"] for v in vehiculos),
    }
