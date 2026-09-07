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

## Capacidades MCP

- `consultar_vehiculos`: devuelve toda la flota con su estado calculado y la condición de espera de viaje.
- `consultar_estado_vehiculo`: devuelve un vehículo por identificador.
- `consultar_alertas`: devuelve los vehículos que superan el límite permitido.
- `agregar_vehiculo`: registra un vehículo con una patente que no exista e indica opcionalmente si espera viaje.
- `actualizar_estado_vehiculo`: modifica velocidad, minutos detenido y la condición de espera de viaje de un vehículo existente.

## Dashboard

El dashboard es una vista local de solo lectura. Presenta el resumen operativo, incluyendo una categoría separada para los vehículos esperando viaje, las alertas y el detalle de cada vehículo. Cuando detecta una incorporación o actualización mientras está abierto, identifica la herramienta MCP asociada y resalta temporalmente el vehículo afectado.

## Alcance actual

- Persistencia local con SQLite.
- Servidor MCP local mediante `stdio`.
- Dashboard local sin frameworks ni dependencias de frontend.
- Pruebas automáticas para las herramientas MCP.
- Conservación del código inicial y de una refactorización intermedia.

## Fuera de alcance

- Autenticación y gestión de usuarios.
- Seguimiento geográfico en tiempo real.
- Conexión con dispositivos o vehículos reales.
- Servicios externos o despliegue en producción.
- Uso de un modelo generativo dentro de la aplicación en ejecución. La IA participa en el desarrollo y como agente cliente del servidor MCP.

## Criterios de éxito

- Codex descubre y consume las herramientas del servidor MCP.
- Las consultas devuelven datos consistentes con SQLite.
- Un vehículo esperando viaje no aparece entre las alertas aunque supere los 30 minutos detenido.
- Las escrituras se verifican mediante una consulta posterior.
- El dashboard refleja las modificaciones sin recarga manual.
- Las pruebas automatizadas finalizan correctamente.
- El repositorio permite reconocer el código inicial, las refactorizaciones y el resultado final.
