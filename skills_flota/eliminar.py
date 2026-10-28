"""Skill de baja de una unidad identificada de forma inequívoca."""
from .contratos import Skill, entrada
from .gestionar import ejecutar

OPERACIONES = ("eliminar",)

SKILL = Skill(
    nombre="eliminar_vehiculo", descripcion="Dar de baja una unidad y verificar que ya no figure en la flota.",
    operaciones=OPERACIONES,
    workflow=("Interpretar borrar, quitar o dar de baja una unidad como eliminar.",
              "Seleccionar una sola unidad por patente o identificador; todos los campos de cambios deben ser null.",
              "Leer y mostrar la unidad exacta que se eliminará; rechazar selecciones ambiguas o inexistentes.",
              "En el chat esperar confirmación de un solo uso, con vencimiento de cinco minutos; cancelar no escribe.",
              "Al confirmar comparar el estado revisado, eliminar y comprobar ausencia dentro de la transacción.",
              "En MCP exigir pedido explícito verificado por el cliente antes de invocar la baja."),
    herramientas=("skills_flota.herramientas.obtener_snapshot", "acciones_flota.preparar", "database.aplicar_cambio_confirmado"),
    input_schema=entrada(OPERACIONES, escritura=True),
    ejemplos=({"operacion": "eliminar", "patentes": ["DEMO123"], "ids": [],
               "cambios": {"patente": None, "velocidad": None, "minutos_detenido": None, "esperando_viaje": None}},),
    ejecutar=ejecutar,
)
