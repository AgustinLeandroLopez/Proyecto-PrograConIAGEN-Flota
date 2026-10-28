"""Contratos JSON Schema y validación del subconjunto usado por las Skills."""
from dataclasses import dataclass
import math
from typing import Callable


SELECCION = {
    "patentes": {"type": "array", "maxItems": 30, "items": {"type": "string", "minLength": 1, "maxLength": 100}},
    "ids": {"type": "array", "maxItems": 30, "items": {"type": "integer", "minimum": 1}},
}
CAMBIOS = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "patente": {"type": ["string", "null"], "minLength": 3, "maxLength": 10},
        "velocidad": {"type": ["number", "null"], "minimum": 0},
        "minutos_detenido": {"type": ["integer", "null"], "minimum": 0, "maximum": 9223372036854775807},
        "esperando_viaje": {"type": ["boolean", "null"]},
    },
    "required": ["patente", "velocidad", "minutos_detenido", "esperando_viaje"],
}
VEHICULO = {
    "type": "object", "additionalProperties": False,
    "required": ["patente", "velocidad", "minutos_detenido", "esperando_viaje"],
    "properties": {
        "id": {"type": "integer", "minimum": 1}, "patente": {"type": "string"},
        "velocidad": {"type": "number", "minimum": 0},
        "minutos_detenido": {"type": "integer", "minimum": 0},
        "esperando_viaje": {"type": "boolean"}, "estado": {"type": "string"},
        "alerta": {"type": "boolean"},
    },
}
RESUMEN = {
    "type": "object", "additionalProperties": False,
    "required": ["total", "en_movimiento", "detenidos", "esperando_viaje", "alertas"],
    "properties": {k: {"type": "integer", "minimum": 0} for k in
                   ("total", "en_movimiento", "detenidos", "esperando_viaje", "alertas")},
}
SALIDA = {
    "type": "object", "additionalProperties": False,
    "required": ["skill", "estado", "respuesta", "datos"],
    "properties": {
        "skill": {"type": "string"},
        "estado": {"type": "string", "enum": ["completado", "pendiente_confirmacion", "cancelado", "error"]},
        "respuesta": {"type": "string"},
        "datos": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "operacion": {"type": "string", "enum": ["agregar", "actualizar", "eliminar"]},
                "anterior": {**VEHICULO, "type": ["object", "null"]},
                "vehiculo": {**VEHICULO, "type": ["object", "null"]},
                "vehiculos": {"type": "array", "items": VEHICULO},
                "resumen": RESUMEN,
                "limite_minutos_detenido": {"type": "integer", "minimum": 0},
                "vehiculo_id": {"type": "integer", "minimum": 1},
                "eliminado": {"type": "boolean"},
            },
        },
        "propuesta": {
            "type": "object", "additionalProperties": False, "required": ["token"],
            "properties": {"token": {"type": "string", "minLength": 20, "maxLength": 100}},
        },
    },
}


def entrada(operaciones, escritura=False):
    propiedades = {"operacion": {"type": "string", "enum": list(operaciones)}, **SELECCION}
    if escritura:
        propiedades["cambios"] = CAMBIOS
    return {"type": "object", "properties": propiedades,
            "required": list(propiedades), "additionalProperties": False}


def validar(valor, esquema, ruta="entrada"):
    """Valida tipos estrictos y restricciones presentes en nuestros contratos.

    Es un validador acotado, no una implementación general de JSON Schema.
    No admite coerción, referencias externas ni carga de código del modelo.
    """
    tipos = esquema.get("type", [])
    tipos = [tipos] if isinstance(tipos, str) else tipos
    def coincide(tipo):
        if tipo == "number":
            try:
                return type(valor) in (int, float) and math.isfinite(valor)
            except OverflowError:
                return False
        return {"object": type(valor) is dict, "array": type(valor) is list,
                "integer": type(valor) is int, "boolean": type(valor) is bool,
                "string": type(valor) is str, "null": valor is None}.get(tipo, False)
    if tipos and not any(coincide(tipo) for tipo in tipos):
        raise ValueError(f"{ruta}: tipo inválido.")
    if "enum" in esquema and valor not in esquema["enum"]:
        raise ValueError(f"{ruta}: opción no permitida.")
    if valor is None:
        return
    if type(valor) is dict:
        propiedades = esquema.get("properties", {})
        if set(esquema.get("required", [])) - set(valor):
            raise ValueError(f"{ruta}: faltan campos obligatorios.")
        if esquema.get("additionalProperties") is False and set(valor) - set(propiedades):
            raise ValueError(f"{ruta}: campos no permitidos.")
        for clave, contenido in valor.items():
            if clave in propiedades:
                validar(contenido, propiedades[clave], f"{ruta}.{clave}")
    elif type(valor) is list:
        if len(valor) > esquema.get("maxItems", float("inf")):
            raise ValueError(f"{ruta}: demasiados elementos.")
        for elemento in valor:
            validar(elemento, esquema.get("items", {}), ruta + "[]")
    elif type(valor) is str:
        if not esquema.get("minLength", 0) <= len(valor) <= esquema.get("maxLength", float("inf")):
            raise ValueError(f"{ruta}: longitud inválida.")
    elif type(valor) in (int, float):
        if not esquema.get("minimum", -float("inf")) <= valor <= esquema.get("maximum", float("inf")):
            raise ValueError(f"{ruta}: valor fuera de rango.")


@dataclass(frozen=True)
class Skill:
    nombre: str
    descripcion: str
    operaciones: tuple[str, ...]
    workflow: tuple[str, ...]
    herramientas: tuple[str, ...]
    input_schema: dict
    ejemplos: tuple[dict, ...]
    ejecutar: Callable
    version: str = "1.0.0"

    def catalogo(self):
        return {"nombre": self.nombre, "version": self.version,
                "descripcion": self.descripcion, "operaciones": list(self.operaciones),
                "workflow": list(self.workflow), "herramientas": list(self.herramientas),
                "input_schema": self.input_schema, "output_schema": SALIDA,
                "ejemplos": list(self.ejemplos)}
