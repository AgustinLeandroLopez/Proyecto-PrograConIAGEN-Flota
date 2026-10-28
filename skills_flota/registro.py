"""Registro cerrado de habilidades; no carga nombres ni código del modelo."""
from copy import deepcopy

import acciones_flota
from .contratos import SALIDA, validar
from .consultar import SKILL as CONSULTAR
from .gestionar import SKILL as GESTIONAR
from .eliminar import SKILL as ELIMINAR

_SKILLS = {s.nombre: s for s in (CONSULTAR, GESTIONAR, ELIMINAR)}
_POR_OPERACION = {op: s.nombre for s in _SKILLS.values() for op in s.operaciones}


def catalogo():
    """Metadatos y contratos exportables sin referencias mutables al registro."""
    return deepcopy([s.catalogo() for s in _SKILLS.values()])


def skill_para_operacion(operacion):
    return _POR_OPERACION.get(operacion, "ninguna") if isinstance(operacion, str) else "ninguna"


def operaciones():
    return tuple(_POR_OPERACION)


def validar_invocacion(nombre, argumentos):
    if not isinstance(nombre, str) or nombre not in _SKILLS:
        raise ValueError("Skill no permitida.")
    validar(argumentos, _SKILLS[nombre].input_schema)


def _validar_resultado(nombre, resultado):
    salida = {"skill": nombre, **resultado}
    validar(salida, SALIDA, "salida")
    if salida["skill"] != nombre:
        raise ValueError("La salida corresponde a otra Skill.")
    if (salida["estado"] == "pendiente_confirmacion") != ("propuesta" in salida):
        raise ValueError("Resultado de Skill inconsistente.")
    return deepcopy(salida)


def invocar(nombre, argumentos, *, canal="chat"):
    """El canal es contexto de confianza del adaptador, nunca un argumento del LLM.

    Una invocación Python usa por defecto las mismas propuestas que el chat.
    El adaptador MCP permite ejecutar el pedido ya autorizado por su cliente.
    """
    if canal not in ("chat", "mcp"):
        raise ValueError("Canal no permitido.")
    validar_invocacion(nombre, argumentos)
    try:
        resultado = _SKILLS[nombre].ejecutar(deepcopy(argumentos), canal)
    except ValueError as error:
        resultado = {"estado": "error", "respuesta": str(error), "datos": {}}
    return _validar_resultado(nombre, resultado)


def confirmar(token, aceptar):
    resultado = acciones_flota.resolver_datos(token, aceptar)
    nombre = skill_para_operacion(resultado.pop("operacion"))
    return _validar_resultado(nombre, resultado)
