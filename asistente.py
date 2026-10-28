"""Consultas de flota y propuestas de escritura validadas en Python."""
import json

from gemini_client import interpretar
from prompt_agente import OPERACIONES
from errores_asistente import ErrorAsistente
from ollama_client import interpretar as interpretar_local
from acciones_flota import validar_campos
from skills_flota import confirmar, invocar, skill_para_operacion, validar_invocacion

FUERA_DE_ALCANCE = "Solo puedo ayudarte con el monitor de flota. Podés consultarme por vehículos, estados y alertas"
PEDIR_DETALLES = "Podés agregar, actualizar o eliminar un vehículo por vez. Indicá la operación, la patente o identificador y los datos que querés cambiar."
MAX_MENSAJE = 1000
MAX_HISTORIAL = 4
MAX_CONTEXTO = 60000
MAX_RESPUESTA = 6000


def validar_entrada(body):
    if not isinstance(body, dict):
        raise ValueError("La consulta debe ser un objeto JSON.")
    if "confirmacion" in body:
        if (set(body) != {"confirmacion", "confirmar"}
                or not isinstance(body["confirmacion"], str)
                or not 20 <= len(body["confirmacion"]) <= 100
                or type(body["confirmar"]) is not bool):
            raise ValueError("Confirmación inválida.")
        return None, []
    if set(body) - {"mensaje", "historial", "proveedor"}:
        raise ValueError("Campos no admitidos.")
    if body.get("proveedor", "nube") not in ("nube", "local"):
        raise ValueError("Proveedor no permitido.")
    mensaje, historial = body.get("mensaje"), body.get("historial", [])
    if not isinstance(mensaje, str) or not 1 <= len(mensaje.strip()) <= MAX_MENSAJE:
        raise ValueError("Escribí una consulta de entre 1 y 1000 caracteres.")
    if (not isinstance(historial, list) or len(historial) > MAX_HISTORIAL
            or any(not isinstance(m, str) or not 1 <= len(m) <= MAX_MENSAJE for m in historial)):
        raise ValueError("El historial admite hasta cuatro consultas de 1000 caracteres.")
    return mensaje.strip(), historial


def validar_alcance(plan):
    # Lista cerrada de operaciones: jamás se muestra prosa generada por Gemini.
    if (not isinstance(plan, dict)
            or set(plan) != {"skill", "operacion", "patentes", "ids", "pide_modificar", "cambios"}
            or plan["operacion"] not in OPERACIONES
            or type(plan["pide_modificar"]) is not bool
            or not isinstance(plan["patentes"], list) or len(plan["patentes"]) > 30
            or any(not isinstance(p, str) or not 1 <= len(p) <= 100 for p in plan["patentes"])
            or not isinstance(plan["ids"], list) or len(plan["ids"]) > 30
            or any(type(i) is not int or i < 1 for i in plan["ids"])):
        raise ErrorAsistente("No se pudo validar el alcance de la consulta. Probá con vehículos, estados o alertas.")
    try:
        cambios = validar_campos(plan["cambios"])
        escritura = plan["operacion"] in ("agregar", "actualizar", "eliminar")
        if escritura and not plan["pide_modificar"]:
            raise ValueError("No se identificó un pedido explícito de modificación.")
        if not escritura and cambios:
            raise ValueError("Una consulta de lectura no puede incluir cambios.")
    except ValueError as error:
        raise ErrorAsistente(str(error)) from None
    try:
        esperada = skill_para_operacion(plan["operacion"])
        if plan["skill"] != esperada:
            raise ValueError("La Skill no corresponde a la operacion solicitada.")
        if esperada != "ninguna":
            validar_invocacion(esperada, argumentos_skill(plan))
    except ValueError as error:
        raise ErrorAsistente(str(error)) from None
    return plan


def responder(body, obtener_snapshot):
    mensaje, historial = validar_entrada(body)
    if "confirmacion" in body:
        return confirmar(body["confirmacion"], body["confirmar"])["respuesta"]
    try:
        snapshot = obtener_snapshot()  # Nueva lectura por consulta, sin usar estado del chat.
    except Exception:
        raise ErrorAsistente("No se pudo consultar la flota actual. No hay resultados disponibles.") from None
    contexto = {"vehiculos": snapshot["vehiculos"], "resumen": snapshot["resumen"],
                "reglas": {"limite_minutos_detenido": snapshot["limite_minutos_detenido"],
                           "alerta": "velocidad 0 y minutos > límite, excepto esperando viaje",
                           "espera": "solo detenido; velocidad positiva desactiva espera"}}
    if len(json.dumps(contexto, ensure_ascii=False)) > MAX_CONTEXTO:
        raise ErrorAsistente("La flota supera el tamaño admitido por esta versión del asistente.")
    interpretar_pedido = interpretar_local if body.get("proveedor", "nube") == "local" else interpretar
    plan = validar_alcance(interpretar_pedido(mensaje, historial, contexto))
    operacion = plan["operacion"]
    if operacion == "fuera_de_alcance":
        return FUERA_DE_ALCANCE
    if operacion == "modificacion":
        return PEDIR_DETALLES
    resultado = invocar(plan["skill"], argumentos_skill(plan))
    if resultado["estado"] == "pendiente_confirmacion":
        return resultado
    aviso = PEDIR_DETALLES + "\n\n" if plan["pide_modificar"] and operacion not in ("agregar", "actualizar", "eliminar") else ""
    return aviso + resultado["respuesta"]


def argumentos_skill(plan):
    argumentos = {k: plan[k] for k in ("operacion", "patentes", "ids")}
    if plan["operacion"] in ("agregar", "actualizar", "eliminar"):
        argumentos["cambios"] = plan["cambios"]
    return argumentos
