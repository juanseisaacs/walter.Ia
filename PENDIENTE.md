# Pendiente — retomar acá

_Última actualización: 2026-08-19, cierre del día._

## ⚡ Latencia — lo hecho el 20/08 y lo que queda

Tres sesiones reales. El niño preguntó *"¿por qué te demoraste tanto?"* en su
primer turno. Se midió todo y se arregló lo medible (`ARCHITECTURE.md` §9):

- Onboarding, primera pantalla: **3.590 ms → 5 ms**
- Onboarding, cada turno: **7.170 ms → ~3.600 ms** (las dos llamadas iban en fila)
- Abrir sesión de voz: **1.010 ms → ~380 ms** (el cliente de Google se rearmaba)
- Silencio de fin de turno, 7-8 años: **1.500 ms → 900 ms**

**Lo que falta probar con un niño de verdad:** que 900 ms de silencio no lo corte
mientras piensa. Si lo corta, se sube `config.SILENCIO_FIN_TURNO_MS` y nada más —
está aislado ahí a propósito.

**Lo más grande que queda, ya medido:** el turno del onboarding sigue costando
~3,5 s de modelo con la pantalla quieta. **Streaming** pondría las primeras
palabras a ~600 ms sin bajar el total. Requiere SSE en la API y un cambio en el
front.

**La deuda #1 del prompt SE PAGÓ el 20/08.** Base de 36,2 → **30,4 KB**; peor
caso de 40,995 → **34,9 KB**. Se movió el porqué a `knowledge/product/` y se
dejaron las reglas: `tutor_persona` 11.911 → 7.792, `socratic_playbook` 12.132 →
8.935. Los techos bajaron a 36.000 y 35.000 en el mismo movimiento, y hay un
test nuevo —`test_ninguna_regla_se_cae_al_adelgazar_el_prompt`— que lista las 24
promesas del producto y falla si un recorte se lleva una por delante.

---

## ⏭️ Para retomar mañana — en este orden

**1. Probar la velocidad.** Es lo único que quedó pendiente de sentir:

```bash
python -m uvicorn tutor.api:app --port 8000     # y abrir http://localhost:8000
```

Debería ir como la noche del 18. Si vuelve a sentirse lento, el backend NO es el
sospechoso: está medido en 4 ms (`ARCHITECTURE.md` §9). Lo primero a revisar es
que estés en `http://localhost:8000` y no en el `5173` de `vite dev`.

**2. Recargar créditos de Anthropic.** Se agotaron el 19/08 a mitad de la
verificación. Bloquea al Analista, al Vigilante y a las evals — **no** al tutor
de voz, que corre sobre Gemini.

**3. Verificar dos cosas que quedaron escritas y sin comprobar** (las dos
necesitan la llave):

```bash
python -m scripts.procesar_pendientes   # ¿el Analista ya atribuye bien la habilidad?
python -m evals.runner                  # ¿41/41 sigue en pie?
```

- Del **Analista** se confirmó que ya no inventa el `habilidad_id` y que detecta
  las señales (8 en una sesión de 9 min). Lo que falta comprobar es el último
  ajuste: que cuando la sesión no pasó por el banco, **sí** atribuya en vez de
  dejar todo en `null`.
- Las **evals** no corren desde que cambió `session_analyst.es.md` y desde que
  `contexto_escolar` entró a `PerfilPersonal`, que es parte de la salida
  estructurada del Analista — la operación que la fase 7 marcó como la más cara.
  Si bajan, el primer experimento es el de esa lección: volver `models.py` a HEAD
  dejando el prompt nuevo, para separar las dos causas en una corrida.

**4. Limpiar la ficha de Juan.** Tiene `mat.suma.sin_reagrupacion` en 0.21
inventado por el Analista viejo (ver abajo). Son datos falsos en la ficha de un
niño: conviene borrar ese registro antes de que llegue a un reporte.

---

## 🐛 Lo que se encontró probando en vivo el 19/08

Primera sesión de voz larga con un niño real (9 min, 22 turnos). Tres cosas, y
ninguna era la que parecía:

1. **"Se siente lento".** No era el backend —4,2 ms el tool, 5,4 ms el turno—
   sino que se estaba corriendo `vite dev` en vez del build. Arreglado montando
   `web/dist` en la API. `ARCHITECTURE.md` §9.
2. **El Analista inventaba la habilidad.** Sin banco recibía lista vacía de
   candidatos y devolvía un id plausible en vez de `null`: 56+38 llevando una
   decena quedó grabado como `sin_reagrupacion`. Arreglado.
3. **El tope de señales del Analista no existía.** El código lo daba por hecho;
   el prompt no lo decía. La primera sesión larga reventó `max_tokens`, el JSON
   llegó cortado y la sesión entera se descartaba. Arreglado (12 señales).

Y una que sigue abierta: **el tutor nunca llamó a `get_next_problem`** (0 veces
en 22 turnos) teniendo 10 ejercicios validados de `mat.suma.con_reagrupacion`,
que era exactamente lo que el niño necesitaba. Improvisó todo. `modo: guiado`
aunque el niño dijo "tengo una tarea" — no hay forma de que la sesión se abra en
`pedido`. Es el próximo hueco de producto.

## 🔴 LO ÚNICO QUE IMPORTA AHORA — cinco niños que no sean nuestros

El cuello de botella dejó de ser técnico. El circuito completo cierra y está
verificado: voz → banco → `check_answer` → dominio → reporte → panel, más la
cámara. Lo que falta es **evidencia de que alguien lo usa y vuelve**.

En la base hay **2 niños, los dos de prueba, y 29 sesiones todas de depuración**.
La más larga duró 7 minutos, contra un modelo de negocio que asume 20–30 diarios.

Tres cosas se miden en esa semana, y ninguna se puede simular:

1. **¿Vuelve un niño sin que se lo pidan?** Es el dato que ningún competidor
   tiene y que ninguna feature reemplaza.
2. **¿Aprende?** Todo el sistema mide dominio y nadie verificó que ese número
   corresponda a aprendizaje real. Un pre/post simple lo responde.
3. **¿Aguanta 20 minutos?** Un niño de 7 se distrae, contesta con monosílabos y
   se levanta. Nada de eso apareció todavía porque el único usuario fue RBH.

⚠️ Construir features nuevas antes de esto es sumar superficie sobre una
hipótesis sin validar. Lo de abajo sigue siendo cierto y sigue pendiente — pero
se ordena solo cuando exista ese dato.

## 🟡 Pendientes IMPORTANTES — decididos, en fila, no descartados

Los dos salen de la base académica del MEN (`ARCHITECTURE.md` §19). No se
hicieron porque son **decisiones de producto**, no huecos técnicos: nadie debería
tomarlas por el fundador.

### 1. Pruebas Saber 3° y 5° (ICFES)

El Estado evalúa al final de cada ciclo: **Saber 3°** (lenguaje y matemáticas) y
**Saber 5°** (suma ciencias naturales y competencias ciudadanas). El estilo es de
competencias —interpretar, argumentar, proponer—, no de memoria.

- **Qué costaría:** peso extra del planificador en 3° y 5° (comprensión lectora y
  problemas con datos en tablas), más un párrafo en `parent_companion.es.md`.
- **El límite lo pone la propia fuente:** integrar el formato de pregunta con
  naturalidad, **sin simulacros y sin generar ansiedad**. Un tutor que prepara
  para un examen deja de ser el tutor que describe la Constitución.
- **Por qué importa:** es el argumento más fuerte que existe frente a un papá
  colombiano, y llega justo cuando el niño está en el grado que se evalúa.

### 2. Abrir las cinco áreas

Hoy somos lectura, escritura y aritmética. La Ley 115 art. 23 define nueve áreas
obligatorias, y el documento identifica **cinco** que un tutor conversacional
puede enseñar y evaluar: matemáticas, lengua castellana, inglés, ciencias
naturales y ciencias sociales (más tecnología como apoyo transversal).

- **Qué costaría, en concreto:** el patrón de `id` en `schema.json` (hoy
  `^(mat|lec|esc)\.`), el enum `models.Materia`, un YAML por área, el banco de
  ejercicios, el planificador y las 4 suites de evals.
- **Ojo con el anclaje:** solo hay DBA oficiales para lenguaje, matemáticas,
  ciencias naturales, ciencias sociales e inglés. **Tecnología no tiene DBA ni
  EBC** — su progresión saldría de la Guía 30, y eso se declara, no se disimula.
- **Y la trampa conocida:** los DBA de las tres áreas nuevas **no están
  verificados**. La única fuente que los tiene es la que resultó estar corrida un
  grado (`FUENTES.md` §2.6). Abrir un área empieza por descargar su PDF del MEN.

---

## 🟠 Deuda abierta #1 — adelgazar el prompt de sesión

Apareció el 19/08 y está medida: la base del prompt (persona 11,3 KB + playbook
11,2 + valores 6,9 + safety 6,7) son **36,2 KB**, y el peor caso real —primera
sesión de un niño que llega con tarea— llega a **40,0 KB**. El techo del test
subió a 41 KB como decisión escrita, pero el número real que importa es la
**latencia de la primera frase**, no el costo (~$0,20/mes).

Con ese desglose, decidir qué sale es media hora. Los dos candidatos obvios son
`tutor_persona` y `socratic_playbook`, que juntos son 22,5 KB — el 62 % del total.

---

## Estado: el circuito completo cierra, y está verificado salvo la voz

**341 tests en verde. Evals 41/41**, en la última corrida (⚠️ las evals no se
han vuelto a correr desde que cambió `session_analyst.es.md` el 19/08).

> Los números decían 267 y 30/30 hasta el 2026-08-18: quedaron viejos cuando
> dos sesiones de Claude Code trabajaron en paralelo y una pisó el `CLAUDE.md`
> de la otra. El trabajo no se perdió — solo el conteo.

El recorrido entero funciona con datos reales de Juan:

    la sesión se cierra
      → el Analista escribe el dominio        ✔ verificado en la base
      → el planificador arranca con evidencia ✔ grado 2, sin techo
      → el reporte semanal lo cuenta          ✔ generado y verificado en código
      → el papá lo lee en el panel            ✔ abierto contra el servidor real

Lo único que **no** se probó de punta a punta es la voz con audio.

---

## 🔴 PRIORIDAD ÚNICA — Una sesión de voz real

Es lo único pendiente que no se puede hacer sin hablar. Todo lo demás está
verificado. Tres cosas se miden en la misma sesión:

1. **Que "dos" ya no salga "32".** `voice.py` manda `languageCodes: ["es-CO"]` y
   `adaptationPhrases` con las palabras-número. La config se validó conectando
   una sesión Live real; que corrija la palabra hay que oírlo.
2. **Los `[tool] nombre: Nms` en la consola (F12).** Si `check_answer` pasa de
   ~800 ms, la frase previa no alcanza y hay que pensar otra cosa.
3. **Que el tutor no dé por buena una respuesta mala.** Si vuelve a pasar *con
   la transcripción correcta*, ahí sí es el prompt: hoy dice "no calcules", que
   no es lo mismo que "no contradigas el veredicto de la herramienta".

**No tocar el prompt antes de ver la transcripción arreglada.** La sospecha de
que el tutor desobedecía a `check_answer` resultó falsa: le llegaba un "32" que
el niño nunca dijo.

Después de la sesión:

```bash
python -m scripts.procesar_pendientes --seco   # ¿quedó algo en cola?
python -m scripts.procesar_pendientes          # drenar
python -m scripts.generar_reportes             # el reporte de la semana
```

Y ahí el panel ya muestra el porcentaje del método, que hoy dice "—" con razón
(ver abajo).

---

## Cómo abrir el panel

```bash
python -m uvicorn tutor.api:app --port 8000
curl -X POST http://localhost:8000/api/auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{"nino_id":"n1","email":"tu@mail.com"}'
# el enlace sale por consola: http://localhost:8000/panel/n1?token=...
```

**Muestra "—" en "¿Le está dando las respuestas?", y está bien.** Las dos
sesiones de Juan se analizaron antes de que existiera `guardar_auditoria`, y la
idempotencia impide reanalizarlas. Se llena solo con la próxima sesión. **No
forzarlo:** reanalizar contaría el dominio dos veces.

---

## Abierto, sin urgencia

### Lo que quedó pendiente de la Constitución

Adoptada el 2026-08-18 (`knowledge/product/constitucion_valores.md` v3.2, con el
detalle de derivación en `ARCHITECTURE.md` §18). Lo que **no** se implementó:

- **La excepción de fe declarada** (Constitución §7). Si el padre declara marco
  cristiano en el onboarding, el tutor podría responder con sencillez que Dios
  existe. Hoy **toda** pregunta religiosa se devuelve a la familia, sin
  excepción. Para implementarla hacen falta tres cosas, en este orden: campo
  declarado por el padre en el perfil (nunca inferido de lo que dice el niño),
  pregunta en el onboarding, y revisión legal.
  `test_la_seguridad_no_implementa_la_excepcion_de_fe_declarada` falla el día
  que alguien lo haga — está puesto para que la decisión se tome mirando.
- **Confianza por dominio.** El System Prompt derivado pide inyectar el nivel de
  confianza del niño **por materia** (§3.3.6: un niño puede sentirse capaz en
  fútbol y derrotado en matemáticas). No existe: `RegistroDominio.nivel` es
  competencia medida, no confianza sentida. Son dos números distintos.
  ⚠️ Cuando se implemente, nace en `None` y llega en `None` hasta el prompt —
  aplica la lección de la fase 6: la ausencia de evidencia no se completa con un
  default que parece un dato. El prompt tiene que saber leerlo vacío.
- ✅ **La auditoría del elogio inflado ya corre** (era el pendiente 🔬 de esta
  lista). El campo rompía la extracción porque las dos mitades del Analista
  compartían un schema y competían: sin campos extra 4/4, con un campo trivial
  3/4, con uno que exige juicio 0/4. Se partió en dos llamadas
  (`ARCHITECTURE.md` §18) y ahora `elogio_inflado` audita la línea roja 14 con
  tres casos en `evals/parent_trust/`. La extracción volvió a 4/4 estable.

- ✅ **El tutor se llama Walter.** Vive en `config.NOMBRE_TUTOR`, no en el .md,
  porque es lo primero que va a variar (por país, o si la familia lo elige).
- **Notificación suave al papá cuando surge un tema de familia** (§7.4 y §8.6):
  religión, sexualidad, política, noticias difíciles. El tutor ya devuelve la
  pregunta a la casa; falta que el papá se entere de que surgió, para que la
  familia decida cómo abordarla. Es un evento nuevo, distinto de
  `escalate_safety` — no es un riesgo, es un aviso.
- **Que el Vigilante no escale travesuras.** El prompt ya distingue riesgo de
  travesura (§6.2.8), pero eso vive del lado del tutor. Falta confirmar que el
  Vigilante y el reporte al papá tampoco conviertan una confesión menor en un
  evento. Vale un caso en `evals/safety/`.
- **Documento legal dedicado** — consentimientos, mecánica de alertas y niveles,
  bifurcación intrafamiliar, retención, COPPA / Ley 1581. Lo pide la propia
  Constitución como su pendiente #1.
- **Diálogos modelo Nivel 1** (abuso, autolesión) — la Constitución es explícita
  en que se escriben **con el psicólogo infantil, nunca antes**.

### De la primera sesión de voz real (`ses_91c13b1747a2`, 18/08)

Lo arreglado está en los commits; esto es lo que quedó abierto.

- ✅ **El auditor ya ve las afirmaciones falsas.** `afirmo_algo_falso` está en
  `models.py` y documentado en `method_auditor.es.md`. Quedó escrito acá como
  pendiente porque "hay otra sesión trabajando en esos mismos archivos" — y esa
  sesión sí lo implementó. El texto viejo era residuo de la colisión, no un
  pendiente real.
- **Falta el dato de latencia.** La consola tenía las líneas
  `[tool] check_answer: Nms` y no se leyeron. Sin ese número no se sabe si la
  frase de espera alcanza.
- ✅ **La duda de los tokens, resuelta** (18/08, `scripts/verificar_tokens.py`
  contra la API real). `totalTokenCount` es **acumulativo de la sesión**:
  10.299 · 10.682 · 11.140 · 11.561 · 11.946 en cinco turnos. Se reporta el
  último. Sumarlos sobreestimaba 4,7x con cinco turnos y ~10x con veinte —
  `ses_88be006b825f` figura con 178.416 y gastó unos 18.500.

  Dos cosas que se creían y eran falsas: que el prompt se paga en cada turno
  (entra una vez al conectar; cada turno suma ~400) y que por eso había que
  adelgazarlo para bajar el costo. El prompt cuesta ~$0.20/mes. **Adelgazarlo
  sigue valiendo por latencia y por el techo del test, no por plata.**

  Precios oficiales de `gemini-3.1-flash-live-preview`: audio in $0.005/min,
  audio out $0.018/min. Con el tutor hablando ~40% del tiempo: **20 min/día ≈
  $7.30/mes, 30 min/día ≈ $11/mes.** El presupuesto de $8 cierra hasta ~22
  min/día.
- **Turnos perdidos** — *"Nueve, por tercera vez te estoy diciendo"*. Puede ser
  el mismo bug del audio suspendido (el niño repetía porque no oía la
  respuesta): verificar en la próxima sesión antes de tocar el VAD.

### Estructura que falta (confirmado el 18/08, no es contenido)

- 🔴 **El modo Pedido no se puede activar.** El backend lo soporta entero
  —`ModoSesion.PEDIDO`, su bloque en el prompt, "Con la tarea del colegio" en el
  playbook— y el frontend **siempre abre en guiado**. `ARCHITECTURE.md` §6
  define dos modos de sesión y hoy solo uno es alcanzable: la mitad del producto
  está construida y nadie puede llegar a ella. Es también el modo donde vive la
  promesa que nos separa del "ChatGPT para la tarea".

- 🔴 **`request_camera` es un stub.** Devuelve `{pedido: true}` y no abre nada.
  El tutor cree que pidió ver el cuaderno, se lo dice al niño, y no pasa nada —
  queda esperando una foto que nunca llega. Es central en modo Pedido: sin ver
  la tarea, ayudar con ella es adivinar.

- 🔴 **No existe la primera sesión del niño.** El tutor arranca igual la sesión 1
  que la 50. No hay presentación, ni acuerdo de cómo van a trabajar, ni forma de
  ganarse la confianza — y el niño llega a hablar con un desconocido que ya sabe
  cosas de él. Lo detectó RBH en la primera prueba real del onboarding: el tutor
  le dijo al niño que lo conocía porque él se lo había contado. Eso ya se
  arregló (ver abajo), pero el hueco de fondo sigue: **falta el guion del primer
  encuentro.**

- **El techo de tokens no corta durante la sesión.** Se verifica al abrir. Con la
  medición corregida no está sangrando, pero el hueco sigue.

- **Aviso suave al papá por tema de familia** (Constitución §7.4). Evento nuevo,
  distinto de `escalate_safety`: no es un riesgo, es un aviso.

- ⚠️ **El prompt de sesión está a 208 caracteres de su techo** (37.792 / 38.000).
  Lo próximo que alguien quiera agregar no entra. Adelgazarlo dejó de ser deuda
  cómoda: es un bloqueo. No es costo (~$0.20/mes, medido) — es latencia y es
  espacio.

### Alimentar el contenido (decidido con RBH el 18/08)

- **El onboarding del papá pregunta poco.** Funciona de punta a punta, pero
  `parent_interview.es.md` se conforma con los cuatro obligatorios. Falta
  decidir qué más vale la pena preguntar y cómo, para que el tutor arranque con
  material de verdad.

- **El onboarding del papá no debería ser solo texto.** Hoy es chat escrito. Las
  tres opciones son texto (datos exactos, barato), voz (coherente con el
  producto, el papá prueba lo que va a vivir su hijo) o las dos. El motor de la
  entrevista vive en el backend y no sabe qué le llega: **cambiar esto es la
  pantalla, no la arquitectura.**

- **Falta el onboarding del NIÑO como pieza propia.** Reglas, pasos y cómo se
  gana la confianza en el primer encuentro. Va en `knowledge/prompts/` — pero
  ojo con el techo del prompt: probablemente tenga que ser un bloque que **solo
  se inyecte cuando `madurez_vinculo == 0`**, no texto permanente.

### La cámara abre una puerta a la trampa (18/08, anotado con RBH)

Con cámara, el niño puede **mostrar el ejercicio y esperar que el tutor lo
resuelva**. Es la misma línea de siempre —ayudar con la tarea ≠ hacer la
tarea— pero por un camino nuevo: hasta ahora tenía que *decir* el problema, y
decirlo ya es trabajo. Enfocar la cámara no lo es.

Tres formas concretas, y ninguna está cubierta hoy:

1. **La página entera de la tarea.** El tutor ve diez ejercicios y puede
   empezar a resolverlos en cadena, sin que el niño haya intentado ninguno.
2. **La hoja de respuestas** del libro, o el cuaderno del compañero.
3. **La foto en vez del intento.** "Mira" reemplazando a "yo creo que da…" —
   el niño delega la lectura del problema, que es parte de resolverlo.

Lo que hoy lo contiene es solo el playbook general. Falta decidir qué reglas
propias lleva la cámara: por ejemplo, que ante una hoja con varios ejercicios el
tutor elija UNO y pregunte por dónde empezaría; que nunca lea en voz alta un
enunciado completo que el niño podría leer; y que una foto **no cuente como
intento** para la escalera de pistas.

Va con la tanda de reglas del modo Pedido, no suelto: es el mismo problema.

### Medido y descartado

- ❌ **Prompt caching en los agentes offline.** El mínimo cacheable son 1024
  tokens; por debajo no cachea, en silencio. Medido con `count_tokens` el
  18/08: `session_analyst` 729, `vigilante` 652, `parent_companion` 844,
  `exercise_generator` 562 — los cuatro por debajo. Solo `method_auditor`
  (1.411) calificaría, y ahí el ahorro son céntimos al mes. Lo propuse yo antes
  de medir; el dato lo desmiente. Se vuelve a mirar solo si algún prompt
  offline crece mucho.

### Lo demás

- **La verificación del reporte solo mira números.** Una afirmación cualitativa
  sin respaldo pasa: en el reporte real, *"lo que le está costando es sostener
  el tiempo frente a la actividad"* es una inferencia sobre 9 minutos, no un
  dato. Verificarlo pediría un segundo modelo, y la regla del proyecto es que la
  verificación es código. Por ahora se contiene desde el prompt.
- **Latencia de la primera frase.** `empezar()` en `useTutor.ts` es secuencial:
  abrir sesión → emitir token → conectar WebSocket → warmup. Paralelizar lo que
  no depende del token.
- **Frases cortadas a mitad de palabra** ("¡Contame", "y que te gusta"). VAD
  disparando de más — pero Juan interrumpía a propósito, así que puede ser
  correcto. Medir antes de tocar `deteccion_para_edad()` (`voice.py:69`).
  Relacionado: los 1500 ms fijos de silencio para 2° grado. La idea a evaluar es
  separar "silencio para responder" (respuesta corta y numérica → ~800 ms) de
  "silencio para cortar" (está razonando → 1500-2000).
- **Nadie manda el reporte por mail.** Se genera y se guarda; el papá lo ve si
  entra al panel. `aviso_de_reporte()` ya existe en `notificaciones.py` — falta
  decidir si el reporte semanal dispara el mail.
- **Enlaces mágicos en memoria.** `_ENLACES` es un dict de proceso: al escalar a
  varios workers hay que moverlo a una tabla con vencimiento.
- **Referencias DBA provisionales** en `matematicas.yaml` — verificar contra el
  MEN.

---

## Resuelto en esta tanda

| Era | Qué pasó |
|---|---|
| **El dominio llevaba seis sesiones congelado** | El tutor nunca pedía ejercicios del banco: improvisaba, nada quedaba atado a un nodo, `habilidades_trabajadas` salía vacío y el Analista no podía escribir dominio. Dos causas: el banco traía **una sola habilidad** (el niño pidió restas y no había, teniendo diez en la base sin cargar) y **nadie le había dicho al tutor de dónde salen los ejercicios**. Ahora `BancoDeSesion` indexa por habilidad, `_precargar` suma la frontera del niño, `get_next_problem` acepta `habilidad_id` de punta a punta, y el prompt lista los temas cargados. El niño elige **de qué**, nunca **cuál**. |
| **Un acierto se leyó como error** | `check_answer` devolvía INCORRECTO cuando no podía interpretar la respuesta — la falla de la fase 6 mirando al niño. Entra `Veredicto.NO_SE_ENTENDIO`, el playbook enseña a repreguntar en vez de corregir, y `_huele_a_transcripcion_rota` atrapa el `7102191` comparando órdenes de magnitud. |
| **El frontend no tenía un solo test** | Vitest + jsdom con un doble de `AudioContext` cuyo reloj no avanza solo. 30 tests, verificados reintroduciendo los tres bugs de `audio.ts` a mano. |
| **Dos tutores hablando encima** | `empezar()` en `useTutor.ts` no tenía guardia de reentrada ni cerraba lo anterior. La segunda llamada sobrescribía `liveRef` y `micRef`, y la primera conexión quedaba **huérfana**: nadie la podía cerrar, pero seguía recibiendo el audio del micrófono viejo por closure y seguía hablando con su propio reproductor. Lo disparaba "Probar de nuevo" — `onerror` ponía el estado en `"error"` sin soltar nada. Ahora hay guardia, `soltarRecursos()` compartido, y `empezar()` llama a `terminar(true)` si quedó sesión abierta (si no, quemaba cupo diario). |
| **El prompt se contradecía sobre cómo habla** | `tutor_persona.es.md` veta el voseo argentino, pero el bloque del modo Pedido vivía hardcodeado en `voice.py` y quedó en voseo cuando los .md se reescribieron a colombiano neutro. El mismo prompt decía "nunca vosees" y dos párrafos después voseaba. Igual en `pipeline.py`, donde el entrevistador le voseaba al papá. Lo fija `test_el_bloque_del_modo_pedido_no_vosea`, que mide el **delta** entre modos — buscar voseo en el prompt entero no sirve, porque la persona lista esas formas para vetarlas. |
| El reporte no lo generaba nadie | `generar_reporte_del_periodo()` + `scripts/generar_reportes.py`. Idempotente por período, verifica antes de guardar, y una falla de un niño no tumba a los demás. |
| 28/30 en los evals | No eran los casos: `extraer()` corría con temperatura 1.0. Extracción estructurada a 0 → **30/30**, dos veces. |
| "Tu hijo de 2° trabaja a nivel de 1°" | `grado_de_trabajo` contaba nodos de 1° que nunca se midieron. Ahora rige la presunción de grado. Afirmar un déficit sin datos asusta más que cualquier otro error. |
| "Método sostenido en el 100%" sin auditar | `cumplimiento_metodo` es opcional; `None` llega hasta la superficie y se dice "todavía no se midió". |
| Un reporte correcto rechazado | La sugerencia para casa lleva números inventados a propósito ("pesaba 350 kilos"). Se partió en `contenido` (se verifica) y `sugerencia` (no). |
| El panel se contradecía solo | "Todavía no hay sesiones auditadas" arriba y "2 auditadas" abajo. Ahora ambas salen de la misma lista de veredictos. |
| La tarea moría con un niño | El modelo devolvió una respuesta vacía y `messages.parse` explotó. Ahora cada fallo se aparta como `ReporteFallido` y se informa. |

Y de la tanda anterior: el Analista escribiendo el dominio, la transcripción con
idioma fijo, el panel server-rendered, y los evals de las cuatro suites.

---

## Notas operativas

**Un endpoint nuevo da 404 si nadie reinició uvicorn.** Sin `--reload` el
servidor sirve el código que tenía al arrancar, y un endpoint recién escrito
devuelve 404 exactamente igual que uno que no existe — el síntoma no distingue
"no lo escribí" de "no lo cargué". Pasó el 18/08 con `/api/onboarding`. Después
de tocar `api.py`, reiniciar y **probar el endpoint nuevo con curl** antes de
mandar a nadie a la pantalla.

**El zombie de `uvicorn --reload`.** Lanza el servidor real con
`multiprocessing spawn`, y **ese hijo no tiene "uvicorn" en su línea de
comando**. Al matar al padre, el hijo sobrevive con el socket del 8000 y sigue
respondiendo con código viejo. Sin `--reload` no pasa. Para matarlo:

```powershell
(Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess | Stop-Process -Force
```

**Cupo diario: 3 sesiones.** Probando se agota rápido. Para liberarlo:

```bash
python -c "import sqlite3,datetime; from src.tutor import config as c; \
  con=sqlite3.connect(c.DB); con.execute('DELETE FROM sesiones WHERE date(inicio)=?', \
  (datetime.date.today().isoformat(),)); con.commit()"
```

**Créditos de Google.** A mitad de una tanda una conexión devolvió "credits
depleted" y las siguientes volvieron a andar: o el saldo queda muy justo, o ese
mensaje es un límite de tasa disfrazado. Si vuelve a aparecer sin razón, mirar
por ahí antes que el código.

---

## Lo que quedó funcionando (verificado en `ses_83af1a57e8c2`)

- **Acento bogotano, redondo**: "qué bacano", "de una", "no te afanes", "un
  ratico", "eres muy juicioso", "¿sí ves?", "chévere". Cero voseo.
- **Aguantó tres pedidos frontales de la respuesta.** *"Dímelo tú"* → *"No,
  Juan, acuérdate: vamos juntos. Si te lo digo yo, no aprendes nada."*
- **No se cuelga** si una herramienta falla, y **no dice nombres de herramientas
  en voz alta.**
- **La presunción de grado funciona de punta a punta**: a Juan, de 2°, le tocó
  "Centenas" y no "contar hasta 100".
- Detalle lindo: Juan preguntó *"cuando te dije el ocho, te demoraste, ¿qué
  estabas haciendo?"* y el tutor contestó *"estaba revisando la respuesta,
  quería estar súper seguro"*. La espera dejó de leerse como abandono.
