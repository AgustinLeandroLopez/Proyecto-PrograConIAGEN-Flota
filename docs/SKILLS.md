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

Recibe `agregar` o `actualizar`, selección de una unidad y campos de cambio.
Valida datos y unicidad, conserva valores omitidos y normaliza la espera de
viaje. En el chat crea una propuesta revisable. Después de confirmar, compara
el estado anterior, escribe y verifica dentro de la misma transacción.

Herramientas: lectura de la flota, `acciones_flota.preparar` y
`database.aplicar_cambio_confirmado`. El adaptador MCP usa la misma construcción
y aplicación del cambio mediante `acciones_flota.ejecutar_autorizado`.

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
python -m unittest -v test_configuracion.py test_asistente.py test_acciones_flota.py test_servidor_mcp.py test_skills_flota.py test_ollama_client.py
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
