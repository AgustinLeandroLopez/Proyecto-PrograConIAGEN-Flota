from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from database import (
    agregar_vehiculo as agregar_vehiculo_en_base,
    actualizar_estado_vehiculo as actualizar_estado_en_base,
    consultar_vehiculo as consultar_vehiculo_en_base,
    consultar_vehiculos as consultar_vehiculos_en_base,
    inicializar_base_de_datos,
)
from monitor import (
    normalizar_esperando_viaje,
    obtener_alertas,
    obtener_estado,
)


mcp = MCPServer(
    "Monitor de flota",
    instructions=(
        "Usa estas herramientas para consultar el estado de la flota local. "
        "Antes de modificar la flota, confirma que el usuario solicito el cambio. "
        "Luego de una modificacion, consulta nuevamente la flota o las alertas para verificarla."
    ),
)

inicializar_base_de_datos()


def agregar_estado(vehiculo) -> dict[str, int | float | str | bool]:
    return {**vehiculo, "estado": obtener_estado(vehiculo)}


@mcp.tool(
    title="Consultar todos los vehiculos",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def consultar_vehiculos() -> list[dict[str, int | float | str | bool]]:
    """Consulta todos los vehiculos de la flota e informa el estado de cada uno."""
    return [agregar_estado(vehiculo) for vehiculo in consultar_vehiculos_en_base()]


@mcp.tool(
    title="Consultar el estado de un vehiculo",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def consultar_estado_vehiculo(
    vehiculo_id: Annotated[int, Field(gt=0, description="Identificador del vehiculo")],
) -> dict[str, int | float | str | bool]:
    """Consulta un vehiculo por su identificador e informa su estado actual."""
    vehiculo = consultar_vehiculo_en_base(vehiculo_id)
    if vehiculo is None:
        raise ToolError(f"No existe un vehiculo con id {vehiculo_id}.")

    return agregar_estado(vehiculo)


@mcp.tool(
    title="Consultar alertas de la flota",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def consultar_alertas() -> list[dict[str, int | float | str | bool]]:
    """Consulta los vehiculos detenidos durante mas tiempo que el limite permitido."""
    vehiculos = consultar_vehiculos_en_base()
    return [agregar_estado(vehiculo) for vehiculo in obtener_alertas(vehiculos)]


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
) -> dict[str, int | float | str | bool]:
    """Agrega un vehiculo nuevo a la flota y devuelve su estado inicial."""
    patente_normalizada = patente.strip().upper()
    if len(patente_normalizada) < 3:
        raise ToolError("La patente debe tener al menos 3 caracteres.")

    esperando_viaje = normalizar_esperando_viaje(velocidad, esperando_viaje)
    vehiculo = agregar_vehiculo_en_base(
        patente_normalizada,
        velocidad,
        minutos_detenido,
        esperando_viaje,
    )
    if vehiculo is None:
        raise ToolError(f"Ya existe un vehiculo con la patente {patente_normalizada}.")

    return agregar_estado(vehiculo)


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
) -> dict[str, int | float | str | bool]:
    """Actualiza la velocidad y los minutos detenido de un vehiculo existente."""
    vehiculo_anterior = consultar_vehiculo_en_base(vehiculo_id)
    if vehiculo_anterior is None:
        raise ToolError(f"No existe un vehiculo con id {vehiculo_id}.")

    if esperando_viaje is None:
        esperando_viaje = vehiculo_anterior["esperando_viaje"]
    esperando_viaje = normalizar_esperando_viaje(velocidad, esperando_viaje)

    actualizado = actualizar_estado_en_base(
        vehiculo_id,
        velocidad,
        minutos_detenido,
        esperando_viaje,
    )
    if not actualizado:
        raise ToolError(f"No existe un vehiculo con id {vehiculo_id}.")

    vehiculo = consultar_vehiculo_en_base(vehiculo_id)
    return agregar_estado(vehiculo)


if __name__ == "__main__":
    mcp.run()
