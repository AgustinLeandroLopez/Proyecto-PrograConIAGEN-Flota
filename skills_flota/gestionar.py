"""Skill de altas y actualizaciones con confirmación del chat."""
import acciones_flota
from .contratos import Skill, entrada
from .herramientas import obtener_snapshot

OPERACIONES = ("agregar", "actualizar")


def ejecutar(argumentos, canal):
    vehiculos = obtener_snapshot()["vehiculos"]
    if canal == "mcp":
        return acciones_flota.ejecutar_autorizado(argumentos, vehiculos)
    return acciones_flota.preparar(argumentos, vehiculos)


SKILL = Skill(
    nombre="gestionar_vehiculos", descripcion="Agregar una unidad o actualizar patente, velocidad, minutos detenido o espera.",
    operaciones=OPERACIONES,
    workflow=("Extraer solo campos explícitos del mensaje actual; usar null para campos omitidos.",
              "Para agregar dejar patentes e ids vacíos; poner la patente nueva en cambios.patente. Exigir velocidad y minutos.",
              "Para actualizar seleccionar una unidad por patente o id; cambios.patente solo contiene una nueva patente.",
              "Interpretar 'detenelo' como velocidad 0; 'esperando viaje' como velocidad 0 y esperando_viaje true. No inventar minutos.",
              "Conservar campos omitidos y desactivar espera con velocidad positiva. Validar patente única y valores no negativos.",
              "En el chat devolver una propuesta; solo una confirmación válida aplica y verifica el cambio transaccionalmente.",
              "En MCP ejecutar únicamente ante el pedido explícito verificado por el cliente; compartir las mismas operaciones Python."),
    herramientas=("skills_flota.herramientas.obtener_snapshot", "acciones_flota.preparar", "database.aplicar_cambio_confirmado"),
    input_schema=entrada(OPERACIONES, escritura=True),
    ejemplos=({"operacion": "agregar", "patentes": [], "ids": [],
               "cambios": {"patente": "DEMO123", "velocidad": 0, "minutos_detenido": 0, "esperando_viaje": True}},),
    ejecutar=ejecutar,
)
