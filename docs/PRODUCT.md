# Monitor de flota

## Propósito

El proyecto demuestra cómo un agente de programación puede analizar, refactorizar y ampliar una aplicación, y luego interactuar con ella mediante un servidor MCP propio. El resultado permite consultar y modificar una flota local mientras un dashboard refleja los cambios automáticamente.

## Problema

Un operador necesita conocer rápidamente qué vehículos están en movimiento, cuáles están detenidos y cuáles requieren atención por permanecer detenidos demasiado tiempo.

## Usuario principal

El usuario principal es un operador o responsable de una flota pequeña que consulta el estado general y revisa alertas.

## Reglas del producto

- Un vehículo tiene identificador numérico, patente única, velocidad, minutos detenido y la condición persistente `esperando_viaje`.
- Si la velocidad es mayor que 0, el vehículo está en movimiento.
- Si está detenido y `esperando_viaje` está activo, está disponible para recibir una asignación y no genera alerta, sin importar sus minutos detenido.
- Si la velocidad es 0 y lleva hasta 30 minutos detenido, está detenido dentro del tiempo permitido.
- Si la velocidad es 0 y lleva más de 30 minutos detenido, está en alerta.
- La velocidad y los minutos detenido deben ser valores iguales o mayores que 0.
- Un vehículo que pasa a tener velocidad mayor que 0 deja automáticamente de esperar viaje.

## Flujo principal

```text
Usuario
  -> Codex en el editor
  -> servidor MCP monitor_flota
  -> herramientas MCP
  -> SQLite
  -> dashboard y respuesta del agente
```

Codex decide qué herramienta utilizar según el pedido. Las herramientas controlan el acceso a SQLite y el dashboard consulta la misma base cada dos segundos.

El agente del dashboard usa el flujo `mensaje -> modelo seleccionado con catálogo de Skills -> validación -> registro de Skills -> herramientas Python -> SQLite`. Se puede elegir Gemini en la nube u Ollama local con `gemma3:4b`. Las tres habilidades empaquetadas son `consultar_flota`, `gestionar_vehiculos` y `eliminar_vehiculo`. Cada una declara propósito, versión, input/output schema, workflow, herramientas y ejemplos. Las descripciones y workflows se envían al modelo y Python invoca la habilidad elegida tras comprobar la compatibilidad con la operación. MCP utiliza el mismo registro mediante adaptadores, sin depender del chatbot. Ver `docs/SKILLS.md`.

## Capacidades MCP

- `consultar_vehiculos`: devuelve toda la flota con su estado calculado y la condición de espera de viaje.
- `consultar_estado_vehiculo`: devuelve un vehículo por identificador.
- `consultar_alertas`: devuelve los vehículos que superan el límite permitido.
- `agregar_vehiculo`: registra un vehículo con una patente que no exista e indica opcionalmente si espera viaje.
- `actualizar_estado_vehiculo`: modifica velocidad, minutos detenido y la condición de espera de viaje de un vehículo existente.
- `eliminar_vehiculo`: elimina una unidad por identificador y verifica su ausencia.

## Dashboard

La tabla del dashboard es una vista local de la flota. Presenta cinco indicadores operativos y una tabla con búsqueda por patente, filtros por estado y ordenamiento. En móviles, las filas se presentan como tarjetas. La navegación permite consultar la flota, las alertas y la actividad observada durante la sesión.

El asistente permite consultar, agregar, actualizar y eliminar una unidad por operación. El modelo seleccionado interpreta el pedido; Python valida una lista cerrada de operaciones y prepara una propuesta con los datos concretos. El operador debe usar Confirmar cambio o Cancelar. Las propuestas vencen en cinco minutos, se procesan una sola vez y se pierden al reiniciar el servidor. Una confirmación no vuelve a consultar a ningún modelo. Si la unidad cambió desde la propuesta, no se sobrescribe: se solicita una nueva operación. Las escrituras y su verificación son transaccionales.

Fleet AI se abre desde una mascota SVG flotante o el acceso superior, en un panel superpuesto que conserva el espacio de la tabla. Ofrece sugerencias de consulta, avatares y estados de procesamiento; respeta movimiento reducido y permite cerrar con Escape. No afirma disponibilidad del modelo sin verificarla. La sugerencia de reporte devuelve un resumen actual en el chat, sin exportación; la de historial consulta su disponibilidad, ya que no se almacena historia de vehículos.

El selector del chat ofrece Asistente IA en la nube y Asistente IA local. Ambos usan las mismas Skills y reglas. Las conversaciones e historiales se mantienen separados por modo; la opción inicial es nube. Local usa exclusivamente Ollama en `127.0.0.1:11434` con el modelo instalado `gemma3:4b`, sin clave, proxies ni redirecciones. No hay cambio automático de proveedor ante errores. El modelo local tiene un plazo de 120 segundos para responder y un límite de prompt de 14000 bytes UTF-8 incluidos los ejemplos; la UI espera hasta 150 segundos. Durante una solicitud el selector queda bloqueado. El primer arranque puede demorar por la carga del modelo.

Las actualizaciones admiten patente, velocidad, minutos detenido y espera de viaje, conservando los campos no indicados. Las altas requieren patente, velocidad y minutos detenido; la espera es opcional. Las patentes introducidas por el asistente deben contener de 3 a 10 letras o números. Los datos de ejemplo solo se insertan cuando se crea la tabla, para que las bajas no reaparezcan al reiniciar. Los temas ajenos al trabajo de flota, como el clima y los resultados deportivos, se rechazan; las preguntas mixtas solo atienden la parte de flota.

Cuando detecta incorporaciones o actualizaciones mientras está abierto, resalta durante 10 segundos los vehículos afectados y conserva hasta 50 eventos en memoria. La hora de cada evento corresponde a su detección, no a una fecha histórica del backend. La herramienta MCP asociada es inferida y se identifica como tal, porque la API no confirma el origen del cambio. Recargar la página reinicia el registro de actividad.

La conexión mostrada corresponde a la API HTTP local y no verifica el cliente MCP. La sincronización automática y la actualización manual consultan la misma API. Ante errores, se conservan los últimos datos disponibles y se informa que pueden estar desactualizados.

## Alcance actual

- Persistencia local con SQLite.
- Servidor MCP local mediante `stdio`.
- Dashboard local sin frameworks ni dependencias de frontend.
- Skills reutilizables como paquete Python, catálogo exportable y demo con SQLite temporal (`python -m skills_flota demo`).
- Configuración local del asistente mediante `.env` (excluido de Git) o variables del entorno, que tienen prioridad. Los cambios requieren reiniciar el dashboard.
- Asistente del dashboard con Gemini en la nube u Ollama local con `gemma3:4b`, para consultar el estado y las reglas y gestionar vehículos mediante propuestas confirmadas. En nube se envían datos actuales al proveedor; en local se procesan en este equipo.
- Pruebas automáticas para las herramientas MCP.
- Conservación del código inicial y de una refactorización intermedia.

## Fuera de alcance

- Autenticación y gestión de usuarios.
- Seguimiento geográfico en tiempo real.
- Conexión con dispositivos o vehículos reales.
- Despliegue en producción o servicios externos distintos de Gemini para el asistente.
- Operaciones masivas del chatbot, cliente MCP del chatbot, ejecución de código o SQL generado por IA, RAG, bases vectoriales y agentes múltiples.

## Criterios de éxito

- Codex descubre y consume las herramientas del servidor MCP.
- Las consultas devuelven datos consistentes con SQLite.
- Un vehículo esperando viaje no aparece entre las alertas aunque supere los 30 minutos detenido.
- Las escrituras se verifican mediante una consulta posterior.
- El asistente no modifica datos antes de confirmar y rechaza confirmaciones vencidas, repetidas o sobre un estado que cambió.
- El dashboard refleja las modificaciones sin recarga manual.
- Las pruebas automatizadas finalizan correctamente.
- El repositorio permite reconocer el código inicial, las refactorizaciones y el resultado final.
- Las Skills se pueden invocar desde el asistente, MCP y un consumidor Python sin duplicar las operaciones de negocio; sus contratos se validan y su reutilización se demuestra con pruebas.
