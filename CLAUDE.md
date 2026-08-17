# RBH Tutor

Tutor AI adaptativo para niños de 1° a 5° de primaria en **lectura, escritura y
aritmética**. Enseña con método socrático: guía con preguntas y pistas
escalonadas, **nunca regala la respuesta**. Aprende del niño sesión a sesión.

Nace del RFS **"The Primer"** de Y Combinator. Ver `ARCHITECTURE.md` para las
decisiones de diseño y su razón.

---

## El norte

Toda decisión se justifica contra uno de los 4 criterios de YC. Si una feature no
sirve a ninguno, no entra al MVP.

1. **Curriculum fidelity** — rigor y alineación a estándares reconocidos
2. **Safety** — protección real de menores
3. **Longitudinal memory** — el tutor conoce al niño y crece con él
4. **Parent trust** — el papá confía porque puede verificar

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
- El prompt de sesión se mantiene flaco: persona + playbook + resumen compacto +
  nodo actual. Nunca el currículum entero ni la historia completa.

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
| Cambiar cómo habla el tutor | `knowledge/prompts/tutor_persona.es.md` |
| Cambiar la escalera de pistas | `knowledge/prompts/socratic_playbook.es.md` |
| Agregar una habilidad al currículum | `knowledge/curriculum/*.yaml` |
| Cambiar cómo se calcula el dominio | `src/tutor/pedagogy.py` |
| Agregar un tool del tutor | `src/tutor/tools.py` |
| Cambiar dónde se guardan los datos | `src/tutor/storage.py` (solo ese archivo) |
| Cambiar de modelo de voz | `src/tutor/voice.py` (solo ese archivo) |
| Ajustar presupuestos o retención | `src/tutor/config.py` |
| Agregar un caso de prueba del método | `evals/parent_trust/` |

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

**Fase 4 completa** — los 4 tools listos.

- `curriculum.py`: carga y valida el grafo (rechaza ciclos, prerrequisitos
  colgados, IDs duplicados) y lo navega en ambas direcciones
- `pedagogy.py`: dominio, olvido, planificador sin techo, escalera socrática
- `storage.py`: `RepositorioSQLite` completo — WAL, transacciones atómicas,
  migraciones por `user_version`, idempotencia y retención
- `tools.py`: `check_answer` (entiende números hablados en español, tolerante
  con la forma y estricto con el valor), `BancoDeSesion`, `request_camera`,
  `escalate_safety`
- `matematicas.yaml`: 13 habilidades de 1° a 3° con doble anclaje
  ⚠️ Referencias DBA **provisionales** — verificar contra el MEN
- 118 tests en verde

```
python -m scripts.demo_planificador    # el cerebro
python -m scripts.demo_persistencia    # el ciclo completo
python -m scripts.demo_verificacion    # check_answer con voz
```

**Pendiente conocido:** `madurez_vinculo` nunca sube — lo incrementa el Analista,
que llega en la fase 6. Hasta entonces el tutor siempre cree que conoce poco al
niño.

Próximo: **fase 5** — `voice.py` + `session.py`: el tutor en vivo.

Ver `ARCHITECTURE.md` §17 para el plan de fases.

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
