# RBH Tutor

Tutor AI adaptativo para niños de 1° a 5° de primaria en **lectura, escritura y
aritmética** — y, mientras tanto, en **carácter, mentalidad y liderazgo**.
Enseña con método socrático: guía con preguntas y pistas escalonadas, **nunca
regala la respuesta**. Aprende del niño sesión a sesión.

Nace del RFS **"The Primer"** de Y Combinator. Ver `ARCHITECTURE.md` para las
decisiones de diseño y su razón.

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
`ARCHITECTURE.md`.

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

---

## Dónde va cada cosa

| Necesito... | Va en |
|---|---|
| Cambiar **qué es** el tutor (valores, carácter, ADN) | `knowledge/product/constitucion_valores.md` **primero**, y de ahí al prompt |
| Cambiar cómo habla el tutor | `knowledge/prompts/tutor_persona.es.md` |
| Cambiar la escalera de pistas | `knowledge/prompts/socratic_playbook.es.md` |
| Cambiar los valores que el tutor vive | `knowledge/prompts/valores.es.md` |
| Agregar una habilidad al currículum | `knowledge/curriculum/*.yaml` |
| Cambiar cómo se calcula el dominio | `src/tutor/pedagogy.py` |
| Agregar un tool del tutor | `src/tutor/tools.py` |
| Cambiar dónde se guardan los datos | `src/tutor/storage.py` (solo ese archivo) |
| Cambiar de modelo de voz | `src/tutor/voice.py` (solo ese archivo) |
| Ajustar presupuestos o retención | `src/tutor/config.py` |
| Agregar un caso de prueba del método | `evals/parent_trust/` |
| Cambiar cómo se ve el panel del papá | `src/tutor/panel.py` (solo ese archivo) |
| Cambiar qué dice el reporte semanal | `knowledge/prompts/parent_companion.es.md` |

---

## Idioma

- **Contenido y prompts:** español. Los campos `en` existen en los YAML pero
  quedan vacíos hasta la fase de inglés.
- **Código:** nombres en inglés (`get_next_problem`), comentarios y docstrings en
  español.
- Los IDs de nodos del grafo **nunca se traducen** — son la llave estable.

---

## Comandos

```bash
# Entorno
python -m venv .venv && .venv/Scripts/activate
pip install -e ".[dev]"

# Tests (rápidos, sin red)
pytest

# Evals (consumen API)
python -m evals.runner
python -m evals.runner --suite parent_trust

# Construir el banco de ejercicios (una vez, por lote)
python -m scripts.build_exercise_bank
```

---

## Estado

**El circuito completo cierra**, de la voz del niño al panel del papá.

El niño habla → el tutor usa el banco y `check_answer` → la sesión se cierra →
el Analista escribe el dominio → el planificador de mañana arranca con la
evidencia de hoy → el reporte semanal lo cuenta → el papá lo lee en el panel.

- `curriculum.py`: carga y valida el grafo (rechaza ciclos, prerrequisitos
  colgados, IDs duplicados) y lo navega en ambas direcciones
- `pedagogy.py`: dominio, olvido, planificador sin techo, escalera socrática y
  **presunción de grado** (un niño de 2° no arranca contando hasta 100, ni se
  le reporta al papá un atraso que nadie midió)
- `storage.py`: `RepositorioSQLite` completo — WAL, transacciones atómicas,
  migraciones por `user_version`, idempotencia, retención, auditorías y reportes
- `tools.py`: `check_answer` (entiende números hablados en español, tolerante
  con la forma y estricto con el valor), `BancoDeSesion`, `request_camera`,
  `escalate_safety`
- `voice.py`: prompt de sesión, tools, fin de turno por edad, token con la
  configuración **atada** (candado #1), voz `Leda` en `es-CO` y transcripción
  de entrada con idioma fijo + sesgo aritmético
- `session.py`: `Orquestador` — abre (precarga + presupuesto + token), registra
  turnos con los dos niveles de seguridad, cierra y encola para el Analista
- `pipeline.py`: Analista (señales y auditoría en dos llamadas — §18), Vigilante,
  métricas en código, reporte al papá verificado contra la fuente, y las tareas
  que drenan las dos colas
- `api.py`: plano de control + el panel del papá server-rendered (`panel.py`)
- `web/`: la interfaz de voz del niño (React + Vite)
- `evals/`: 30 casos en las 4 suites de YC — **30/30**, estable en dos corridas
- `matematicas.yaml`: 13 habilidades de 1° a 3° con doble anclaje
  ⚠️ Referencias DBA **provisionales** — verificar contra el MEN
- 267 tests en verde

```
python -m scripts.demo_planificador     # el cerebro
python -m scripts.demo_persistencia     # el ciclo completo
python -m scripts.demo_verificacion     # check_answer con voz
python -m scripts.verificar_gemini      # los 2 supuestos contra la API real
python -m scripts.procesar_pendientes   # drena la cola del Analista
python -m scripts.generar_reportes      # el reporte semanal al papá
```

**Arquitectura de voz verificada (2026-08-17):** `live_connect_constraints`
funciona (el navegador no puede cambiar el prompt) y tool calling anda. El
modelo `gemini-3.1-flash-live-preview` **solo devuelve AUDIO** — la entrada sí
acepta texto.

**Lo que falta es evidencia, no código:** una sesión de voz con audio real que
confirme que la transcripción arreglada corrige el "dos" → "32", y la medición
de `check_answer` en la consola del navegador. Ver `PENDIENTE.md`.

Ver `ARCHITECTURE.md` §17 para el plan de fases.

---

## Lección aprendida (fase 7)

**El schema pesa más que el prompt.** Toda esta tanda salió de agregar un
boolean a `AuditoriaCumplimiento`: `curriculum_fidelity` cayó de 4/4 a 0/4 sin
que nada del currículum se tocara. El modelo devolvía la auditoría impecable y
`observaciones: []`.

Cuatro cosas que quedaron, todas medidas:

1. **Un schema tiene presupuesto de atención, y se reparte.** Medido:
   sin campos extra 4/4 · con un campo trivial 3/4 · con un campo que exige
   juicio 0/4. Cuando dos trabajos distintos comparten una salida estructurada,
   **el que pierde es el que no estás mirando**. La salida fue partir el Analista
   en dos llamadas (`ARCHITECTURE.md` §18).
2. **El síntoma miente.** "Observaciones vacías" se lee como "el prompt está
   mal", y se pierde una tarde corrigiendo el prompt. Ante una regresión en evals
   después de tocar un modelo Pydantic, la primera prueba es **volver el modelo a
   HEAD dejando el prompt nuevo**: separa las dos causas en una corrida.
3. **Un baseline con una variable a medias no es un baseline.** La primera
   medición se hizo con el `models.py` nuevo y el prompt viejo — la peor de las
   tres combinaciones — y dio 0/4, lo que parecía probar que la regresión era
   preexistente. No lo era.
4. **Una descripción de campo enfática puede colgar al modelo.** Un
   `description` largo y en mayúsculas ("OBLIGATORIO…") hizo que Haiku entrara en
   un loop generando `‌` hasta agotar `max_tokens`, y el JSON truncado se
   descartaba entero. La misma regla, dicha corta y en tono neutro: 4/4 estable
   en tres corridas. En salida estructurada, **el campo se describe, no se grita.**

Y una que es de método, no de modelos: cuando el mismo síntoma vuelve tres veces
con arreglos distintos, el arreglo está en el lugar equivocado. `habilidad_id`
se resolvió cuando se dejó de pedirle al modelo lo que el código ya sabía — si
la sesión trabajó una sola habilidad, no había nada que inferir.

---

## Lección aprendida (fase 6)

Dos datos se estaban **inventando solos**, en direcciones opuestas, y ninguno
lo detectaron los tests:

- `cumplimiento_metodo` devolvía `1.0` cuando no había ni una sesión auditada:
  el reporte iba a decirle al papá que el método se sostuvo en el 100% de las
  sesiones, sin haber mirado ninguna.
- `grado_de_trabajo` devolvía 1 para un niño de 2° del que no había evidencia,
  porque contaba nodos de 1° que nunca se midieron. El reporte le decía al papá
  que su hijo trabaja por debajo de su grado.

Los dos son el mismo error: **tratar la ausencia de evidencia como evidencia.**
Lo detectó correr el reporte de verdad y leerlo, no la suite.

→ Cuando un número va a llegarle al papá, `None` es una respuesta válida y hay
que dejar que llegue hasta la superficie. "No lo medimos" se dice; no se
completa con un default que parece un dato.

Y una tercera, de la misma corrida: **la verificación estricta también hace
daño si no distingue lo que se afirma de lo que se propone.** `verificar_reporte`
tumbó un reporte correcto porque la sugerencia para casa decía "este dinosaurio
pesaba 350 kilos". Un verificador que rechaza lo válido termina dejando al papá
sin nada, que es el resultado que quería evitar.

---

## Lección aprendida (fase 4)

Hay **dos** definiciones del nodo de currículum: `knowledge/curriculum/schema.json`
(valida los YAML) y `models.Habilidad` (lo que usa el código). Pueden separarse
sin que nada avise — pasó con `verificable_en_codigo`, que vivió solo en el JSON
desde la fase 0: el YAML lo declaraba, jsonschema lo validaba, y Pydantic lo
descartaba en silencio.

→ `test_schema_json_y_el_modelo_pydantic_no_se_desincronizan` compara los dos
conjuntos de campos. **Al agregar un campo hay que tocar los dos archivos.**

---

## Lección aprendida (fase 2)

Los tests de `pedagogy.py` verificaban comportamiento **relativo** ("decae", "lo
firme decae más lento") y todos pasaban — pero el olvido estaba calibrado diez
veces más rápido de lo real: un niño "perdía" contar hasta 100 en dos semanas.

Lo detectó la **demo**, no los tests.

→ Para cualquier modelo con constantes numéricas, escribir también tests de
**calibración absoluta** ("dos semanas no borran lo dominado", "las vacaciones
desgastan pero no borran") y correr una simulación con datos realistas antes de
darlo por bueno.
