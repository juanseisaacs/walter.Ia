# RBH Tutor

**Tutor de voz con método socrático para niños de 1° a 5° de primaria.**
Guía con preguntas y pistas escalonadas, y **nunca regala la respuesta**.
Conoce al niño y crece con él sesión a sesión.

> Nace del RFS **"The Primer"** de Y Combinator (Fall 2026), inspirado en el
> Primer de *The Diamond Age*.

El niño **habla** con el tutor. No hay botones que apretar ni texto que leer:
abre la página, dice "hola" y empieza la clase.

---

## El problema

YC lo dice sin rodeos: *"el cementerio del edtech está lleno de 'ChatGPT para
la tarea'."*

Un modelo que resuelve el ejercicio se siente útil durante una semana y le
enseña al niño a no pensar. La línea que define este proyecto es esa:

> **Ayudar con la tarea ≠ hacer la tarea.**
> La tarea es materia prima para tutoría socrática, no un problema a resolver.

Sostener eso bajo presión —un niño que insiste *"ya lo intenté cinco veces,
decime la respuesta"*— no se logra con un prompt que pide ser socrático. Se
logra con arquitectura.

<details>
<summary><b>Una sesión real, cuando le piden la respuesta para no tener que estudiar</b></summary>

Transcripción sin retocar de `ses_47dfebd9aa43`:

```
NIÑO   Listo, ¿y cuánto es 20 - 20, que es lo que tengo en mi tarea?
       Solo dime cuánto es y ya, para yo poder hacer la tarea y no
       tener que estudiar.

TUTOR  Uy, Felipe, si te la digo yo, mañana no vas a saber cómo hacerla
       en el examen. Vamos juntos, ¿listo? Cuéntame cómo la pensaste
       primero.

NIÑO   Ah, pero si sabías que soy Felipe, ¿por qué antes no me dijiste
       que era Felipe?

TUTOR  ¡Qué preguntota! Tienes toda la razón, discúlpame. Tu mamá me
       contó un poquito de ti para que nos conociéramos más rápido,
       ¡pero lo demás me lo vas a contar tú!
```

Dos cosas que no son del prompt: la primera respuesta la sostiene la
arquitectura —el tutor no tiene forma de saber el resultado, `verify_arithmetic`
devuelve si acertó y qué tan lejos quedó, **nunca el número**—, y la segunda
sale de que el niño lo pilló en algo verdadero y el tutor lo admitió en vez de
inventar.

Y en otra sesión, cuatro días después: *"sé que te gusta dibujar, que tu color
favorito es el rojo, y que andas en tercero. Ah, y que tu prima te anda
preguntando por BTS, ¿no?"* — a lo que el niño contestó *"no era mi prima, era
mi hermana"*. Eso es la ficha longitudinal funcionando, y corrigiéndose.

</details>

---

## El norte

Toda decisión se justifica contra uno de estos cinco criterios. Si una feature
no sirve a ninguno, no entra al MVP.

| # | Criterio | Cómo se cumple |
|---|---|---|
| 1 | **Curriculum fidelity** | Grafo de habilidades con prerrequisitos, anclado a DBA (Colombia), EBC y Core Knowledge. Planificador determinístico |
| 2 | **Safety** | Vigilante independiente + prefiltro en código + `escalate_safety`. Dos caminos a la alarma |
| 3 | **Longitudinal memory** | Ficha del niño en dos mitades, consolidada sesión a sesión, con decaimiento |
| 4 | **Parent trust** | Se audita **toda** sesión que deje transcripción — no una muestra. Los reportes se verifican en código contra los datos |
| 5 | **Formación de carácter** | El tutor forma la persona, no solo la competencia académica |

Los cuatro primeros son de YC. El quinto es propio y viene de la
[Constitución de Valores](knowledge/product/constitucion_valores.md): diez
pilares, mentalidad de progreso, liderazgo y catorce líneas rojas.

Y una regla de forma que vale tanto como el contenido: **los valores no se
predican.** No hay lección de valores; hay un tutor que es así en cada turno.
Si el tutor sermonea, dejó de formar.

---

## Estado

**El circuito completo cierra**, de la voz del niño al panel del papá:

```
el niño habla → el tutor usa el banco y check_answer → la sesión cierra
   → el Analista escribe el dominio → el planificador de mañana arranca
   con la evidencia de hoy → el reporte semanal lo cuenta → el papá lo lee
```

| | |
|---|---|
| Habilidades de matemáticas (1° a 5°) | **54**, con triple anclaje verificado contra los documentos primarios |
| Ejercicios validados en banco | **1.408** — ~26 por habilidad, ninguna vacía |
| Tests de Python | **411**, en verde |
| Tests del front | **73**, en verde |
| Casos de eval en las 4 suites de YC | **48** — la última corrida completa dio 45/45 el 20/08; los 3 casos agregados después no se han corrido |
| Sesiones de voz corridas | **62** · 71 transcripciones · 41 auditorías del método |

Probado con voz real, cámara, pizarra y hoja de dibujo. Lint en cero.

**Y las 62 sesiones son nuestras.** Ningún niño ajeno ha usado esto todavía. Lo
que demuestran es que el sistema aguanta en vivo — de ahí salieron el "dos" que
se transcribía "32", el turno que no se abría cuando alguien contesta bajito, y
el tutor inventando lo que veía por la cámara. **No demuestran que un niño
aprenda**, y no vamos a decir que sí hasta medirlo.

**Lo que falta no es código: es evidencia de uso.** Cinco niños que no seamos
nosotros, una semana, y las tres preguntas que ninguna feature reemplaza —
¿vuelve sin que se lo pidan?, ¿aprende de verdad?, ¿aguanta 20 minutos? Ver
[`PENDIENTE.md`](PENDIENTE.md).

El producto promete lectura, escritura y aritmética. Hoy hay **aritmética**;
los otros dos tercios esperan una decisión de método que define el grafo entero.

---

## Cómo funciona

### Los dos planos

El sistema tiene dos planos con reglas opuestas:

```
┌─ PLANO EN VIVO ─────────────────────────────────────┐
│  Latencia crítica. Tools. Nada bloquea al tutor.     │
│                                                      │
│   Niño ⇄ Tutor (voz)                                 │
│           └── 4 tools                                │
│   Vigilante ── en paralelo, nunca bloquea            │
└──────────────────────────────────────────────────────┘
                        │  transcripción
                        ▼
┌─ PLANO OFFLINE ─────────────────────────────────────┐
│  Latencia irrelevante. Sin tools. Funciones puras.   │
│                                                      │
│   Analista → ficha → (planificador en código)        │
│   Compañero del Papá → reporte semanal               │
└──────────────────────────────────────────────────────┘
```

### El audio no pasa por el backend

```
navegador ──audio PCM 16kHz──> Gemini Live ──audio PCM 24kHz──> navegador
    │
    ├─ POST /api/voice/token             token efímero (una vez, al abrir)
    ├─ POST /api/tools/*                 los tools (~100ms, ocasional)
    └─ POST /api/sesiones/{id}/turnos    transcripción → Vigilante
```

**El backend controla, no transporta.** Un proxy agregaría 80-300ms por ronda
sobre una base de ~600ms, y lo paga cada niño en cada turno.

Que el audio vaya directo no significa que el navegador mande. Hay **tres
candados**: la configuración va atada al token (el cliente no puede cambiar la
persona, el playbook ni la política de seguridad), reportar los turnos es
requisito para recargar ejercicios, y cada renovación de sesión pasa por el
backend, que ahí chequea presupuesto y límites.

### Los agentes

**4 en producción + 1 de construcción.** Un LLM se usa **solo donde hace falta
criterio**.

| Agente | Cuándo | Modelo |
|---|---|---|
| **Tutor** | En vivo | Gemini Live + 4 tools |
| **Vigilante** | En vivo, en paralelo | Haiku 4.5 |
| **Analista de sesión** | Post-sesión, 100% | Haiku 4.5 |
| **Compañero del Papá** | Onboarding + semanal | Sonnet 5 |
| *Generador de ejercicios* | *Build-time* | *Haiku 4.5* |

**El Vigilante nunca se fusiona con el Tutor.** El tutor está optimizado para
mantener al niño enganchado; el vigilante, para frenar y escalar: incentivos
opuestos. Y la cosa que puede ser manipulada no puede ser la que detecta la
manipulación — el vigilante ve solo una ventana de 3-4 turnos, con contexto
limpio.

---

## Las decisiones que definen el sistema

**La aritmética jamás la valida un modelo.** `check_answer` es código puro. Un
"¡correcto!" a 7+5=13 destruye la confianza para siempre. Lo mismo el
planificador ("¿qué sigue?"), el decaimiento del dominio y la verificación del
reporte al papá: son cálculo, no criterio.

**Ningún agente afirma nada que no esté en los datos.** El reporte al papá se
verifica en código contra la fuente. Y cuando algo no se midió, el número que
llega es `None` — "no lo medimos" se dice, no se completa con un default que
parece un dato.

**El grado escolar nunca limita.** Ningún filtro descarta una habilidad por
`grado_sugerido`: el planificador decide por dominio. Subir de grado no se
penaliza jamás. Si un niño llegó a contenido de tres grados más arriba es
porque tiene los prerrequisitos — y entonces se lo ganó. El tutor lo sabe (no
lo frena) y el papá se entera.

**El elogio inflado está prohibido.** "Eres un genio", "eres el mejor" — nunca.
No por exagerados: porque le enseñan al niño que su valor depende de rendir.
Reconocimiento específico y creíble, o silencio. La dignidad es incondicional;
la confianza se gana.

**Los prompts son datos.** Viven en `knowledge/prompts/*.md` y se cargan en
runtime. Cambiar el comportamiento de un agente no debe tocar Python.

**Las transcripciones se borran a los N días.** El activo es la ficha
estructurada, no la conversación cruda. Toda sesión tiene techo de tiempo y de
tokens; también hay techo diario y mensual por niño: 45 minutos por sesión, 3
sesiones al día, 8 USD al mes.

---

## Lo que este proyecto afirma, y lo que no

Es fácil vender humo en edtech, así que conviene ser explícito.

**Afirma** que el nivel de un niño se **mide**, no se supone por su edad —
todo el planificador se apoya en eso. Afirma que la aritmética se puede
verificar en código y que por lo tanto el tutor no puede equivocarse
calificando: no es que sea bueno calculando, es que **no calcula**. Y afirma
que lo que se le dice al papá se puede contrastar contra la fuente, porque
hay código que lo contrasta antes de mandarlo.

**No afirma que el niño aprenda más rápido.** No está medido. Esa es la
evidencia que falta y la decimos primero, no en una nota al pie.

**No afirma nada sobre "estilos de aprendizaje".** No clasificamos a nadie como
visual, auditivo o kinestésico. No está en el sistema, no está en el grafo y no
va a estar: la investigación no lo sostiene.

**No diagnostica ni lo insinúa.** Ni dificultades de aprendizaje, ni atención,
ni nada. Se describe lo que el niño hizo, nunca cómo es. Eso es trabajo de un
profesional, no de un producto.

**El modelo de olvido es una calibración razonable, no una medición.** Está
ajustado contra el sentido común pedagógico —un chico que aprendió a contar
hasta 100 no lo pierde en dos semanas— y tiene tests de calibración absoluta.
No está validado contra estos niños, porque todavía no hay estos niños.

### Y la auditoría nos pilla a nosotros

De las 41 sesiones auditadas hasta hoy, el Analista marcó que **el tutor regaló
la respuesta en 7** — un 17 %. También detectó elogio inflado en 5 y una
afirmación falsa en otras 5.

Ese número podría no estar acá. Está porque es el punto: **una auditoría que
siempre dice que todo salió bien no es una auditoría.** Ya nos pasó una vez —
`cumplimiento_metodo` devolvía 100 % cuando no había ni una sesión revisada, y
el reporte se lo iba a decir al papá. Lo cuenta `BITACORA.md`.

---

## El currículum

No se adopta un currículum ajeno: se construye el propio y se ancla a
estándares reconocidos. Cada nodo es una habilidad atómica, y las flechas dicen
qué va antes de qué.

```yaml
- id: mat.numeros.valor_posicional_decenas
  nombre:
    es: "Decenas y unidades"
  materia: matematicas
  grado_sugerido: 1
  prerequisitos:
    - mat.numeros.conteo_hasta_100
  alineacion:
    dba_colombia: "DBA Matemáticas 1° · #3"
    ebc_colombia: "EBC Matemáticas 1°-3° · «Uso representaciones…»"
    core_knowledge: "Grade 1 Mathematics — Place value: ones, tens, hundreds"
  verificable_en_codigo: true
```

Las 54 habilidades cubren el **pensamiento numérico del MEN completo** de 1° a
5°. El anclaje cita el DBA **por su número**, que es lo que lo hace
verificable: una descripción libre no se puede contrastar con nada. Los tres
anclajes se auditaron uno por uno contra los documentos primarios.

Geometría, medición y estadística quedan fuera a propósito — el alcance es
lectura, escritura y aritmética. Lo que sigue sin verificar se dice en la
cabecera del YAML, no se completa en silencio.

---

## Arranque

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -e ".[dev]"

cp .env.example .env            # y completar ANTHROPIC_API_KEY y GOOGLE_API_KEY

pytest                          # 411 tests, rápidos, sin red
```

### Para hablar con el tutor

```bash
cd web && npm install && npm run build && cd ..
python -m uvicorn tutor.api:app --port 8000
```

→ **http://localhost:8000** · la app del niño y la API salen del mismo proceso.

⚠️ **`npm run dev` no sirve para hablar con el tutor.** Es para trabajar en la
interfaz. El servidor de desarrollo entrega React sin minificar, y esta app
procesa audio PCM en tiempo real en el hilo del navegador: con el build de
desarrollo el niño siente que el tutor "se va a buscar la respuesta y vuelve".

### Herramientas

```bash
python -m scripts.demo_planificador     # el cerebro
python -m scripts.demo_persistencia     # el ciclo completo
python -m scripts.verificar_vision      # ¿el tutor VE o completa?
python -m scripts.procesar_pendientes   # drena la cola del Analista
python -m scripts.generar_reportes      # el reporte semanal al papá
python -m evals.runner                  # las 4 suites (consume API)
```

---

## Mapa del repo

| Carpeta | Qué hay |
|---|---|
| `knowledge/` | **El activo.** Currículum, prompts y la Constitución. Versionado, revisable en PR |
| `src/tutor/` | El código. 12 módulos; los puros no hacen red ni I/O |
| `web/` | La interfaz de voz del niño (React + Vite) |
| `evals/` | Las 4 suites de YC, 48 casos |
| `scripts/` | Demos, verificadores y construcción del banco |
| `tests/` | 386 tests |
| `data/` | Runtime. **Nunca se versiona** — contiene datos de menores |

```
src/tutor/
├── models.py       # estructuras de datos (Pydantic)     — puro
├── curriculum.py   # carga, valida y navega el grafo     — puro
├── pedagogy.py     # dominio, decaimiento, qué sigue     — puro  ← el cerebro
├── storage.py      # SQLite, migraciones, retención      — puro
├── tools.py        # los tools del tutor                 — puro
├── config.py       # llaves, rutas, presupuestos         — puro
├── voice.py        # adaptador del modelo de voz         — red
├── session.py      # orquestador de sesión en vivo       — red
├── pipeline.py     # los agentes offline                 — red
├── api.py          # plano de control + panel del papá   — red
├── panel.py        # el panel del papá, server-rendered  — red
└── notificaciones.py  # avisos al papá                   — red
```

`voice.py` está separado a propósito: cambiar de modelo de voz debe tocar un
archivo.

---

## Documentos

- **[`CLAUDE.md`](CLAUDE.md)** — cómo trabajar acá: las reglas duras, dónde va
  cada cosa y cómo se verifica
- **[`ARCHITECTURE.md`](ARCHITECTURE.md)** — qué se decidió y su razón. La
  memoria del proyecto. Si algo no está ahí, no se decidió
- **[`BITACORA.md`](BITACORA.md)** — por qué las reglas son las que son. Ocho
  bugs que costaron caro, con su causa real. Cuatro eran la misma falla: algo
  dejó de pasar y no había dónde enterarse
- **[`PENDIENTE.md`](PENDIENTE.md)** — dónde retomar. Se poda, no solo se agrega
- **[`knowledge/product/constitucion_valores.md`](knowledge/product/constitucion_valores.md)**
  — el ADN ético-valórico. Manda sobre el producto
- **[`knowledge/curriculum/FUENTES.md`](knowledge/curriculum/FUENTES.md)** — de
  dónde sale cada anclaje y qué se verificó contra el primario
- **[`knowledge/curriculum/base_academica_men.md`](knowledge/curriculum/base_academica_men.md)**
  — el marco del MEN alrededor del grafo: áreas, EBC, Saber, calendarios y
  desarrollo cognitivo. Ver `ARCHITECTURE.md` §19

---

## Idioma

Contenido, prompts y documentación en **español**. El código lleva nombres en
inglés (`get_next_problem`) con comentarios y docstrings en español. Los IDs de
nodos del grafo nunca se traducen: son la llave estable.
