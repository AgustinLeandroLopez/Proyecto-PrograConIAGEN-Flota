# Monitor de flota

## Propósito

El proyecto demuestra cómo un agente de programación puede analizar, refactorizar y ampliar una aplicación, y luego interactuar con ella mediante un servidor MCP propio. El resultado permite consultar y modificar una flota local mientras un dashboard refleja los cambios automáticamente.

## Problema

Un operador necesita conocer rápidamente qué vehículos están en movimiento, cuáles están detenidos y cuáles requieren atención por permanecer detenidos demasiado tiempo.

## Usuario principal

El usuario principal es un operador o responsable de una flota pequeña que consulta el estado general y revisa alertas.

## Reglas del producto

- Un vehículo tiene identificador numérico, patente única, velocidad, minutos detenido, `esperando_viaje`, `en_viaje`, `zona`, `tarifa_base` y `precio_minimo`, persistidos en SQLite.
- La zona ficticia debe ser Centro, Norte, Sur u Oeste. Tarifa y mínimo base son enteros de 1 a 1000000 pesos ficticios; el mínimo base no puede superar la tarifa base. No representan GPS ni precios reales.
- Si la velocidad es mayor que 0, el vehículo está en movimiento.
- Si está detenido y `esperando_viaje` está activo, está disponible para recibir una asignación y no genera alerta, sin importar sus minutos detenido.
- Si la velocidad es 0 y lleva hasta 30 minutos detenido, está detenido dentro del tiempo permitido.
- Si la velocidad es 0 y lleva más de 30 minutos detenido, está en alerta.
- La velocidad y los minutos detenido deben ser valores iguales o mayores que 0.
- Un vehículo que pasa a tener velocidad mayor que 0 deja automáticamente de esperar viaje.
- `en_viaje` es un booleano persistente de asignación, distinto de la velocidad. No puede coexistir con `esperando_viaje`. Una unidad en viaje no es candidata a nuevas negociaciones. Volver a esperar viaje finaliza su asignación. Las alertas por detención se mantienen: el flag no las suprime.

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
- `agregar_vehiculo`: registra un vehículo con patente única; admite espera, en viaje, zona, tarifa base y mínimo base opcionales.
- `actualizar_estado_vehiculo`: modifica velocidad y minutos detenido; admite espera, en viaje, zona y precios base opcionales. Conserva los opcionales omitidos; velocidad y minutos siguen siendo obligatorios en MCP.
- `eliminar_vehiculo`: elimina una unidad por identificador y verifica su ausencia.

## Dashboard

La tabla del dashboard es una vista local de la flota. Presenta cinco indicadores operativos y una tabla con búsqueda por patente, filtros por estado y ordenamiento. Incluye columnas de Zona, Tarifa base y Mínimo base provenientes de SQLite. En móviles, las filas se presentan como tarjetas con los mismos campos; en escritorio permite desplazamiento horizontal cuando falta espacio. Incluye el estado En viaje, resaltado de asignaciones y filtro específico. La navegación permite consultar flota, alertas y actividad de la sesión.

Cada fila permite abrir o cerrar un detalle de los datos existentes mediante clic o con el botón Ver detalle, accesible por teclado y visible en dispositivos táctiles. Las filas abiertas se conservan durante la sincronización y al filtrar u ordenar; se descartan cuando la unidad deja de existir. La actualización modifica los nodos existentes para conservar el foco y permitir transiciones de las barras de velocidad, relativas al máximo actual de la flota, sin representar límites permitidos. Las filas y sus badges tienen un realce sutil con mouse o foco de teclado, sin desplazar columnas. Las transiciones respetan la preferencia de movimiento reducido.

El asistente permite consultar, agregar, actualizar y eliminar una unidad por operación. El modelo seleccionado interpreta el pedido; Python valida una lista cerrada de operaciones y prepara una propuesta con los datos concretos. El operador debe usar Confirmar cambio o Cancelar. Las propuestas vencen en cinco minutos, se procesan una sola vez y se pierden al reiniciar el servidor. Una confirmación no vuelve a consultar a ningún modelo. Si la unidad cambió desde la propuesta, no se sobrescribe: se solicita una nueva operación. Las escrituras y su verificación son transaccionales.

Fleet AI se abre desde una mascota SVG flotante o el acceso superior, en un panel superpuesto que conserva el espacio de la tabla. El encabezado permite maximizar a todo el ancho y alto y restaurar el panel lateral sin perder conversación, modo o solicitud en curso. El tamaño elegido se conserva al cerrar y reabrir durante la sesión. Ofrece avatares y estados de procesamiento, respeta movimiento reducido y permite cerrar con Escape. Las sugerencias de nube y local son botones compactos en un desplegable sobre el campo de escritura; aparecen al comenzar y se pliegan al enviar, pudiendo volver a abrirse. No afirma disponibilidad del modelo sin verificarla. El reporte devuelve un resumen actual en el chat, sin exportación; la sugerencia de historial consulta su disponibilidad porque no se almacena historia de vehículos.

El selector ofrece Asistente IA en la nube, Asistente IA local y Selección multiagente. Nube y local usan las mismas Skills y reglas. Las conversaciones e historiales se mantienen separados por modo; la opción inicial es nube. Local usa exclusivamente Ollama en `127.0.0.1:11434` con `gemma3:4b`, sin clave, proxies ni redirecciones. No hay cambio automático de proveedor ante errores. El modelo local tiene un plazo de 120 segundos y límite de prompt de 14000 bytes UTF-8 incluidos ejemplos; la UI espera hasta 150 segundos. El selector se bloquea durante solicitudes. El primer arranque puede demorar por la carga del modelo.

La selección multiagente es una negociación didáctica de vehículo y precio con asignación confirmable. Gemini representa al cliente y busca menor precio y cercanía dentro de su presupuesto. Gemma representa a la flota y defiende su mínimo. Pueden proponer, contraproponer, aceptar o retirarse en hasta tres rondas. Solo participan unidades esperando viaje y detenidas, leídas mediante `consultar_flota`. El operador configura origen, destino y presupuesto en «Viaje ficticio», que se pliega al enviar. Los campos del formulario definen la solicitud; si el texto pide otras condiciones, los modelos deben pedir ajustar el formulario. No se impone elegir al que más tiempo lleva esperando.

`escenario_flota.py` define distancias ficticias y cotiza desde zona, tarifa y mínimo base de SQLite. El cuadro muestra retiro, destino, presupuesto y «Iniciar negociación», sin listado previo de candidatos ni costos. El botón inicia el mismo flujo del chat sin exigir otro mensaje; se deshabilita durante carga o solicitud. Carga y errores aparecen solo cuando corresponden. En multiagente se omiten bienvenida extensa y sugerencias duplicadas. Al maximizar en escritorio, los tres campos se alinean en una fila. Origen y destino deben ser distintos; presupuesto entero de 1 a 1000000. Referencia = tarifa base + km de viaje × 800 + km al retiro × 400. Mínimo total = `precio_minimo` base + km totales × 300. Escenario inicial: Centro → Norte, presupuesto 9000. Los costos por ruta no se guardan como precios base.

Al iniciar, la migración transaccional agrega las columnas sin borrar vehículos ni repetir semillas. La primera migración de zona y tarifas conserva los perfiles previos por ID: Centro/Norte/Sur/Oeste, bases 4000/4500/3500/4200 y mínimos 3000/3400/2800/3200. La columna `en_viaje` se agrega con false. Las ediciones posteriores se conservan al reiniciar. Altas sin configuración usan Centro, base 4000, mínimo 3000 y en_viaje false, visibles en la propuesta. Las semillas nuevas tienen perfiles explícitos. Cotizar nunca recalcula perfiles por ID.

Python valida IDs, precios enteros positivos y referencia máxima. Las ofertas del cliente no pueden exceder presupuesto ni las de la flota bajar de su mínimo. Aceptar exige copiar unidad y precio de la última oferta y respetar ambos límites. Tras releer candidatos, un acuerdo invoca `gestionar_vehiculos` para proponer `en_viaje=true`, `esperando_viaje=false` y minutos detenido 0, conservando velocidad y configuración. Compara el estado anterior de la propuesta con el candidato; si cambió, cancela el token y pide repetir. Confirmar cambio aplica y verifica en una transacción; cancelar, vencer o reutilizar el token no asigna. La confirmación vuelve a verificar concurrencia. No hay cobro ni historial de viajes o precios acordados. Las intervenciones se construyen en Python desde JSON y datos verificados.

Este modo usa explícitamente ambos proveedores y envía pedido, historial propio, candidatos y diálogo a ambos; no recibe historiales de modos individuales. El presupuesto estructurado va solo al cliente y los mínimos solo a la flota. Esto acota contexto sin prometer confidencialidad: el usuario puede mencionarlos en el texto. Puede terminar con acuerdo y propuesta, sin acuerdo, sin candidatos, pedido no admitido, cambio de flota o negociación incompleta. Sin candidatos no llama a modelos. Ante errores conserva intervenciones válidas, sin fallback ni reintentos. Hasta seis llamadas con límites de cada proveedor y espera del navegador de 450 segundos. La interpretación depende de los modelos; límites económicos y disponibilidad se validan en Python. Capacidad, horarios y ubicaciones reales siguen fuera de alcance. No se garantiza precio óptimo ni acuerdo.

Las actualizaciones admiten patente, velocidad, minutos detenido, espera, en viaje, zona, tarifa base y mínimo base; conservan lo omitido. Las altas requieren patente, velocidad y minutos, con el resto opcional. «Actualizá ABC123 a zona Sur, tarifa base 6000 y mínimo base 4500» prepara una propuesta confirmable. «Finalizá el viaje de ABC123» propone en_viaje false; «Dejá ABC123 esperando viaje» finaliza la asignación y lo hace disponible. La concurrencia compara todos los campos persistidos. Las patentes del asistente deben contener de 3 a 10 letras o números. Las semillas solo se insertan al crear la tabla. Los temas ajenos a la flota se rechazan.

En nube y local, «Poné ABC123 en Esperando viaje» y «¿Podés poner ABC123 en Esperando viaje?» son pedidos de actualización. Activar espera propone velocidad 0 si no se indicó otra, incluso si el modelo omite ese campo, sin alterar minutos omitidos. Requiere confirmar. Sin unidad ni referencia inequívoca en el historial, el modelo debe seleccionar `modificacion` para pedir patente o ID, sin elegir una unidad ni rechazar como tema ajeno.

Cuando detecta incorporaciones o actualizaciones mientras está abierto, resalta durante 10 segundos los vehículos afectados y conserva hasta 50 eventos en memoria. La hora de cada evento corresponde a su detección, no a una fecha histórica del backend. La herramienta MCP asociada es inferida y se identifica como tal, porque la API no confirma el origen del cambio. Recargar la página reinicia el registro de actividad.

La conexión mostrada corresponde a la API HTTP local y no verifica el cliente MCP. La sincronización automática y la actualización manual consultan la misma API. Ante errores, se conservan los últimos datos disponibles y se informa que pueden estar desactualizados.

## Alcance actual

- Persistencia local con SQLite.
- Servidor MCP local mediante `stdio`.
- Dashboard local sin frameworks ni dependencias de frontend.
- Skills reutilizables como paquete Python, catálogo exportable y demo con SQLite temporal (`python -m skills_flota demo`).
- Configuración local del asistente mediante `.env` (excluido de Git) o variables del entorno, que tienen prioridad. Los cambios requieren reiniciar el dashboard.
- Asistente del dashboard con Gemini en la nube u Ollama local con `gemma3:4b`, para consultar el estado y las reglas y gestionar vehículos mediante propuestas confirmadas. En nube se envían datos actuales al proveedor; en local se procesan en este equipo.
- Negociación multiagente didáctica con Gemini y Gemma: zonas, distancias y tarifas ficticias, presupuesto por viaje y acuerdo de unidad/precio validado; asignación En viaje tras confirmar.
- Pruebas automáticas para las herramientas MCP.
- Conservación del código inicial y de una refactorización intermedia.

## Fuera de alcance

- Autenticación y gestión de usuarios.
- Seguimiento geográfico en tiempo real.
- Conexión con dispositivos o vehículos reales.
- Despliegue en producción o servicios externos distintos de Gemini para el asistente.
- Operaciones masivas del chatbot, cliente MCP del chatbot, ejecución de código o SQL generado por IA, RAG, bases vectoriales y agentes múltiples fuera de la negociación acotada de vehículos.

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
- La negociación limita las rondas, valida unidad, precio, mínimo, presupuesto y disponibilidad, y solo asigna En viaje tras una confirmación válida y verificada.
