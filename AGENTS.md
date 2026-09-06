# Instrucciones del proyecto

## Contexto del producto

- Este repositorio contiene un monitor local de flota desarrollado progresivamente con asistencia de IA.
- Antes de cambiar reglas de negocio, alcance o comportamiento visible, leer `docs/PRODUCT.md`.

## Arquitectura y alcance

- Mantener una solución pequeña basada en Python, SQLite y HTML, CSS y JavaScript sin frameworks.
- `database.py` concentra el acceso a SQLite.
- `monitor.py` contiene las reglas de estado y alertas.
- `servidor_mcp.py` publica las capacidades para el agente.
- `dashboard.py` y `dashboard/index.html` muestran la misma información de SQLite y no modifican la flota.
- Conservar las versiones históricas dentro de `versiones/`; sirven como evidencia del proceso de refactorización.

## Reglas de la flota

- Un vehículo está en alerta cuando su velocidad es 0 y lleva más de 30 minutos detenido.
- Una patente identifica de forma única a un vehículo.
- La velocidad y los minutos detenido no pueden ser negativos.

## Servidor MCP

- El servidor se llama `monitor_flota` y usa transporte local `stdio`.
- Herramientas disponibles: `consultar_vehiculos`, `consultar_estado_vehiculo`, `consultar_alertas`, `agregar_vehiculo` y `actualizar_estado_vehiculo`.
- Para operaciones solicitadas por el usuario sobre la flota, preferir las herramientas MCP en lugar de modificar `flota.db` directamente.
- Antes de agregar o actualizar datos, comprobar que el usuario haya pedido explícitamente la modificación.
- Después de una escritura mediante MCP, verificar el resultado con una herramienta de consulta.
- El código de aplicación y las pruebas pueden usar la capa de datos directamente cuando corresponda.

## Implementación y verificación

- Preservar el comportamiento existente salvo que el usuario solicite cambiarlo.
- Evitar dependencias nuevas cuando la biblioteca estándar resuelva el caso con claridad.
- Ejecutar `python -m unittest -v test_servidor_mcp.py` después de modificar el servidor MCP, la base o las reglas.
- Si cambia la API del dashboard, verificar también `http://127.0.0.1:8000/api/vehiculos` con el servidor local activo.
- Mantener el README y la documentación alineados con las herramientas disponibles.

## Git y archivos locales

- No incluir `.doc_review/`, `flota.db`, `__pycache__/` ni archivos `*.pyc` en el repositorio.
- No inventar la URL del repositorio. Cuando Git esté configurado, obtenerla del remoto `origin` y reflejarla en el README.
- No guardar credenciales, tokens ni secretos en archivos versionados.
