# Skills del monitor de flota

Paquete Python de capacidades reutilizables. Cada módulo contiene un objeto
`SKILL` con nombre, versión, propósito, operaciones, contrato de entrada,
workflow, herramientas, ejemplos y función de ejecución. El contrato de salida
compartido se publica junto a cada definición.

| Skill | Módulo | Operaciones |
| --- | --- | --- |
| `consultar_flota` | `consultar.py` | Resumen, alertas, disponibilidad, unidades y reglas |
| `gestionar_vehiculos` | `gestionar.py` | Agregar y actualizar una unidad |
| `eliminar_vehiculo` | `eliminar.py` | Dar de baja una unidad |

## Uso desde Python

Desde la raíz del repositorio, con la base inicializada:

```python
from skills_flota import catalogo, invocar, confirmar

habilidades = catalogo()
resultado = invocar("consultar_flota", {
    "operacion": "alertas", "patentes": [], "ids": [],
})
print(resultado["skill"], resultado["estado"], resultado["datos"])

propuesta = invocar("gestionar_vehiculos", {
    "operacion": "actualizar", "patentes": ["ABC123"], "ids": [],
    "cambios": {
        "patente": None, "velocidad": 0,
        "minutos_detenido": None, "esperando_viaje": True,
    },
})
print(propuesta["respuesta"])
# Después de revisar y recibir la decisión del operador:
# resultado = confirmar(propuesta["propuesta"]["token"], True)
```

Las invocaciones Python usan por defecto el mismo modo de propuesta del chat.
`canal="mcp"` se reserva al adaptador de confianza que ejecuta el pedido explícito
del cliente MCP. El modelo y el navegador no pueden seleccionar ese canal.

## Contratos y resultados

`catalogo()` devuelve un catálogo JSON serializable con `input_schema` y
`output_schema`. Los tipos son estrictos: por ejemplo, `true` no es un
identificador entero y `"60"` no es una velocidad numérica. Se rechazan campos
extra, operaciones incompatibles y números no finitos. Las reglas de negocio
completan la validación de selección, unicidad y coherencia de la unidad.

Toda ejecución válida devuelve:

```json
{
  "skill": "consultar_flota",
  "estado": "completado",
  "respuesta": "Texto producido por Python a partir de datos actuales.",
  "datos": {
    "vehiculos": [],
    "resumen": {
      "total": 0, "en_movimiento": 0, "detenidos": 0,
      "esperando_viaje": 0, "alertas": 0
    },
    "limite_minutos_detenido": 30
  }
}
```

Los estados posibles son `completado`, `pendiente_confirmacion`, `cancelado` y
`error`. Una propuesta añade `propuesta.token` y datos de la unidad revisada.
Una operación con datos insuficientes devuelve `error` sin escribir. Las
invocaciones con contratos inválidos y las confirmaciones inválidas levantan
`ValueError`; los adaptadores HTTP/MCP lo convierten en sus errores públicos.
Los errores inesperados de infraestructura se manejan en el adaptador.

`contratos.validar` implementa solo los tipos y restricciones usados por estos
contratos: objetos, arrays, tipos escalares/null, enum, required,
additionalProperties, longitudes, cantidad máxima y límites numéricos. No es un
validador general de JSON Schema. Las salidas también se validan antes de devolverlas.

## Demostración sin credenciales

```powershell
python -m skills_flota catalogo
python -m skills_flota demo
```

La primera orden exporta las definiciones. La segunda usa las tres habilidades
para consultar, agregar, actualizar y eliminar `DEMO123` en una base temporal.
Procesa confirmaciones de prueba de forma explícita y devuelve resultados JSON.
No hace llamadas a Gemini ni modifica `flota.db`.

El paquete depende de `database.py`, `monitor.py` y `acciones_flota.py` del
proyecto. Se reutiliza entre consumidores de este repositorio; no es una
distribución independiente instalada en PyPI.

Ver [la guía de la entrega](../docs/SKILLS.md) para la relación con la consigna,
el flujo del agente y los casos de demostración.
