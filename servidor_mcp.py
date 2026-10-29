from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from database import inicializar_base_de_datos
from skills_flota import invocar
from acciones_flota import CAMPOS


mcp = MCPServer(
    "Monitor de flota",
    instructions=(
        "Usa estas herramientas para consultar el estado de la flota local. "
        "Antes de modificar la flota, confirma que el usuario solicito el cambio. "
        "Luego de una modificacion, consulta nuevamente la flota o las alertas para verificarla."
    ),
)

def ejecutar_skill(nombre, argumentos):
    """MCP adapta su contrato público al mismo registro usado por el chatbot."""
    try:
        resultado = invocar(nombre, argumentos, canal="mcp")
    except ValueError as error:
        raise ToolError(str(error)) from None
    if resultado["estado"] == "error":
        raise ToolError(resultado["respuesta"])
    return resultado["datos"]


def consultar(operacion, ids=None):
    return ejecutar_skill("consultar_flota", {
        "operacion": operacion, "patentes": [], "ids": ids or [],
    })["vehiculos"]


@mcp.tool(
    title="Consultar todos los vehiculos",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def consultar_vehiculos() -> list[dict[str, int | float | str | bool]]:
    """Consulta todos los vehiculos de la flota e informa el estado de cada uno."""
    return consultar("vehiculos")


@mcp.tool(
    title="Consultar el estado de un vehiculo",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def consultar_estado_vehiculo(
    vehiculo_id: Annotated[int, Field(gt=0, description="Identificador del vehiculo")],
) -> dict[str, int | float | str | bool]:
    """Consulta un vehiculo por su identificador e informa su estado actual."""
    vehiculos = consultar("vehiculos", [vehiculo_id])
    if not vehiculos:
        raise ToolError(f"No existe un vehiculo con id {vehiculo_id}.")

    return vehiculos[0]


@mcp.tool(
    title="Consultar alertas de la flota",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def consultar_alertas() -> list[dict[str, int | float | str | bool]]:
    """Consulta los vehiculos detenidos durante mas tiempo que el limite permitido."""
    return consultar("alertas")


@mcp.tool(
    title="Agregar un vehiculo a la flota",
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=False,
    ),
)
def agregar_vehiculo(
    patente: Annotated[
        str,
        Field(min_length=3, max_length=10, description="Patente del nuevo vehiculo"),
    ],
    velocidad: Annotated[float, Field(ge=0, description="Velocidad actual en km/h")],
    minutos_detenido: Annotated[
        int,
        Field(ge=0, description="Cantidad de minutos que lleva detenido"),
    ],
    esperando_viaje: Annotated[
        bool,
        Field(description="Indica si esta disponible y esperando la asignacion de un viaje"),
    ] = False,
    zona: Annotated[str, Field(description="Zona ficticia: Centro, Norte, Sur u Oeste")] = "Centro",
    tarifa_base: Annotated[int, Field(ge=1, le=1000000, description="Tarifa base en pesos ficticios")] = 4000,
    precio_minimo: Annotated[int, Field(ge=1, le=1000000, description="Mínimo base, no mayor que tarifa_base")] = 3000,
    en_viaje: Annotated[bool, Field(description="Unidad con un viaje activo, incompatible con esperando_viaje")] = False,
) -> dict[str, int | float | str | bool]:
    """Agrega un vehiculo nuevo a la flota y devuelve su estado inicial."""
    return ejecutar_skill("gestionar_vehiculos", {
        "operacion": "agregar", "patentes": [], "ids": [],
        "cambios": {"patente": patente.strip().upper(), "velocidad": velocidad,
                    "minutos_detenido": minutos_detenido, "esperando_viaje": esperando_viaje,
                    "zona": zona, "tarifa_base": tarifa_base, "precio_minimo": precio_minimo, "en_viaje": en_viaje},
    })["vehiculo"]


@mcp.tool(
    title="Actualizar el estado de un vehiculo",
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
def actualizar_estado_vehiculo(
    vehiculo_id: Annotated[int, Field(gt=0, description="Identificador del vehiculo")],
    velocidad: Annotated[float, Field(ge=0, description="Velocidad actual en km/h")],
    minutos_detenido: Annotated[
        int,
        Field(ge=0, description="Cantidad de minutos que lleva detenido"),
    ],
    esperando_viaje: Annotated[
        bool | None,
        Field(
            description=(
                "Activa o desactiva la espera de viaje. Si se omite, se conserva "
                "el valor actual salvo que el vehiculo pase a estar en movimiento."
            )
        ),
    ] = None,
    zona: Annotated[str | None, Field(description="Zona ficticia; omitida conserva la actual")] = None,
    tarifa_base: Annotated[int | None, Field(ge=1, le=1000000, description="Tarifa base; omitida conserva la actual")] = None,
    precio_minimo: Annotated[int | None, Field(ge=1, le=1000000, description="Mínimo base; omitido conserva el actual")] = None,
    en_viaje: Annotated[bool | None, Field(description="Activa/finaliza un viaje; omitido conserva el actual salvo que vuelva a esperar")] = None,
) -> dict[str, int | float | str | bool]:
    """Actualiza la velocidad y los minutos detenido de un vehiculo existente."""
    return ejecutar_skill("gestionar_vehiculos", {
        "operacion": "actualizar", "patentes": [], "ids": [vehiculo_id],
        "cambios": {"patente": None, "velocidad": velocidad,
                    "minutos_detenido": minutos_detenido, "esperando_viaje": esperando_viaje,
                    "zona": zona, "tarifa_base": tarifa_base, "precio_minimo": precio_minimo, "en_viaje": en_viaje},
    })["vehiculo"]


@mcp.tool(
    title="Eliminar un vehiculo de la flota",
    annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=True, idempotent_hint=True,
        open_world_hint=False,
    ),
)
def eliminar_vehiculo(
    vehiculo_id: Annotated[int, Field(gt=0, description="Identificador del vehiculo a eliminar")],
) -> dict[str, int | bool]:
    """Elimina la unidad solicitada explícitamente y verifica que ya no exista."""
    return ejecutar_skill("eliminar_vehiculo", {
        "operacion": "eliminar", "patentes": [], "ids": [vehiculo_id],
        "cambios": dict.fromkeys(CAMPOS),
    })


if __name__ == "__main__":
    inicializar_base_de_datos()
    mcp.run()
