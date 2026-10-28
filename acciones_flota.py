"""Propuestas acotadas y confirmaciones de un solo uso; nunca ejecuta código de IA."""
import math
import secrets
import threading
import time

import database
from monitor import normalizar_esperando_viaje, obtener_estado

CAMPOS = ("patente", "velocidad", "minutos_detenido", "esperando_viaje")
PENDIENTES = {}
LOCK = threading.Lock()
TTL = 300
MAX_PENDIENTES = 100


def validar_campos(campos, *, patente_estricta=True):
    if not isinstance(campos, dict) or set(campos) != set(CAMPOS):
        raise ValueError("No se pudieron interpretar los datos. Indicá patente, velocidad, minutos detenido y espera.")
    valores = {k: v for k, v in campos.items() if v is not None}
    if "patente" in valores:
        patente = valores["patente"]
        if (not isinstance(patente, str) or not 3 <= len(patente.strip()) <= 10
                or (patente_estricta and (not patente.strip().isascii() or not patente.strip().isalnum()))):
            raise ValueError("Usá una patente de 3 a 10 letras o números, sin espacios ni símbolos.")
        valores["patente"] = patente.strip().upper()
    if "velocidad" in valores:
        velocidad = valores["velocidad"]
        if type(velocidad) not in (int, float) or not math.isfinite(velocidad) or velocidad < 0:
            raise ValueError("La velocidad debe ser un número finito igual o mayor que 0.")
    if "minutos_detenido" in valores:
        minutos = valores["minutos_detenido"]
        if type(minutos) is not int or not 0 <= minutos <= 9223372036854775807:
            raise ValueError("Los minutos detenido deben ser un entero igual o mayor que 0 dentro del rango admitido.")
    if "esperando_viaje" in valores and type(valores["esperando_viaje"]) is not bool:
        raise ValueError("La espera de viaje debe ser verdadero o falso.")
    return valores


def describir(vehiculo):
    return (f"{vehiculo['patente']}: {vehiculo['velocidad']:g} km/h, "
            f"{vehiculo['minutos_detenido']} min detenido, "
            f"esperando viaje: {'sí' if vehiculo['esperando_viaje'] else 'no'}.")


def construir_cambio(plan, vehiculos, *, patente_estricta=True):
    operacion = plan["operacion"]
    if operacion not in ("agregar", "actualizar", "eliminar"):
        raise ValueError("Operación no permitida.")
    cambios = validar_campos(plan["cambios"], patente_estricta=patente_estricta)
    anterior = None
    if operacion == "agregar":
        if plan["ids"] or plan["patentes"]:
            raise ValueError("Para agregar usá la patente nueva en los datos, sin seleccionar otra unidad.")
        if not all(k in cambios for k in ("patente", "velocidad", "minutos_detenido")):
            raise ValueError("Para agregar indicá patente, velocidad y minutos detenido. Ejemplo: agregá XYZ123 a 0 km/h, detenido 0 minutos, esperando viaje.")
        nuevo = {"esperando_viaje": False, **cambios}
    else:
        if len(plan["ids"]) > 1 or len(plan["patentes"]) > 1 or not (plan["ids"] or plan["patentes"]):
            raise ValueError("Indicá una sola patente o identificador por operación.")
        seleccion = [v for v in vehiculos
                     if (not plan["ids"] or v["id"] == plan["ids"][0])
                     and (not plan["patentes"] or v["patente"].casefold() == plan["patentes"][0].casefold())]
        if len(seleccion) != 1:
            raise ValueError("No existe una unidad que coincida con esa patente o identificador.")
        anterior = {k: seleccion[0][k] for k in ("id", *CAMPOS)}
        if operacion == "eliminar":
            if cambios:
                raise ValueError("Solicitá la eliminación por separado, sin cambios de estado.")
            nuevo = None
        else:
            if not cambios:
                raise ValueError("Indicá qué querés actualizar: patente, velocidad, minutos detenido o espera de viaje.")
            nuevo = {k: anterior[k] for k in CAMPOS} | cambios
    if nuevo is not None:
        nuevo["esperando_viaje"] = normalizar_esperando_viaje(nuevo["velocidad"], nuevo["esperando_viaje"])
        if any(v["patente"].casefold() == nuevo["patente"].casefold()
               and (anterior is None or v["id"] != anterior["id"]) for v in vehiculos):
            raise ValueError("Ya existe un vehículo con esa patente.")
        resumen = ("Agregar: " if anterior is None else f"Actualizar unidad {anterior['id']}.\nAntes: {describir(anterior)}\nDespués: ") + describir(nuevo)
        resumen += "\n" + obtener_estado(nuevo)
    else:
        resumen = f"Eliminar definitivamente la unidad {anterior['id']}.\n{describir(anterior)}"
    return anterior, nuevo, resumen


def preparar(plan, vehiculos):
    anterior, nuevo, resumen = construir_cambio(plan, vehiculos)
    operacion = plan["operacion"]
    with LOCK:
        ahora = time.monotonic()
        for token in list(PENDIENTES):
            if PENDIENTES[token][0] <= ahora:
                del PENDIENTES[token]
        if len(PENDIENTES) >= MAX_PENDIENTES:
            raise ValueError("Hay demasiadas operaciones pendientes. Esperá unos minutos.")
        token = secrets.token_urlsafe(32)
        PENDIENTES[token] = (ahora + TTL, operacion, anterior, nuevo)
    return {"estado": "pendiente_confirmacion",
            "respuesta": resumen + "\nRevisá los datos y confirmá para aplicar. La propuesta vence en 5 minutos.",
            "datos": {"operacion": operacion, "anterior": anterior, "vehiculo": nuevo},
            "propuesta": {"token": token}}


def resolver_datos(token, confirmar):
    if not isinstance(token, str) or type(confirmar) is not bool:
        raise ValueError("Confirmación inválida.")
    with LOCK:
        pendiente = PENDIENTES.pop(token, None)
    if pendiente is None or pendiente[0] <= time.monotonic():
        raise ValueError("La propuesta venció o ya fue procesada. Volvé a solicitar la operación.")
    if not confirmar:
        return {"operacion": pendiente[1], "estado": "cancelado",
                "respuesta": "Operación cancelada. No se modificó la flota.", "datos": {}}
    _, operacion, anterior, nuevo = pendiente
    return {"operacion": operacion, **aplicar(operacion, anterior, nuevo)}


def aplicar(operacion, anterior, nuevo):
    resultado = database.aplicar_cambio_confirmado(operacion, anterior, nuevo)
    if operacion == "eliminar":
        return {"estado": "completado",
                "respuesta": f"Vehículo {anterior['patente']} eliminado. Se verificó que ya no está en la flota.",
                "datos": {"vehiculo_id": anterior["id"], "eliminado": True}}
    return {"estado": "completado",
            "respuesta": (f"Vehículo {'agregado' if operacion == 'agregar' else 'actualizado'} y verificado.\n"
                          f"Unidad {resultado['id']} · {describir(resultado)}\n{obtener_estado(resultado)}"),
            "datos": {"vehiculo": {**resultado, "estado": obtener_estado(resultado)}}}


def ejecutar_autorizado(plan, vehiculos):
    """Entrada de confianza para MCP: el cliente debe comprobar el pedido explícito."""
    anterior, nuevo, _ = construir_cambio(plan, vehiculos, patente_estricta=False)
    return aplicar(plan["operacion"], anterior, nuevo)


def resolver(token, confirmar):
    """Adaptador de texto conservado para consumidores anteriores."""
    return resolver_datos(token, confirmar)["respuesta"]
