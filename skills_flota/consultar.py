"""Skill de consultas: contrato, procedimiento y ejecución reutilizable."""
from .contratos import Skill, entrada
from .herramientas import obtener_snapshot, resumir

OPERACIONES = ("resumen", "alertas", "esperando", "movimiento", "detenidos", "vehiculos", "reglas", "sin_datos", "viajes")
MAX_RESPUESTA = 6000


def ejecutar(argumentos, canal):
    snapshot = obtener_snapshot()
    operacion = argumentos["operacion"]
    vehiculos = snapshot["vehiculos"]
    patentes, ids = argumentos["patentes"], argumentos["ids"]
    aviso = ""
    if patentes or ids:
        buscadas = {p.casefold() for p in patentes}
        vehiculos = [v for v in vehiculos if v["patente"].casefold() in buscadas or v["id"] in ids]
        if buscadas - {v["patente"].casefold() for v in vehiculos} or set(ids) - {v["id"] for v in vehiculos}:
            aviso = "Alguna de las unidades solicitadas no está registrada.\n"
    resumen = resumir(vehiculos)
    filtros = {"alertas": lambda v: v["alerta"], "esperando": lambda v: v["esperando_viaje"],
               "viajes": lambda v: v.get("en_viaje", False),
               "movimiento": lambda v: v["velocidad"] > 0,
               "detenidos": lambda v: v["velocidad"] == 0 and not v["alerta"] and not v["esperando_viaje"]}
    elegidos = [v for v in vehiculos if filtros.get(operacion, lambda v: True)(v)]
    if operacion == "sin_datos":
        texto = "El monitor dispone del estado actual, si está en viaje, zona y tarifas base; no tiene ubicaciones reales (GPS), detalles históricos de viajes, causas de detención ni historial."
    elif operacion == "reglas":
        texto = (f"Hay alerta con velocidad 0 y más de {snapshot['limite_minutos_detenido']} minutos detenido, excepto si espera viaje. "
                 "Esperando viaje implica velocidad 0 y no genera alerta. Al moverse deja de esperar viaje. "
                 "En viaje indica una unidad asignada; no está disponible. Volver a esperar finaliza esa asignación. "
                 "La patente es única; velocidad y minutos detenido no pueden ser negativos.")
    elif operacion == "resumen":
        texto = (f"Flota actual: {resumen['total']} vehículos; {resumen['en_movimiento']} en movimiento, "
                 f"{resumen['detenidos']} detenidos, {resumen['esperando_viaje']} esperando viaje y {resumen['alertas']} en alerta.")
    elif not elegidos:
        texto = "No hay vehículos registrados que coincidan con la consulta actual."
    else:
        texto = "Estado actual:\n"
        for indice, v in enumerate(elegidos):
            linea = (f"{v['patente']} (unidad {v['id']}): {v['velocidad']:g} km/h, "
                     f"{v['minutos_detenido']} min detenido. {v['estado']}. "
                     f"Zona ficticia: {v['zona']}; tarifa base: ${v['tarifa_base']}; mínimo base: ${v['precio_minimo']}\n")
            if len(aviso) + len(texto) + len(linea) > MAX_RESPUESTA - 100:
                texto += f"Quedan {len(elegidos) - indice} unidades sin mostrar. Consultá por una unidad específica."
                break
            texto += linea
    return {"estado": "completado", "respuesta": (aviso + texto).rstrip(),
            "datos": {"vehiculos": elegidos, "resumen": resumen,
                      "limite_minutos_detenido": snapshot["limite_minutos_detenido"]}}


SKILL = Skill(
    nombre="consultar_flota", descripcion="Consultar estados actuales, alertas, disponibilidad y reglas de la flota.",
    operaciones=OPERACIONES,
    workflow=("Leer la flota actual mediante obtener_snapshot; el historial no prueba estados.",
              "Extraer solo patentes o identificadores pedidos y aplicar el filtro de consulta.",
              "Calcular estados y resumen con las reglas de monitor.py; no modificar datos.",
              "Devolver JSON estructurado y texto basado en los datos; informar unidades o información ausentes."),
    herramientas=("skills_flota.herramientas.obtener_snapshot", "monitor.obtener_estado", "monitor.esta_en_alerta"),
    input_schema=entrada(OPERACIONES),
    ejemplos=({"operacion": "alertas", "patentes": [], "ids": []},), ejecutar=ejecutar,
)
