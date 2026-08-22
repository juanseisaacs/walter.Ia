# RBH Tutor

Tutor AI adaptativo para niños de 1° a 5° de primaria en **lectura, escritura y
aritmética** — y, mientras tanto, en **carácter, mentalidad y liderazgo**.
Enseña con método socrático: guía con preguntas y pistas escalonadas, **nunca
regala la respuesta**. Aprende del niño sesión a sesión.

Nace del RFS **"The Primer"** de Y Combinator.

**Los cuatro documentos, y qué contesta cada uno:**

| Archivo | Contesta |
|---|---|
| `CLAUDE.md` (este) | **Cómo trabajar acá.** Las reglas y dónde va cada cosa |
| `ARCHITECTURE.md` | **Qué se decidió y por qué.** Si no está ahí, no se decidió |
| `BITACORA.md` | **Por qué las reglas son las que son.** Lo que se rompió y qué costó |
| `PENDIENTE.md` | **Dónde retomar.** Se poda, no solo se agrega |

---

## El norte

Toda decisión se justifica contra uno de estos 5 criterios. Si una feature no
sirve a ninguno, no entra al MVP.

1. **Curriculum fidelity** — rigor y alineación a estándares reconocidos
2. **Safety** — protección real de menores
3. **Longitudinal memory** — el tutor conoce al niño y crece con él
4. **Parent trust** — el papá confía porque puede verificar
5. **Formación de carácter** — el tutor forma la persona, no solo la
   competencia académica

Los cuatro primeros son de YC. El quinto es nuestro, y viene de la
**Constitución** (`knowledge/product/constitucion_valores.md`): diez pilares
valóricos, mentalidad de progreso, liderazgo y catorce líneas rojas.

**La Constitución manda sobre el producto.** Si una oportunidad de negocio
choca con ella, gana ella — o se reforma con decisión fundadora explícita,
nunca por omisión. Ver `ARCHITECTURE.md` §18 para qué se adoptó, qué se
comprimió y las tres divergencias registradas.

Y una regla de forma que vale tanto como el contenido: **los valores no se
predican.** No hay lección de valores; hay un tutor que es así en cada turno.
Si el tutor sermonea, dejó de formar.

---

## Reglas duras

Estas no se negocian. Cada una viene de una decisión razonada en
`ARCHITECTURE.md`, y varias de un bug que costó caro (`BITACORA.md`).

### Latencia
- **La respuesta hablada del tutor nunca espera a nuestra infraestructura.**
  Un tool call es la excepción explícita (ocasional, ~100ms). Lo que no se
  admite es el backend en el camino de cada palabra.
- **El audio va directo del navegador a Gemini.** El backend controla, no
  transporta. Ver `ARCHITECTURE.md` §10.
- El **Vigilante corre en paralelo** — jamás bloquea la respuesta del tutor.
- Los ejercicios se **precargan al inicio** de la sesión, nunca durante.
- El prompt de sesión se mantiene flaco: persona + playbook + valores +
  seguridad + resumen compacto + nodo actual. Nunca el currículum entero ni la
  historia completa. Hay un **techo con test** — subirlo es una decisión, no un
  descuido.

### Determinismo
- **La aritmética jamás la valida un modelo.** `check_answer` es código puro.
- El planificador ("¿qué sigue?") es **código**, no un agente.
- El decaimiento de dominio es una **fórmula**, no un juicio.
- **Ningún agente afirma nada que no esté en los datos.** El reporte al papá se
  verifica en código contra la fuente.

### Seguridad
- **El Vigilante nunca se fusiona con el Tutor.** Contexto limpio, no manipulable.
- El Vigilante clasifica **ventanas de 3-4 turnos**, no turnos sueltos.
- El prefiltro en código corre turno a turno, a 0ms.
- Hay **dos caminos independientes** a la alarma: el Vigilante y `escalate_safety`.

### Producto
- **Ayudar con la tarea ≠ hacer la tarea.** La tarea es materia prima para
  tutoría socrática. Si se cruza esa línea, somos lo que YC dice que fracasa.
- El modo Pedido exige método socrático **más estricto**, no más laxo.
- **SIN TECHO: el grado escolar nunca limita.** Si el niño tiene los
  prerrequisitos, se le ofrece el contenido — tenga la edad que tenga. Ningún
  filtro puede descartar una habilidad por `grado_sugerido`; el planificador
  decide por dominio. Cuando va adelantado, el tutor lo sabe (no lo frena) y el
  papá se entera (va en el reporte).
- **Se explica derecho solo lo convencional.** El nombre del signo o cómo se
  escribe la eñe se dicen y se sigue: nadie los deduce razonando. El resultado
  del ejercicio en curso, jamás. La duda se resuelve con *¿podría llegar solo
  si le pregunto bien?* Ver `ARCHITECTURE.md` §18.
- **El elogio inflado está prohibido.** "Eres un genio", "eres el mejor", "eres
  increíble" — nunca. No por exagerados: porque le enseñan al niño que su valor
  depende de rendir. Reconocimiento específico y creíble, o silencio.
- **La dignidad es incondicional; la confianza se gana.** El niño vale siempre,
  le salga o no. Su confianza en sí mismo no se declara: se construye con
  logros reales y no se afirma sin evidencia.

### Datos
- **Las transcripciones se borran a los N días.** El activo es la ficha
  estructurada, no la conversación cruda.
- **Toda sesión tiene techo** de tiempo y de tokens. También hay techo diario y
  mensual por niño.
- El `session_id` es **llave de idempotencia**: una sesión nunca se analiza dos
  veces.

### Código
- **Los prompts son datos.** Viven en `knowledge/prompts/*.md` y se cargan en
  runtime. Cambiar el comportamiento de un agente **no debe tocar Python**.
- **Un archivo se parte en carpeta a las ~400 líneas.** No antes. Se organiza
  cuando duele, no por anticipación.
- Los módulos puros (`models`, `curriculum`, `pedagogy`, `storage`, `tools`)
  **no hacen red ni I/O externo**. Si un cambio los obliga a hacerlo, el diseño
  está mal.
- **Un contrato entre Python y TypeScript necesita un test que lo cruce.** Un
  enum declarado de un lado y consumido del otro se separa sin que nada avise:
  el compilador no puede verlo porque son dos lenguajes. Ver
  `tests/test_contrato_pizarra.py`.
- **La técnica dice CÓMO explicar, nunca si dar la respuesta.** El motor de
  técnicas elige la forma de enseñar; el playbook socrático es innegociable y
  entra antes en el prompt. Una técnica que lo contradiga la rechaza el test.
- **Ninguna técnica entra sin bloque de evidencia**, con fuente, respaldo y
  `adaptacion_es` — si la evidencia viene en inglés, hay que decir si transfiere.
  `efecto_verificado` va en `false` mientras nadie lo contraste con el original.
- **Los veredictos del método se encadenan.** Cada auditoría queda anotada en
  `data/audits/cadena.jsonl` con el hash de la anterior. Editar un veredicto
  viejo rompe la cadena y `verificar_cadena` dice dónde. Es lo que convierte el
  porcentaje del panel en algo que el papá puede **verificar**, no creer.

---

## Dónde va cada cosa

| Necesito... | Va en |
|---|---|
| Cambiar **qué es** el tutor (valores, carácter, ADN) | `knowledge/product/constitucion_valores.md` **primero**, y de ahí al prompt |
| Cambiar cómo habla el tutor | `knowledge/prompts/tutor_persona.es.md` |
| Cambiar la escalera de pistas | `knowledge/prompts/socratic_playbook.es.md` |
| Cambiar los valores que el tutor vive | `knowledge/prompts/valores.es.md` |
| Agregar una habilidad al currículum | `knowledge/curriculum/*.yaml` |
| Cambiar qué del español se verifica en código | `src/tutor/lengua.py` |
| Cambiar cómo se escriben los ejercicios de lenguaje | `knowledge/prompts/exercise_generator_lengua.es.md` |
| Cambiar con qué materia arranca un niño nuevo | `pedagogy.ORDEN_DE_MATERIAS` |
| Agregar un dibujito a la pizarra | `web/src/pizarra/emojis.ts` |
| Agregar o cambiar una **forma de enseñar** | `knowledge/tecnicas/*.yaml`. Van de a pares rivales, y ninguna entra sin bloque de evidencia |
| Cambiar cómo se calcula el dominio | `src/tutor/pedagogy.py` |
| Agregar un tool del tutor | `src/tutor/tools.py` **y** el `case` en `web/src/voz/useTutor.ts`. El test de contrato falla si se hace solo uno |
| Cambiar dónde se guardan los datos | `src/tutor/storage.py` (solo ese archivo) |
| Cambiar de modelo de voz | `src/tutor/voice.py` (solo ese archivo) |
| Ajustar presupuestos o retención | `src/tutor/config.py` |
| Cambiar cómo le habla el tutor según el grado | `pedagogy.REGISTRO_POR_GRADO` |
| Cambiar el año escolar (fechas, calendarios) | `pedagogy._TRAMOS` y `GUIA_POR_MOMENTO` |
| Agregar un caso de prueba del método | `evals/parent_trust/` |
| Cambiar cómo se ve el panel del papá | `src/tutor/panel.py` (solo ese archivo) |
| Cambiar qué dice el reporte semanal | `knowledge/prompts/parent_companion.es.md` |
| Agregar un tipo a la pizarra | `voice.py` (el enum) **y** `web/src/pizarra/desdeElTutor.ts` (el handler). El test de contrato falla si se hace solo uno |

---

## Idioma

- **Contenido y prompts:** español. Los campos `en` existen en los YAML pero
  quedan vacíos hasta la fase de inglés.
- **Código:** nombres en inglés (`get_next_problem`), comentarios y docstrings en
  español.
- Los IDs de nodos del grafo **nunca se traducen** — son la llave estable.

---

## Cómo se verifica

**Ninguna afirmación de "funciona" vale sin haber corrido la que corresponda.**

| Comando | Qué cubre | ¿Gasta cuota? |
|---|---|---|
| `pytest` | 589 tests: lógica, agentes con cliente falso, contratos. Sin red | no |
| `ruff check .` | Lint. Tiene que quedar en cero — `F811` ya escondió un test que no corría | no |
| `python -m scripts.verificar_cadena` | Que ningún veredicto del método se haya tocado. `--sembrar` ancla los que ya existían | no |
| `cd web && npm test` | 94 tests del front: audio, micrófono, pizarra | no |
| `cd web && npm run build` | Que TypeScript compile. Necesario para hablar con el tutor | no |
| _(automático)_ | Un **hook** valida `knowledge/` en cuanto se edita: currículum → `test_curriculum`, prompts → `test_voice`. Ver `.claude/settings.json` y `scripts/hook_validar_knowledge.py` | no |
| `python -m scripts.demo_planificador` | El cerebro con datos realistas. Detectó lo que la suite no vio (fase 2) | no |
| `python -m scripts.demo_persistencia` | El ciclo completo, de la sesión al dominio | no |
| `python -m scripts.demo_tecnicas` | El motor de técnicas sesión a sesión, con tres niños simulados | no |
| `python -m scripts.demo_verificacion` | `check_answer` con respuestas habladas | no |
| `python -m scripts.verificar_tokens` | Que el prompt de sesión siga bajo el techo | no |
| `python -m scripts.build_exercise_bank` | Reconstruye el banco. El validador impide voseo y enunciados largos — eso no lo sostiene el prompt | **sí** |
| `python -m evals.runner` | Las 4 suites de YC, 48 casos, contra el modelo real | **sí** |
| `python -m scripts.verificar_gemini` | Los supuestos de la Live API contra la API real | **sí** |
| `python -m scripts.verificar_vision` | ¿El tutor VE o completa? Le muestra lo que no puede adivinar | **sí** |
| `python -m scripts.e2e_voz` | La pantalla del niño en un navegador de verdad, con sesión Live real. `--sin-voz` hace la mitad que no cuesta nada | **sí** |
| `python -m scripts.procesar_pendientes` | Drena la cola del Analista **y aplica la retención**. La purga corre siempre, aunque la cola esté vacía o falte la llave. `--seco` la calcula sin borrar | **sí** |
| `python -m scripts.generar_reportes` | El reporte semanal al papá | **sí** |

Y una que no es un comando: **abrir `data/tutor.db` y leer las filas.** Cuatro
de los siete bugs de `BITACORA.md` los destapó mirar el dato, no la suite.

### Cómo se levanta para HABLAR con el tutor

```bash
cd web && npm run build && cd ..        # una vez, o tras tocar la interfaz
python -m uvicorn tutor.api:app --port 8000
```

Y se abre **http://localhost:8000**. La app del niño y la API salen del mismo
proceso: un origen, sin proxy.

⚠️ **`npm run dev` NO se usa para hablar con el tutor.** Sirve para trabajar en
la interfaz y nada más. El servidor de desarrollo entrega React sin minificar y
los módulos sueltos; esta app procesa audio PCM en tiempo real en el hilo del
navegador, y con el build de desarrollo el niño siente que el tutor "se va a
buscar la respuesta y vuelve". Medido el 19/08: el backend responde en **4 ms**
—veinte veces por debajo del presupuesto— así que cuando la sesión se siente
lenta, **el sospechoso no es el backend**. Ver `ARCHITECTURE.md` §9.

---

## Al terminar algo

Correr la verificación que corresponda, y **decir el resultado tal cual salió.**

- Si algo falla, se dice que falla, con su salida.
- Si algo quedó sin hacer, se dice cuál y por qué.
- Si una medición contradice algo que se afirmó antes, se dice.
- Si el bug tenía otra causa que la que se supuso primero, se dice la real.

**Un "listo" sin verificación no vale.** Y si cambió algo duradero —una
decisión, una trampa nueva, un pendiente que se cierra— actualizar
`ARCHITECTURE.md`, `BITACORA.md` o `PENDIENTE.md`, según cuál sea.

---

## Estado

**El circuito completo cierra**, de la voz del niño al panel del papá.

El niño habla → el tutor usa el banco y `check_answer` → la sesión se cierra →
el Analista escribe el dominio → el planificador de mañana arranca con la
evidencia de hoy → el reporte semanal lo cuenta → el papá lo lee en el panel.

| | |
|---|---|
| Habilidades (1° a 5°) | **78** — 54 de matemáticas, 13 de lectura, 11 de escritura |
| Ejercicios validados en banco | **2.052** — ~26 por habilidad, ninguna vacía |
| Tests | **589** de Python + **94** del front, en verde. Lint en cero |
| Casos de eval en las 4 suites de YC | **48** |
| Sesiones de prueba corridas | **62**, todas nuestras — ningún niño externo todavía |

El detalle de qué hace cada módulo está en `README.md`; las decisiones y su
razón, en `ARCHITECTURE.md`.

**Arquitectura de voz verificada (2026-08-17):** `live_connect_constraints`
funciona (el navegador no puede cambiar el prompt) y tool calling anda. El
modelo `gemini-3.1-flash-live-preview` **solo devuelve AUDIO** — la entrada sí
acepta texto.

**Lo que falta es evidencia, no código.** Ver `PENDIENTE.md` y
`ARCHITECTURE.md` §17 para el plan de fases.
