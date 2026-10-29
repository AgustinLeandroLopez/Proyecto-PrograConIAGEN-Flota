# Monitor simple de flota

Proyecto desarrollado para demostrar un proceso progresivo de análisis y refactorización asistido por IA, finalizando con un servidor MCP que permite al agente consultar y actualizar la flota.

La versión actual obtiene los vehículos desde una base de datos local SQLite y conserva la misma lógica de alertas y salida por consola de la versión inicial.

Repositorio: [AgustinLeandroLopez/Proyecto-PrograConIAGEN-Flota](https://github.com/AgustinLeandroLopez/Proyecto-PrograConIAGEN-Flota)

## Documentación del proyecto

- [`AGENTS.md`](AGENTS.md): contexto e instrucciones que Codex carga al trabajar en el repositorio.
- [`docs/PRODUCT.md`](docs/PRODUCT.md): propósito, reglas, alcance y criterios de éxito del producto.
- [`docs/SKILLS.md`](docs/SKILLS.md): relación con la consigna de la cátedra, contratos, workflows y demostración de reutilización.
- [`skills_flota/README.md`](skills_flota/README.md): uso del paquete de Skills desde Python y la terminal.

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
- `skills_flota/`: paquete reutilizable con las Skills `consultar_flota`, `gestionar_vehiculos` y `eliminar_vehiculo`, contratos y registro de ejecución.
- `prompt_agente.py`: contrato e instrucciones compartidos por los dos modelos.
- `ollama_client.py`: transporte local para Ollama con `gemma3:4b`.
- `multiagente.py`: negociación entre Gemini y Gemma, con asignación confirmable, con validación de unidad, precio y límites económicos, hasta tres rondas.
- `escenario_flota.py`: zonas, distancias, tarifas y mínimos ficticios para negociar un viaje con presupuesto.
- `test_multiagente.py`: pruebas aisladas de negociación, contratos de transporte y API HTTP.
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
- `agregar_vehiculo`: incorpora una unidad y admite `esperando_viaje`, `zona`, `tarifa_base` y `precio_minimo` opcionales.
- `actualizar_estado_vehiculo`: modifica velocidad y minutos, que siguen siendo obligatorios, y admite espera, zona, tarifa y mínimo base opcionales. Conserva los opcionales omitidos.
- `eliminar_vehiculo`: elimina una unidad por identificador y verifica que ya no exista.

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

El centro de operaciones usa un tema oscuro responsive, cinco indicadores con datos reales y una tabla que se convierte en tarjetas en móviles. Incluye búsqueda por patente, filtro por estado, ordenamiento por patente, velocidad o prioridad de estado, y actualización manual. La navegación permite ir al dashboard, los vehículos, las alertas activas y la actividad de la sesión.

El panel de actividad conserva hasta 50 cambios observados desde que se abrió la página y resalta las unidades actualizadas durante 10 segundos. No es un historial persistente: las horas corresponden al momento de detección. La herramienta MCP asociada se muestra como una inferencia, porque la API no informa el origen de cada modificación.

El indicador de conexión verifica la API HTTP local, no el estado del cliente MCP. Ante un error conserva los últimos datos, avisa que pueden estar desactualizados y reintenta automáticamente. La fecha del encabezado corresponde a la consulta general; no hay una fecha individual de actualización por vehículo disponible.

El frontend sigue contenido en `dashboard/index.html`, con secciones para estilos, estructura, datos y renderizado. No requiere compilación, fuentes remotas ni nuevas dependencias. Los íconos son SVG locales y la tipografía usa Inter si está instalada, con alternativas del sistema.

## Pruebas

Para ejecutar toda la suite de pruebas unitarias y de integración:

```powershell
python -m unittest discover -v
```

`test_monitor.py` verifica el límite de alerta a los 29, 30 y 31 minutos,
la excepción de espera de viaje, el movimiento y la flota vacía, sin acceder
a SQLite. Estas pruebas y ejemplos representativos en `test_escenario_flota.py`
y `test_acciones_flota.py` señalan las fases AAA: **Arrange** (preparar),
**Act** (ejecutar) y **Assert** (comprobar). El ejemplo de cambio concurrente
también verifica la excepción esperada y que no se sobrescriban los datos.

```powershell
python -m unittest -v test_asistente.py
```

Las pruebas del asistente usan SQLite temporal y Gemini simulado: no modifican `flota.db` ni consumen cuota. Verifican validación, lectura actualizada, propuestas, confirmaciones, errores y API HTTP. No prueban la interpretación semántica de Gemini real.

```powershell
python -m unittest -v test_servidor_mcp.py
```

## Asistente de flota · consultas y gestión

El botón **Asistente de flota** abre un chat lateral (pantalla completa en celulares), con sugerencias, envío con Enter, cierre con botón o Escape e indicador de consulta en curso. Sus errores no detienen la sincronización del dashboard. El navegador solo llama a `POST /api/asistente`; la clave permanece en Python.

El selector permite elegir **Asistente IA en la nube · Gemini** o **Asistente IA local · Gemma 3 4B**. Ambos reutilizan las mismas Skills de consulta, gestión y baja, con iguales validaciones y confirmaciones. Solo cambia el intérprete del pedido. La opción inicial es nube y las conversaciones se conservan por separado en memoria: cambiar de modo no envía el historial local a Gemini. El selector se bloquea mientras una solicitud está en curso.

Para cambiar una unidad a **Esperando viaje**, escribí «Poné ABC123 en Esperando viaje» (usando su patente real), revisá la propuesta y pulsá **Confirmar cambio**. También admite «¿Podés poner la unidad 2 en Esperando viaje?». Se propone velocidad 0 y se conservan los minutos detenido si no pediste cambiarlos. Si no identificás la unidad, el asistente debe pedir patente o ID. Este cambio se realiza desde nube o local; la selección multiagente solo recomienda.

También ofrece **Selección multiagente · Gemini + Gemma**, con conversación e historial propios. Negocia vehículo y precio: Gemini representa al cliente y busca buen precio y cercanía al retiro; Gemma representa a la flota y defiende su precio mínimo. Pueden ofertar, contraproponer, aceptar o retirarse en hasta tres rondas. Solo participan unidades esperando viaje. Python valida presupuesto, mínimo, precio de referencia y disponibilidad. Al acordar prepara una propuesta para marcar la unidad En viaje; requiere Confirmar cambio antes de modificarla.

Para probarlo:

1. Configurar Gemini como se explica abajo y abrir Ollama con `gemma3:4b` instalado.
2. Iniciar o reiniciar el dashboard con `python dashboard.py` y recargar la página.
3. Elegir **Selección multiagente** y abrir **Viaje ficticio**: seleccionar retiro, destino y presupuesto máximo. Los campos definen el viaje: para cambiar esas condiciones, usar el formulario.
4. Pulsar **Iniciar negociación** dentro del cuadro del viaje, sin escribir un mensaje adicional. El chat muestra ofertas, contrapropuestas y resultado. También admite escribir «Negociá un vehículo para este viaje». Sin unidades esperando viaje, informa que no hay candidatos sin llamar a modelos. Para crear disponibilidad de demostración, usar deliberadamente nube o local y confirmar la propuesta.

Cada unidad tiene `zona`, `tarifa_base` y `precio_minimo` guardados en SQLite y visibles en las columnas **Zona ficticia**, **Tarifa base** y **Mínimo base** de la tabla principal y en las tarjetas móviles. Al reiniciar `python dashboard.py`, la migración agrega los campos sin borrar vehículos y conserva los perfiles anteriores una sola vez. Las ediciones posteriores sobreviven a los reinicios. Nuevas altas sin esos datos usan Centro, base 4000 y mínimo base 3000.

Para editarlos, elegir nube o local y pedir «Actualizá ABC123 a zona Sur, tarifa base 6000 y mínimo base 4500». Revisar la propuesta y pulsar **Confirmar cambio**. Se conservan velocidad, minutos, espera y cualquier campo omitido. Zonas admitidas: Centro, Norte, Sur y Oeste. Importes enteros de 1 a 1000000; mínimo base no mayor que tarifa base. Estos datos siguen siendo ficticios; no son GPS ni tarifas reales.

La negociación consulta esos valores guardados y calcula por ruta: referencia = tarifa base + km de viaje × 800 + km al retiro × 400; mínimo total = mínimo base + km totales × 300. **Mínimo base** en la tabla es el valor guardado; el mínimo que evalúa Gemma incluye el recorrido. Las distancias y fórmulas están en `escenario_flota.py`. El viaje inicial es Centro → Norte con presupuesto 9000. Se pueden probar presupuestos bajos para explorar negociaciones sin acuerdo.

El pedido, historial propio, candidatos y diálogo se envían a ambos modelos. El contexto estructurado de Gemini incluye presupuesto; el de Gemma incluye mínimos. Ambos límites son visibles al operador para la demo y pueden aparecer en el texto del usuario. No se comparten historiales de los modos individuales. Ante errores se conserva el diálogo previo y se informa negociación incompleta, sin fallback ni reintentos. La espera del navegador es 450 segundos para hasta seis llamadas; cada llamada mantiene su timeout. Si la flota cambia, hay que repetir. Capacidad, horarios y ubicaciones reales no se admiten. El reconocimiento del alcance depende del modelo; Python verifica que aceptar copie la última unidad y precio ofrecidos y respete ambos límites.

Las intervenciones visibles se construyen desde decisiones JSON y datos verificados, sin mostrar prosa libre. El precio es ficticio y no se cobra. Tras confirmar, la unidad pasa a En viaje y deja de estar disponible. Para liberarla, pedí «Dejá ABC123 esperando viaje» y confirmá el cambio. Dos modelos no garantizan el mejor precio ni un acuerdo; se demuestra el intercambio entre roles con objetivos distintos.

### Opción local con Ollama

Abrir Ollama y comprobar que el modelo esté instalado:

```powershell
ollama list
```

Debe aparecer `gemma3:4b`. Si falta, instalarlo con `ollama pull gemma3:4b`. Con Ollama abierto, iniciar el dashboard con `python dashboard.py`, abrir el asistente y elegir la opción local. No requiere API key ni cambios en `.env`.

Python llama exclusivamente a `http://127.0.0.1:11434/api/chat` con el modelo local fijo `gemma3:4b`, sin proxies del entorno ni redirecciones. Si Ollama falla, se informa el error: no se cambia a Gemini automáticamente. La primera consulta puede tardar por la carga del modelo. Las consultas del modo local no llaman al proveedor cloud; los datos locales seguirán apareciendo en SQLite y pueden ser consultados desde el otro modo si el operador lo elige explícitamente.

El cliente usa `stream: false`, JSON Schema en `format`, temperatura 0, contexto de 16384 tokens y hasta 512 tokens de salida, según la [API de chat de Ollama](https://docs.ollama.com/api/chat) y su [guía de salidas estructuradas](https://docs.ollama.com/capabilities/structured-outputs). Se limita el prompt completo a 14000 bytes UTF-8 para dejar margen de contexto; no se trunca silenciosamente. Timeout local: 120 segundos; espera del navegador: 150 segundos. El archivo `ollama_client.py` concentra estos límites. El rechazo de temas ajenos sigue dependiendo de la interpretación del modelo y de la validación del plan; revisar siempre las propuestas.

### Opción en la nube con Gemini

Obtener una clave en [Google AI Studio](https://aistudio.google.com/api-keys). Completar el archivo `.env` en la raíz del proyecto (o copiar `.env.example` si no existe):

```dotenv
GEMINI_API_KEY=tu_clave_de_ai_studio
GEMINI_MODEL=gemini-3.5-flash-lite
```

Guardar el archivo y ejecutar `python dashboard.py`. Reiniciar el servidor después de cambiar `.env`. El archivo está excluido de Git; no pegar la clave en chats ni guardarla en archivos versionados. Se admiten líneas `KEY=VALUE`, valores con comillas simples o dobles y comentarios en líneas que empiezan con `#`. No se expanden variables ni se admiten comentarios al final de un valor.

Las variables del entorno tienen prioridad sobre `.env`. Si antes configuraste una clave en PowerShell y querés usar la del archivo, ejecutar `Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue` y, si corresponde, `Remove-Item Env:GEMINI_MODEL -ErrorAction SilentlyContinue` antes de iniciar el servidor.

Como alternativa, configurar la clave **en la terminal local** con PowerShell:

```powershell
$geminiKey = Read-Host 'Clave Gemini' -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $geminiKey).Password
Remove-Variable geminiKey
$env:GEMINI_MODEL = 'gemini-3.5-flash-lite'
python dashboard.py
```

Abrir `http://127.0.0.1:8000`. Las variables se aplican al servidor iniciado desde esa terminal. Si ya estaba iniciado, detenerlo y volver a ejecutarlo. El dashboard carga `.env` desde la raíz del proyecto al iniciar, sin sobrescribir variables del entorno. Sin clave, el dashboard funciona y el chat explica la configuración faltante.

Modelo predeterminado: `gemini-3.5-flash-lite`, publicado con entrada y salida en nivel gratuito en la [tabla oficial de precios](https://ai.google.dev/gemini-api/docs/pricing), consultada el 22 de octubre de 2026. Esto no garantiza acceso ni cuota para una cuenta particular: verificar modelo habilitado, nivel y [límites activos en AI Studio](https://ai.google.dev/gemini-api/docs/rate-limits). No hay cambio automático de modelo ni reintentos. La integración REST sigue la [referencia generateContent](https://ai.google.dev/api/generate-content) con instrucción de sistema y salida estructurada.

**Datos enviados al modelo seleccionado:** consulta, hasta cuatro consultas anteriores del usuario de ese mismo modo (solo para resolver referencias), vehículos actuales con identificador, patente, velocidad, minutos detenido, espera, estado y alerta; resumen y reglas del monitor. No se envían secretos ni respuestas anteriores. En modo nube estos datos se envían a Gemini; en modo local se procesan con Ollama en el equipo. Gemini puede usar contenido del nivel gratuito para mejorar sus productos según sus condiciones; revisar los términos del proveedor antes de usar datos sensibles.

`gemini_client.py` concentra el transporte HTTPS con biblioteca estándar. `asistente.py` valida entradas y el alcance en Python: solo acepta una lista cerrada de intenciones y referencias a unidades. Gemini interpreta el lenguaje; Python produce el texto a partir de una nueva lectura mediante `obtener_snapshot()` y las reglas de `monitor.py`. Ninguna prosa arbitraria del modelo se muestra. El modelo no ejecuta SQL ni código. Estas medidas reducen desvíos, pero no garantizan que interprete correctamente todas las preguntas.

Las descripciones, operaciones y workflows del paquete `skills_flota` se incluyen en las instrucciones de ambos modelos. Gemini recibe también los contratos de entrada en el prompt; Gemma usa instrucciones más breves y ejemplos ficticios, con el mismo contrato estructurado de selección. El modelo seleccionado propone una Skill, operación y argumentos en JSON; Python comprueba su compatibilidad e invoca el registro. Cada Skill publica nombre, versión, propósito, esquema de entrada/salida, pasos, herramientas y ejemplos. El chatbot y las seis herramientas MCP comparten los ejecutores. La selección estructurada usa un despachador Python, sin depender del protocolo nativo de function calling de un proveedor.

Para inspeccionar los contratos y demostrar su reutilización sin claves ni llamadas al proveedor:

```powershell
python -m skills_flota catalogo
python -m skills_flota demo
```

La demo usa las tres Skills con una base temporal; no cambia `flota.db`. Ver [la guía de Skills para la entrega](docs/SKILLS.md).

Consultas disponibles: resumen, alertas, espera de viaje, movimiento, detenidos dentro del límite, listado o estado por patente/identificador y reglas. Para temas mixtos solo se responde la parte de flota. El clima, Boca y otros temas ajenos se rechazan. Ubicaciones, viajes asignados, causas e historial no están disponibles. Ante una referencia a una unidad inexistente se informa la ausencia.

También se puede gestionar **una unidad por operación**:

- «Agregá XYZ123 a 0 km/h, detenido 0 minutos, esperando viaje».
- «Actualizá XYZ123 a 60 km/h y 0 minutos detenido».
- «Poné XYZ123 esperando viaje».
- «Cambiá la patente XYZ123 por XYZ456».
- «Eliminá el vehículo XYZ456».

El asistente muestra una propuesta y los botones **Confirmar cambio** y **Cancelar**. Todavía no se escribe nada cuando aparece la propuesta: revisá la unidad y los datos, especialmente antes de eliminar. Las altas requieren patente, velocidad y minutos detenido; la espera es opcional y vale falso si se omite. Las actualizaciones conservan los campos no indicados; una velocidad positiva desactiva la espera. Las patentes admitidas por el asistente contienen de 3 a 10 letras o números.

`acciones_flota.py` proporciona a las Skills la validación de valores, resolución de la unidad y hasta 100 propuestas en memoria. Cada propuesta vence a los cinco minutos y su confirmación es de un solo uso. Al confirmar no se llama a Gemini: `database.py` compara el estado revisado, aplica el cambio y verifica el resultado en una transacción. Si otro proceso cambió la unidad, se rechaza la propuesta y se debe pedir una nueva. Los datos de ejemplo se cargan solo al crear la tabla: una baja no reaparece al reiniciar. Recargar pierde los botones del chat; reiniciar el servidor invalida las propuestas pendientes. Si se pierde la conexión al confirmar, consultá la flota antes de repetir el pedido.

La API `POST /api/asistente` recibe `{mensaje, historial, proveedor}` (`proveedor` admite `nube` o `local`; si se omite conserva `nube`) y devuelve `{respuesta}` o una propuesta con `{skill, estado, respuesta, datos, propuesta: {token}}`. Los botones envían exclusivamente `{confirmacion: token, confirmar: true/false}` al mismo endpoint; confirmar no llama a ningún modelo. Los campos, el origen local y el token se validan en Python; no se aceptan instrucciones de escritura arbitrarias del navegador. Esta aplicación sigue siendo local y sin autenticación.

Límites generales: 1000 caracteres por mensaje, cuatro consultas previas por modo, cuerpo HTTP de 24 KB, contexto de flota de 60 000 caracteres y respuesta de hasta 6000 caracteres (listados largos se indican como incompletos). El modo local tiene además el límite de prompt indicado arriba. Gemini tiene un máximo de salida de 1024 tokens y timeout de 20 segundos; el navegador espera hasta 45 segundos en ese modo. Cada cliente controla también el plazo durante la lectura y un máximo de respuesta del proveedor de 32 KB. Solo se procesa una consulta de chat simultánea en el servidor; el cliente también evita duplicados. Se conservan hasta 40 mensajes en pantalla por modo durante la sesión, sin persistencia; recargar borra ambas conversaciones.

Para una comprobación real, configurar la clave y probar las tres sugerencias, una consulta por patente, «¿Cómo salió Boca el domingo?», «¿Cómo está el tiempo?», un intento de cambiar el rol y una pregunta mixta. Revisar una propuesta de alta, una actualización y una baja; cancelar no debe cambiar datos. La semántica real, el acceso y las cuotas solo pueden verificarse con credenciales. Para comprobar la presentación, abrir y cerrar el chat tanto en escritorio como en una pantalla móvil y verificar que se pueda escribir, enviar y desplazar los mensajes.

Pruebas con bases temporales y Gemini simulado, sin modificar la flota local ni consumir cuota:

```powershell
python -m unittest -v test_configuracion.py test_asistente.py test_acciones_flota.py test_servidor_mcp.py test_skills_flota.py test_ollama_client.py test_multiagente.py test_escenario_flota.py test_datos_persistentes.py test_asignacion_viaje.py test_monitor.py
```

### Fleet AI

Fleet AI abre el mismo chat desde la mascota SVG local en la esquina inferior derecha o desde el acceso superior. El panel se superpone al dashboard, admite Escape y devuelve el foco al acceso utilizado. Incluye sugerencias, avatares, estados de procesamiento y movimiento reducido. Enter envía; Shift+Enter agrega una línea. Conserva Gemini, Ollama, historiales separados y confirmaciones de cambios. No comprueba disponibilidad del modelo al abrir. Generar reporte consulta un resumen actual en el chat; no exporta archivos. El sistema no almacena historial de vehículos.
