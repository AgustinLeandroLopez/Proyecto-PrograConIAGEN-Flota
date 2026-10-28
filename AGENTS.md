# Instrucciones del proyecto

## Contexto del producto

- Este repositorio contiene un monitor local de flota desarrollado progresivamente con asistencia de IA.
- Antes de cambiar reglas de negocio, alcance o comportamiento visible, leer `docs/PRODUCT.md`.

## Arquitectura y alcance

- Mantener una solución pequeña basada en Python, SQLite y HTML, CSS y JavaScript sin frameworks.
- `database.py` concentra el acceso a SQLite.
- `monitor.py` contiene las reglas de estado y alertas.
- `servidor_mcp.py` publica las capacidades para el agente.
- `dashboard.py` y `dashboard/index.html` muestran la misma información de SQLite. El asistente puede proponer altas, cambios y bajas; solo se aplican tras confirmar la propuesta concreta en el chat.
- `acciones_flota.py` valida los cambios del asistente, administra propuestas de un solo uso y ejecuta las confirmaciones mediante la capa de datos.
- `skills_flota/` empaqueta las habilidades de consulta, gestión y baja. El asistente y MCP usan el mismo registro; conservar sus contratos de entrada/salida, workflows, confirmaciones del chat y ejemplos. `skills_flota/herramientas.py` concentra el snapshot compartido.
- `prompt_agente.py` contiene el contrato compartido de selección de Skills. Los dos modelos reciben el catálogo y workflows; el modo local usa un prompt adaptado al modelo pequeño. Usa únicamente `127.0.0.1:11434` con `gemma3:4b`; no agregar fallback automático a nube. Mantener separados los historiales de ambos modos.
- Conservar las versiones históricas dentro de `versiones/`; sirven como evidencia del proceso de refactorización.

## Reglas de la flota

- Un vehículo está en alerta cuando su velocidad es 0 y lleva más de 30 minutos detenido.
- Un vehículo con `esperando_viaje` activo debe tener velocidad 0 y no genera alerta, aunque supere los 30 minutos detenido.
- Si un vehículo pasa a tener velocidad mayor que 0, `esperando_viaje` se desactiva automáticamente.
- Una patente identifica de forma única a un vehículo.
- La velocidad y los minutos detenido no pueden ser negativos.

## Servidor MCP

- El servidor se llama `monitor_flota` y usa transporte local `stdio`.
- Herramientas disponibles: `consultar_vehiculos`, `consultar_estado_vehiculo`, `consultar_alertas`, `agregar_vehiculo`, `actualizar_estado_vehiculo` y `eliminar_vehiculo`. Las altas y actualizaciones administran el booleano `esperando_viaje`.
- Para operaciones solicitadas por el usuario sobre la flota, preferir las herramientas MCP en lugar de modificar `flota.db` directamente.
- Antes de agregar o actualizar datos, comprobar que el usuario haya pedido explícitamente la modificación.
- Antes de eliminar datos, comprobar también el pedido explícito del usuario. El asistente del dashboard exige confirmar cada propuesta de escritura y verifica el resultado dentro de la misma transacción.
- Después de una escritura mediante MCP, verificar el resultado con una herramienta de consulta.
- El código de aplicación y las pruebas pueden usar la capa de datos directamente cuando corresponda.

## Implementación y verificación

- Preservar el comportamiento existente salvo que el usuario solicite cambiarlo.
- Evitar dependencias nuevas cuando la biblioteca estándar resuelva el caso con claridad.
- Ejecutar `python -m unittest -v test_servidor_mcp.py` después de modificar el servidor MCP, la base o las reglas.
- Si se modifican Skills o el asistente, ejecutar además `python -m unittest -v test_asistente.py test_acciones_flota.py test_skills_flota.py test_ollama_client.py`. La demo y las pruebas usan bases temporales; no modificar la flota real para verificaciones.
- Si cambia la API del dashboard, verificar también `http://127.0.0.1:8000/api/vehiculos` con el servidor local activo.
- Mantener el README y la documentación alineados con las herramientas disponibles.

## Git y archivos locales

- No incluir `.doc_review/`, `flota.db`, `__pycache__/` ni archivos `*.pyc` en el repositorio.
- No inventar la URL del repositorio. Cuando Git esté configurado, obtenerla del remoto `origin` y reflejarla en el README.
- No guardar credenciales, tokens ni secretos en archivos versionados.
