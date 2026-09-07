# Monitor simple de flota

Proyecto desarrollado para demostrar un proceso progresivo de análisis y refactorización asistido por IA, finalizando con un servidor MCP que permite al agente consultar y actualizar la flota.

La versión actual obtiene los vehículos desde una base de datos local SQLite y conserva la misma lógica de alertas y salida por consola de la versión inicial.

Repositorio: [AgustinLeandroLopez/Proyecto-PrograConIAGEN-Flota](https://github.com/AgustinLeandroLopez/Proyecto-PrograConIAGEN-Flota)

## Documentación del proyecto

- [`AGENTS.md`](AGENTS.md): contexto e instrucciones que Codex carga al trabajar en el repositorio.
- [`docs/PRODUCT.md`](docs/PRODUCT.md): propósito, reglas, alcance y criterios de éxito del producto.

## Versiones conservadas

- `versiones/01_version_inicial.py`: código inicial con datos en memoria y condicionales anidados.
- `versiones/02_primera_refactorizacion.py`: incorporación de funciones, una constante para el límite y condiciones más simples.
- Versión actual: separación entre acceso a SQLite, reglas del monitor y ejecución principal.

## Estructura actual

- `main.py`: inicia el programa y coordina la consulta y presentación de los vehículos.
- `database.py`: crea, migra y consulta la base SQLite. También contiene funciones para consultar y actualizar un vehículo.
- `monitor.py`: contiene las reglas que determinan el estado, las alertas y la salida por consola.
- `servidor_mcp.py`: publica las operaciones de la flota como herramientas MCP.
- `test_servidor_mcp.py`: verifica las herramientas mediante un cliente MCP en memoria.
- `dashboard.py`: inicia un dashboard web local conectado a la misma base SQLite.
- `dashboard/index.html`: interfaz visual que actualiza la flota automáticamente.
- `.codex/config.toml`: configura el servidor MCP local para Codex.
- `flota.db`: se genera automáticamente la primera vez que se ejecuta el programa.

## Requisitos

- Python 3.10 o superior.
- SDK oficial de MCP para Python.

Instalar la dependencia:

```powershell
python -m pip install -r requirements.txt
```

## Ejecución

```powershell
python main.py
```

Para ejecutar las versiones anteriores:

```powershell
python versiones/01_version_inicial.py
python versiones/02_primera_refactorizacion.py
```

## Herramientas MCP

El servidor publica estas herramientas:

- `consultar_vehiculos`: devuelve toda la flota, el estado calculado y si cada vehículo espera viaje.
- `consultar_estado_vehiculo`: consulta un vehículo por su identificador.
- `consultar_alertas`: devuelve los vehículos detenidos más de 30 minutos que no esperan viaje.
- `agregar_vehiculo`: incorpora un vehículo nuevo e incluye opcionalmente `esperando_viaje`.
- `actualizar_estado_vehiculo`: modifica velocidad, minutos detenido y `esperando_viaje` de un vehículo. Velocidad y minutos siguen siendo obligatorios.

`esperando_viaje` es un estado persistente para un vehículo detenido y disponible. Puede tener cualquier cantidad de minutos detenido sin generar una alerta. Si se actualiza con velocidad mayor que 0, el estado se desactiva automáticamente. Las bases existentes se actualizan en el inicio: se agrega la columna con valor `false` sin eliminar vehículos.

El servidor utiliza transporte local `stdio`. Al ejecutarlo directamente queda esperando que un cliente MCP se conecte:

```powershell
python servidor_mcp.py
```

La configuración incluida en `.codex/config.toml` utiliza las rutas locales de este equipo. Para activarla, abrir esta carpeta como proyecto confiable en Codex y reiniciar la aplicación. Luego se puede consultar el servidor desde el menú de MCP o mediante `/mcp`.

## Dashboard web

Iniciar el dashboard en otra terminal:

```powershell
python dashboard.py
```

Luego abrir `http://127.0.0.1:8000`. La página consulta la base local cada dos segundos, por lo que refleja automáticamente las actualizaciones realizadas mediante las herramientas MCP.

Para demostrar la integración, mantener el dashboard abierto y pedirle a Codex:

> Usá la herramienta `agregar_vehiculo` del MCP `monitor_flota` para agregar un vehículo con patente JKL012, velocidad 25 km/h y 0 minutos detenido. Después consultá la flota para verificarlo.

El vehículo nuevo aparecerá automáticamente en el dashboard. También se puede demostrar una actualización:

> Usá el MCP `monitor_flota` para actualizar el vehículo con ID 2: velocidad 0 y 40 minutos detenido. Después consultá nuevamente las alertas.

El vehículo `DEF456` aparecerá en alerta en el dashboard. Al terminar, restaurarlo a velocidad 0 y 15 minutos detenido.

Para marcarlo disponible y esperando una asignación:

> Usá el MCP `monitor_flota` para actualizar el vehículo con ID 2: velocidad 0, 45 minutos detenido y `esperando_viaje` en true. Después consultá las alertas para verificar que no aparezca.

## Pruebas

```powershell
python -m unittest -v test_servidor_mcp.py
```

## Flujo sugerido para la demostración

1. Pedir al agente que consulte las alertas de la flota.
2. Solicitar que actualice el vehículo 2 para dejarlo detenido durante 40 minutos.
3. Pedir nuevamente las alertas y verificar que el vehículo 2 aparezca en el resultado.
4. Marcarlo esperando viaje y verificar que deja de aparecer entre las alertas.
5. Restaurar el vehículo 2 a su estado inicial.
