# Agente de flota con Skills empaquetadas y reutilizables

## Relación con la consigna

El objetivo del trabajo es implementar un agente inteligente, ejecutado
localmente o mediante una API en la nube, con habilidades específicas
empaquetadas y reutilizables. El proyecto usa una aplicación Python local y
un selector entre Gemini mediante HTTPS y Ollama local con `gemma3:4b`.
Así se pueden demostrar ambas alternativas sin cambiar las Skills.

La definición usada corresponde al material de cátedra «12-Agentes», páginas
19–21: capacidad estructurada con propósito, entrada, workflow, salida e
invocación de herramientas. El paquete `skills_flota` materializa esos elementos
en código y participa en las invocaciones reales del agente.

| Elemento | Evidencia en el proyecto |
| --- | --- |
| Nombre y propósito | Cada objeto `SKILL` declara nombre, descripción y versión |
| Entrada estructurada | `input_schema`, validado antes de ejecutar |
| Instrucciones/workflow | Pasos declarados por Skill e incluidos en las instrucciones de ambos modelos |
| Salida estructurada | `output_schema` con estado, respuesta y datos; validación de salida |
| Invocación de herramientas | Las funciones de ejecución usan lectura de SQLite, reglas del monitor y operaciones transaccionales |
| Empaquetado | Paquete Python importable `skills_flota`, registro y catálogo exportable |
| Reutilización | Chatbot, adaptadores MCP y consumidor Python/CLI utilizan el mismo registro |

## Habilidades implementadas

### Consultar flota

Archivo: `skills_flota/consultar.py`. Nombre invocable: `consultar_flota`.

Recibe operación, patentes e identificadores. Lee un snapshot actual, selecciona
las unidades, aplica filtros y calcula el resumen. Devuelve vehículos, métricas
y texto. No modifica la base. Incluye estados, alertas, espera, movimiento,
detenciones, reglas y aviso de información no disponible.

Herramientas: `skills_flota.herramientas.obtener_snapshot`, acceso de lectura
de `database.py` y reglas de `monitor.py`.

### Gestionar vehículos

Archivo: `skills_flota/gestionar.py`. Nombre invocable: `gestionar_vehiculos`.

Recibe `agregar` o `actualizar`, selección de una unidad y campos de cambio,
incluyendo zona ficticia, tarifa base y mínimo base persistidos en SQLite.
Valida datos y unicidad, conserva valores omitidos y normaliza la espera de
viaje. En el chat crea una propuesta revisable. Después de confirmar, compara
el estado anterior, escribe y verifica dentro de la misma transacción.

Herramientas: lectura de la flota, `acciones_flota.preparar` y
`database.aplicar_cambio_confirmado`. El adaptador MCP usa la misma construcción
y aplicación del cambio mediante `acciones_flota.ejecutar_autorizado`.

El chat reconoce «Poné ABC123 en Esperando viaje» y pedidos interrogativos
equivalentes como actualizaciones confirmables. Si el modelo selecciona activar
espera y omite velocidad, el asistente completa velocidad 0 antes de invocar la
Skill, conservando los minutos omitidos. Sin unidad identificada, las instrucciones
de ambos modelos indican pedir detalles (`modificacion`), sin elegir una unidad.

### Eliminar vehículo

Archivo: `skills_flota/eliminar.py`. Nombre invocable: `eliminar_vehiculo`.

Recibe la selección de una sola unidad, sin cambios de estado. Identifica la
unidad, prepara su baja y espera confirmación en el chat. Al aplicarla,
comprueba que la unidad no haya cambiado y verifica su ausencia. Cancelar no
modifica la flota. Los datos de ejemplo no reaparecen al reiniciar.

Herramientas: lectura actual, preparación de propuestas y eliminación
transaccional de la capa de datos. Reutiliza el ejecutor de escritura de la
Skill de gestión con un contrato que solo permite eliminar.

## Flujo de una solicitud

```text
Mensaje del operador
  -> asistente.py: valida entrada y lee contexto actual
  -> gemini_client.py u ollama_client.py: mensaje + catálogo + workflows
  -> Gemini o Gemma: selecciona skill, operación y argumentos estructurados
  -> asistente.py: comprueba alcance y compatibilidad skill/operación
  -> skills_flota.registro.invocar: valida input_schema y llama al ejecutor
  -> herramientas Python: leen o preparan un cambio
  -> validación de output_schema
  -> respuesta o propuesta revisable en el chat

Confirmar cambio
  -> skills_flota.confirmar: resuelve el token sin llamar al modelo
  -> comparación del estado + escritura + verificación en SQLite
  -> resultado estructurado y texto de confirmación
```

La invocación se realiza con un despachador Python a partir de la salida JSON
del modelo. No depende del protocolo nativo de function calling de un proveedor.
Las herramientas MCP son otro punto de entrada al mismo registro; el chatbot
no inicia un cliente MCP. Una herramienta expone una operación y la Skill
reúne propósito, contratos, procedimiento y ejecución reutilizable.

Para `fuera_de_alcance` y pedidos ambiguos `modificacion`, el modelo debe devolver
`skill: "ninguna"`. El asistente rechaza temas ajenos o pide más detalles sin
invocar una habilidad de escritura. Una selección incompatible, por ejemplo
`consultar_flota` junto a `eliminar`, es rechazada por Python.

## Reutilización demostrable

El registro tiene tres consumidores:

1. El chatbot: `asistente.py` llama a `invocar` después de validar la decisión
   del modelo. Las escrituras devuelven propuestas.
2. MCP: `servidor_mcp.py` conserva las seis herramientas públicas y adapta sus
   parámetros a las mismas Skills. El cliente debe verificar previamente que
   el usuario pidió la modificación. El canal MCP no requiere botones del chat.
3. Python/CLI: otro programa importa `invocar` y `confirmar`, sin depender del
   dashboard ni de Gemini. `python -m skills_flota demo` lo demuestra usando
   una base temporal.

El catálogo se obtiene con `python -m skills_flota catalogo` y contiene los
esquemas de entrada/salida y ejemplos. Las definiciones son objetos Python
versionados del paquete; no requieren un archivo `SKILL.md` ni frameworks de agentes.

## Verificación y límites

```powershell
python -m unittest -v test_configuracion.py test_asistente.py test_acciones_flota.py test_servidor_mcp.py test_skills_flota.py test_ollama_client.py test_multiagente.py test_escenario_flota.py test_datos_persistentes.py test_asignacion_viaje.py
```

Las pruebas usan bases temporales y respuestas simuladas del proveedor. Verifican
contratos, catálogo enviado al modelo, invocación efectiva del registro,
reutilización entre Python y MCP, reglas de alerta, confirmaciones, cancelación,
vencimiento, repetición y cambios concurrentes. Estas pruebas no garantizan la
interpretación semántica de un modelo real; eso se comprueba con consultas a
Gemini u Ollama y datos de prueba. `test_ollama_client.py` comprueba también
la selección de proveedor, ausencia de fallback a nube y confirmaciones locales.

Una demostración para la entrega puede mostrar:

1. El catálogo y la demo offline para identificar las tres Skills y sus resultados JSON.
2. «¿Qué vehículos están en alerta?» en el dashboard.
3. «Agregá DEMO123 a 0 km/h, detenido 0 minutos, esperando viaje» y revisar la propuesta.
4. Confirmar el alta y observar la unidad en la tabla.
5. «Actualizá DEMO123 a 60 km/h y 0 minutos detenido»; confirmar y comprobar que ya no espera viaje.
6. Pedir la baja, probar Cancelar y luego repetir para confirmar la eliminación.
7. «¿Cómo está el tiempo?» y «¿Cómo salió Boca?» para mostrar el rechazo de temas ajenos.
8. Elegir Asistente IA local y repetir una consulta y una propuesta con Gemma;
   comprobar que ambos proveedores invocan las mismas Skills.

Los pasos de escritura del dashboard deben realizarse deliberadamente con una
unidad de demostración. El comando `demo` ya ofrece una alternativa aislada.

Se mantiene una operación de escritura por vez y confirmaciones con duración
de cinco minutos. El sistema es local, sin autenticación, sin historial persistente
de auditoría y sin operaciones masivas. Cualquiera de los modelos puede interpretar mal un pedido;
la revisión de la propuesta permite al operador comprobar los datos antes de aplicar.

## Dos intérpretes, las mismas Skills

`prompt_agente.py` concentra el contrato de selección compartido.
`gemini_client.py` adapta el pedido a la API en la nube. `ollama_client.py`
convierte el mismo contrato a JSON Schema y lo envía al endpoint local de chat
con `format`, sin streaming y temperatura 0. Ambos reciben descripciones,
operaciones y workflows desde el mismo registro; el prompt local es más breve
y añade ejemplos ficticios de clasificación y extracción para orientar a Gemma.

La web conserva conversaciones separadas; solo se envía el historial del modo
seleccionado. Si falla Ollama no se invoca Gemini. Las confirmaciones no dependen
del proveedor y no consultan nuevamente a ningún modelo. Los datos persistidos
en la flota son compartidos por ambos modos, porque usan la misma SQLite.

La integración local sigue la [API oficial de chat](https://docs.ollama.com/api/chat)
y la [documentación de salidas estructuradas](https://docs.ollama.com/capabilities/structured-outputs).

## Selección multiagente: roles distintos, lectura compartida

El tercer modo del dashboard coordina dos roles en `multiagente.py`: Gemini es
coordinador de viajes y Gemma en Ollama es responsable de flota. Se inspira en
la separación entre agentes y habilidades compartidas de la clase «13-Multiagentes».
Ahora negocia una unidad y su precio para un viaje ficticio: Gemini busca precio
bajo y cercanía, mientras Gemma defiende el mínimo de la flota. Reemplaza la
selección inicial por mayor tiempo de espera.

El orquestador invoca `consultar_flota` con operación `esperando` a través del
mismo registro existente. No agrega Skills ni cambia sus contratos. Los modelos
reciben candidatos, pedido, historial propio y decisiones anteriores. Sus prompts
de rol son específicos y su salida JSON admite `proponer`, `aceptar`, `retirarse` o
`no_aplica`, junto con ID y precio entero (ambos null para cerrar sin oferta).
Los modos individuales conservan
el contrato original de selección de Skills en `prompt_agente.py`.

```text
Pedido en Selección multiagente
  -> consultar_flota: candidatos actuales esperando viaje
  -> escenario_flota: zonas ficticias, distancias y costos por ruta
  -> Gemini: oferta de unidad y precio, dentro del presupuesto
  -> Python: validar decisión, ID y precio
  -> Gemma: aceptación o contrapropuesta, respetando su mínimo
  -> Python: validar decisión, ID y precio
  -> repetir hasta tres rondas si no se acepta
  -> acuerdo: comprobar última oferta, ambos límites y releer candidatos
  -> gestionar_vehiculos: propuesta para marcar En viaje (sin escribir todavía)
  -> Confirmar cambio: asignación y verificación transaccional
```

El formulario «Viaje ficticio» define origen, destino y presupuesto entero
positivo, hasta 1000000. El escenario inicial es Centro → Norte con 9000 pesos
ficticios. Zona, `tarifa_base` y `precio_minimo` base están guardados por unidad
en SQLite. La migración inicial conserva los perfiles previos por ID una sola
vez; los reinicios respetan ediciones. Nuevas altas sin configuración usan
Centro/4000/3000. Las herramientas MCP de alta y actualización admiten los tres
parámetros opcionales y las consultas los devuelven. `escenario_flota.py` calcula
desde esos valores guardados, sin asignar perfiles durante la negociación.
La referencia es base + km de viaje × 800 + km al retiro × 400; el mínimo es
`precio_minimo` base guardado + km totales × 300. Son datos ficticios, sin GPS ni
precios reales. El mínimo cotizado se distingue del mínimo base del dashboard.

Los esquemas de Skills amplían `cambios` y los vehículos de salida con `zona`,
`tarifa_base` y `precio_minimo`. Los campos nuevos de entrada son opcionales para
conservar consumidores anteriores; los modelos reciben el esquema completo.
Se conserva el workflow de confirmación y se verifica concurrencia sobre todos
los campos persistidos. Zona debe pertenecer al catálogo; importes enteros de
1 a 1000000 y mínimo base no mayor que tarifa. Los mismos límites se controlan
en Python y SQLite. La tabla y tarjetas muestran esos valores y el asistente
puede consultarlos o proponer su actualización sin alterar campos omitidos.

Python permite ofertas del cliente por debajo del piso de la flota y ofertas de
la flota por encima del presupuesto: justamente esas diferencias motivan la
negociación. Cada rol debe respetar su propio límite. Aceptar exige la misma
unidad y precio de la última propuesta del otro agente y cumplir ambos límites,
incluso si ambos modelos coinciden. Propuestas iguales sin aceptación explícita
no se convierten automáticamente en acuerdo. Retirarse termina sin acuerdo.

El resultado contiene `estado`, `respuesta`, `dialogo`, `vehiculo_recomendado`,
`precio_acordado`, `solicitud`, `candidatos` y `ficticio`.
Los estados son `acuerdo`, `sin_acuerdo`, `sin_candidatos`, `no_aplica`,
`flota_cambio` e `incompleta`. Solo `acuerdo` incluye vehículo y precio acordado.
Un acuerdo incorpora también `propuesta.token`, creado por la Skill de gestión.
Al confirmar se activa `en_viaje`, desactiva `esperando_viaje` y reinician los
minutos detenido a 0, sin inventar velocidad. Sin confirmar la unidad no cambia.
La propuesta se compara con el candidato negociado y la confirmación comprueba
concurrencia otra vez. Cancelar o vencer conserva su disponibilidad previa.
El dashboard ofrece el filtro En viaje. Para liberar la unidad, el asistente
puede proponer «Dejá ABC123 esperando viaje», que finaliza su asignación.
La consulta `viajes` de `consultar_flota` lista asignaciones activas. El precio y
recorrido del acuerdo no se persisten como historial; solo el estado de la unidad.
El texto de las intervenciones lo genera Python desde las decisiones y datos;
no es una transcripción de prosa libre. Los errores conservan las intervenciones
válidas anteriores. Sin candidatos no se llama a los proveedores.

La conversación multiagente está separada de nube y local. Este modo usa
explícitamente la nube y envía su pedido, historial, candidatos y diálogo a ambos
proveedores. El presupuesto estructurado solo va a Gemini; los mínimos solo a
Gemma. Esto acota el contexto de cada rol, sin prometer confidencialidad: el
usuario puede mencionar esos límites en el mensaje y ambos son visibles en la
demo. Reutiliza transportes, límites y endpoint local fijo; no hay fallback
ni reintentos. Puede realizar hasta seis llamadas y el navegador espera hasta
450 segundos. No admite ubicaciones reales, capacidad ni horarios. Si el texto
pide otras condiciones de viaje, los modelos deben pedir ajustar el formulario;
su reconocimiento semántico depende del modelo. Disponibilidad y límites
económicos se validan en Python. No garantiza precio óptimo ni acuerdo.

`POST /api/asistente` admite un objeto opcional `solicitud` solo para
`proveedor: "multiagente"`, con `origen`, `destino` y `presupuesto`. Si se omite,
usa el escenario inicial. El endpoint de lectura `GET /api/escenario-negociacion`
devuelve zonas, parámetros y candidatos con costos; admite `origen` y `destino`
como query params. La web usa sus zonas y valores iniciales para cargar el
formulario compacto. El botón «Iniciar negociación» envía los campos al mismo
endpoint del chat; el listado previo de candidatos y costos no se muestra.

`test_multiagente.py` usa bases temporales y proveedores simulados: comprueba
acuerdo con precio, concesiones, ausencia de candidatos, retiro, tres rondas sin
acuerdo, presupuesto incompatible, límites económicos, decisiones inválidas,
contextos por rol, cambios concurrentes, ausencia de escrituras, reutilización
de la Skill, transporte y API HTTP. `test_escenario_flota.py` verifica distancias,
valores recibidos desde la base y costos por ambos tramos del viaje.
`test_datos_persistentes.py` cubre migración, reinicios, confirmación/cancelación,
validación, concurrencia y uso de la configuración guardada al negociar. No garantiza la
interpretación semántica de Gemini o Gemma reales.
