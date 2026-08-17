# Arquitectura — RBH Tutor

> Tutor AI adaptativo para niños de 1° a 5° de primaria en lectura, escritura y
> aritmética. Método socrático: nunca regala la respuesta.

Este documento es la **memoria del proyecto**. Toda decisión de arquitectura vive
acá, con su razón. Si algo no está acá, no se decidió.

---

## 1. El norte: los 4 criterios de YC

El proyecto nace del RFS **"The Primer"** (Y Combinator, Fall 2026, por Andrew
Miklas), inspirado en el Primer de *The Diamond Age*. YC define cuatro
dimensiones para ganar en este espacio. **Toda decisión de arquitectura se
justifica contra una de estas cuatro. Si una feature no sirve a ninguna, no entra
al MVP.**

| # | Criterio | Cómo lo cumplimos |
|---|---|---|
| 1 | **Curriculum fidelity** | Grafo de habilidades con prerrequisitos, anclado a DBA (Colombia) y Core Knowledge. Planificador determinístico |
| 2 | **Safety** | Vigilante independiente + prefiltro en código + `escalate_safety`. Dos caminos a la alarma |
| 3 | **Longitudinal memory** | Ficha del niño en dos mitades, consolidada sesión a sesión, con decaimiento |
| 4 | **Parent trust** | Auditoría del método en el 100% de las sesiones, reportes verificados contra datos, retención mínima |

**La advertencia de YC:** *"el cementerio del edtech está lleno de 'ChatGPT para
la tarea'."* Ayudamos con la tarea, **nunca la hacemos**. La tarea es materia
prima para tutoría socrática, no un problema a resolver.

---

## 2. Los dos planos

El sistema tiene dos planos con reglas opuestas.

```
┌─ PLANO EN VIVO ─────────────────────────────────────┐
│  Latencia crítica. Tools. Nada bloquea al tutor.    │
│                                                      │
│   Niño ⇄ Tutor (voz)                                │
│           └── 4 tools                                │
│   Vigilante ── en paralelo, nunca bloquea            │
└──────────────────────────────────────────────────────┘
                        │  transcripción
                        ▼
┌─ PLANO OFFLINE ─────────────────────────────────────┐
│  Latencia irrelevante. Sin tools. Funciones puras.  │
│                                                      │
│   Analista → ficha → (planificador en código)       │
│   Compañero del Papá → reporte semanal              │
└──────────────────────────────────────────────────────┘
```

---

## 3. Agentes

**4 en producción + 1 herramienta de construcción.**

| # | Agente | Cuándo | Modelo | Entra → Sale |
|---|---|---|---|---|
| 1 | **Compañero del Papá** | Onboarding + semanal | Sonnet 5 | Conversación / datos → ficha inicial / reporte |
| 2 | **Tutor** | En vivo | Gemini Live + 4 tools | Voz + ficha → voz |
| 3 | **Vigilante** | En vivo, **paralelo** | Haiku 4.5 | Ventana de turnos → alerta / nada |
| 4 | **Analista de sesión** | Post-sesión, **100%** | Haiku 4.5 | Transcripción → señales + auditoría |
| — | *Generador de ejercicios* | *Build-time* | *Haiku 4.5* | *Nodo → ejercicios validados* |

### Decisiones de fusión

- **Analista + Supervisor de calidad → uno solo.** Mismo input, mismo momento,
  mismo modelo. Fusionados, la auditoría del método socrático pasa de muestreo
  del 10% a **cobertura del 100%** al mismo costo.
- **Entrevistador + Reportero → Compañero del Papá.** Misma persona hablándole al
  papá. Un agente, dos modos. Deja lugar para un modo Q&A futuro.

### Lo que NO se fusiona

**El Vigilante nunca se fusiona con el Tutor.** Tres razones:

1. **Conflicto de roles.** El tutor está optimizado para mantener al niño
   enganchado; el vigilante para frenar y escalar. Incentivos opuestos.
2. **Manipulación.** El contexto del tutor está lleno de input no confiable. La
   cosa que puede ser manipulada no puede ser la que detecta la manipulación. El
   vigilante ve solo una ventana de turnos, con contexto limpio.
3. **Auditabilidad.** Un veredicto discreto por ventana es una traza. Seguridad
   adentro de la cabeza del tutor no se puede demostrar.

---

## 4. Lo que es código, no agente

Un LLM se usa **solo donde hace falta criterio**. Todo lo demás es código
determinístico: gratis, instantáneo, predecible, auditable.

| Pieza | Por qué en código |
|---|---|
| **Planificador** ("¿qué sigue?") | Es un cálculo sobre el grafo: nodos con prerrequisitos dominados y este no. No es criterio |
| **Verificación de respuestas** | La aritmética jamás la valida un modelo. Un "¡correcto!" a 7+5=13 destruye la confianza para siempre |
| **Prefiltro de seguridad** | String match sobre términos de alta señal. 0ms |
| **Decaimiento de dominio** | Fórmula sobre `last_practiced`. Repaso espaciado |
| **Verificación del reporte** | Los números del reporte deben coincidir con la fuente |

---

## 5. Los 4 tools del tutor

| Tool | Qué hace | Latencia |
|---|---|---|
| `check_answer` | Verificación determinística en memoria | ~5ms |
| `get_next_problem` | Saca uno del banco precargado en memoria | ~0ms |
| `request_camera` | Pide ver el cuaderno o la tarea | n/a |
| `escalate_safety` | Segundo camino independiente a la alarma | n/a |

**Descartados a propósito:** `record_observation` (el Analista lo extrae después,
sin costo de latencia) y `end_session` (la sesión termina sola).

---

## 6. Los dos modos de sesión

| | **Guiado** | **Pedido** |
|---|---|---|
| Quién elige el tema | El planificador | El niño |
| Ejercicios | Del banco precargado | Los trae el niño |
| Cámara | Ocasional | Central |
| Método socrático | Estricto | **Más estricto todavía** |

El modo se elige al abrir la sesión, explícitamente
(*"¿seguimos donde quedamos o tenés tarea?"*).

El modo Pedido es además la **mejor herramienta de diagnóstico**: lo que el niño
trae del colegio dice dónde está parado sin tomarle examen.

---

## 7. Currículum: grafo propio con doble anclaje

**No adoptamos un currículum ajeno.** Construimos el nuestro y lo anclamos a dos
estándares reconocidos:

```yaml
- id: mat.suma.con_reagrupacion
  nombre:
    es: "Suma llevando"
    en: "Addition with regrouping"
  prerequisitos:
    - mat.suma.sin_reagrupacion
    - mat.valor_posicional.decenas
  alineacion:
    dba_colombia: "DBA Matemáticas 2° · #3"
    core_knowledge: "Grade 2 Mathematics — Addition with regrouping"
```

**Por qué así:**

1. **Fidelidad demostrable** — ante "¿contra qué está alineado?", hay respuesta,
   y en dos estándares
2. **Multi-mercado desde el día 1** — Colombia y homeschool USA sin duplicar
3. **Extensible** — otro país es un campo, no un grafo nuevo
4. **Legalmente limpio** — la estructura es nuestra; citamos alineación

**Idioma:** español primero. Los campos `en` existen desde el día 1 pero quedan
vacíos. Costo hoy: cero. Refactor mañana: cero.

---

## 8. Storage: archivos + SQLite

| Dónde | Qué | Por qué |
|---|---|---|
| `knowledge/` (git) | Currículum, prompts, evals | Lo escribe un humano. Se revisa en PR, se versiona, se puede volver atrás |
| `data/tutor.db` (SQLite) | Ficha del niño, sesiones, observaciones | Lo escribe el sistema, concurrentemente. Necesita escrituras atómicas |
| `data/*.json` | Transcripciones, reportes | Append-only, se escriben una vez |

**Por qué SQLite y no JSON para la ficha:** la sesión en vivo y el pipeline
offline escriben la misma ficha. Leer-modificar-escribir sobre JSON tiene *race
condition*: el último pisa al anterior y se pierde historial de aprendizaje, en
silencio. SQLite serializa las escrituras.

**SQLite no es un servidor.** Es un archivo. Sin proceso, sin Docker, sin
connection string.

**Repository pattern:** todo acceso pasa por la interfaz de `storage.py`. El día
que haya servidor (necesario para las tiendas), cambia un archivo, no la app.
La interfaz se mantiene chica — los métodos que se usan, no un ORM.

---

## 9. Latencia

> **Regla de oro: la respuesta hablada del tutor nunca espera a nuestra
> infraestructura.**
>
> Un tool call es la excepción explícita: es ocasional (cada ~30-60s, no cada
> turno), el modelo está diseñado para esperarlo, y ~100ms ahí es aceptable.
> Lo que no se admite es que el backend esté en el camino de cada palabra.

| Componente | Ingenuo | Diseñado |
|---|---|---|
| Modelo de voz | 300-800ms | 300-800ms *(piso)* |
| Vigilante | +400-800ms ❌ | **0ms** — corre en paralelo |
| `get_next_problem` | +100-500ms ❌ | **~0ms** — precargado al inicio |
| `check_answer` | +50-150ms | **~5ms** — cálculo en memoria |
| Prompt inflado | +100-300ms ❌ | mínimo |
| **Agregado total** | **+650 a 1750ms** | **+5 a 20ms** |

**Todo el trabajo pesado se hace ANTES de la sesión.** Al arrancar, el sistema ya
sabe qué va a enseñar y con qué ejercicios. Durante la sesión no piensa: ejecuta.

**El prompt de sesión se mantiene flaco:** persona + playbook + resumen compacto
del niño + nodo actual. No el currículum entero ni la historia completa.

**Punto específico de niños:** la latencia más percibida no es la del modelo —
es cuánto silencio se espera para decidir que el niño terminó de hablar. Los
niños hacen pausas largas mientras piensan. Cortarlos ahí es lo peor que puede
pasar en método socrático. Es una perilla a calibrar por edad.

---

## 10. Arquitectura de voz: el niño habla directo con el modelo

**El audio va del navegador a Gemini Live sin pasar por nuestro backend.**

```
navegador ──audio PCM 16kHz──> Gemini Live ──audio PCM 24kHz──> navegador
    │
    ├─ POST /api/voice/token      token efímero (una vez, al abrir)
    ├─ POST /api/tools/*          los 4 tools (~100ms, ocasional)
    └─ POST /api/sesiones/{id}/turnos   transcripción → Vigilante
```

**Por qué directo:** dos saltos de red menos por ronda. Un proxy en el backend
agrega ~80-120ms con el servidor bien ubicado, y 250-300ms si queda lejos. Sobre
una base de ~600ms es 15-20% — real, y lo paga cada niño en cada turno.

### Los tres candados

El backend no está en el camino del audio, pero sí en el del **control**:

**1. La configuración va atada al token.**
Al emitir el token efímero se fija el modelo y la configuración desde el
servidor. El navegador **no puede cambiar** la persona, el playbook socrático ni
la política de seguridad. Protege la propiedad intelectual y evita que a alguien
se le puedan arrancar los frenos de seguridad al tutor.

**2. Reportar es necesario, no opcional.**
Se precargan pocos ejercicios; para recargar hay que haber reportado los turnos
anteriores. Un cliente que deja de reportar **se queda sin ejercicios**. No es
vigilancia: el reporte es parte de cómo funciona.

**3. El tope de sesión hace de control de gasto.**
Las sesiones de Gemini Live tienen duración máxima propia. Cada renovación pasa
obligatoriamente por el backend, y ahí se chequea presupuesto, límite diario y
las restricciones que puso el papá.

### Lo que esto NO resuelve, y cuándo importa

La auditoría queda **muy difícil de saltear, no imposible**: un cliente
modificado puede dejar de reportar.

Para consumidor con niños de 5 a 10 años, el adversario realista no existe. Los
que sí son reales —un competidor copiando el playbook— quedan cubiertos por el
candado 1.

> **Disparador para migrar a proxy:** el día que se venda a un colegio o
> institución que exija auditoría infalsificable. Es un plan distinto, con su
> propio precio — no una deuda técnica.

Si se migra, **toda la capa de audio del cliente sigue igual** (captura,
reproducción encadenada, interrupción): solo se muda la conexión.

### Parámetros de audio que no son opcionales

Verificados en un experimento previo (`walter-voz`). No son preferencias:

| Parámetro | Valor | Si se cambia |
|---|---|---|
| Sample rate entrada | 16000 Hz | Gemini no entiende o distorsiona |
| Sample rate salida | 24000 Hz | Reproducirlo a otra frecuencia cambia el tono |
| Formato | PCM 16-bit LE, mono, base64 | Es el único que acepta |
| `echoCancellation` | `true` | El tutor se oye a sí mismo y se auto-interrumpe |
| Reproducción | Encadenada en el reloj de audio | Sin esto la voz suena cortada. **Es lo más importante** |
| Captura | AudioWorklet | `ScriptProcessorNode` compite con la UI y corta el audio |
| `interrupted` | → detener TODAS las fuentes | Si no, sigue hablando segundos después de que lo interrumpan |

**No existe parámetro de velocidad de habla.** El ritmo solo se influye desde el
prompt.

**Detección de fin de turno:** hay que configurarla explícitamente. Los defaults
están pensados para adultos; **un nene de 7 años hace pausas largas mientras
piensa y el sistema le va a cortar la frase**. Ver §9.

### ✅ Verificado con API key real (2026-08-17)

`python -m scripts.verificar_gemini` — reproducible.

| Supuesto | Resultado |
|---|---|
| **La configuración se puede atar al token** (`live_connect_constraints`) | ✅ **Confirmado.** El candado 1 existe. La persona, el playbook y la política de seguridad quedan fijados del lado del servidor |
| **Tool calling en Live API** | ✅ **Confirmado.** El modelo llamó `check_answer({'ejercicio_id': 'e1', 'respuesta_nino': '42'})` sin ajustes |

**Hallazgo no documentado:** `gemini-3.1-flash-live-preview` **solo devuelve
AUDIO**. Pedirle `responseModalities: ["TEXT"]` falla con
`1007 ... combination of response modalities (TEXT) is not supported`.
La **entrada** sí acepta texto — que es exactamente lo que necesita la
alternativa secundaria por escrito.

**Modelos Live disponibles** (consultado con `models.list()`, no adivinado):

| Modelo | Nota |
|---|---|
| `gemini-3.1-flash-live-preview` | **El nuestro** — baja latencia |
| `gemini-2.5-flash-native-audio-latest` | Audio nativo, más expresivo. Vale probarlo |
| `gemini-2.5-flash-native-audio-preview-12-2025` | Idem, versión fija |
| `gemini-3.5-live-translate-preview` | Traducción — no aplica |

Todos en *preview*: si un ID devuelve 404, volver a correr `models.list()` en
vez de adivinar.

---

## 11. La ficha del niño (longitudinal memory)

Dos mitades con reglas distintas:

| Mitad | Contiene | Quién la escribe |
|---|---|---|
| **Académica** | Dominio por nodo, intentos, último repaso, ritmo | **Código** (cálculo determinístico) |
| **Personal** | Intereses, motivadores, frustraciones, estilo de comunicación | **El Analista** (observación acumulada) |

**Regla de la mitad personal: consolidar, no acumular.** Si ya sabía que le gusta
el fútbol y hoy lo confirma, refuerza la línea existente — no agrega una nueva.
Si no, a los 6 meses la ficha es ilegible.

**Madurez del vínculo:** el tutor sabe cuánto sabe del niño. En la sesión 2 es
explorador; en la 40 va directo.

**Decaimiento:** el dominio baja con el tiempo sin práctica. El planificador
reintroduce repasos. Un sistema que asume que el niño nunca olvida es falso y se
nota rápido.

---

## 12. Sin techo: el grado no limita

**El grado escolar es una etiqueta administrativa, no un límite.** Si un niño
avanza rápido, el tutor crece con él. La promesa es explotar el potencial, no
contenerlo dentro de lo que "corresponde" a su edad.

Esto no es una feature aparte: es una consecuencia de que el planificador decida
por **dominio** y no por grado. `habilidades_disponibles` devuelve todo lo que
tenga prerrequisitos cumplidos, sin mirar `grado_sugerido`.

**Asimetría deliberada en el planificador:**

```python
distancia_grado = max(0, nino.grado - h.grado_sugerido)
```

Subir de grado **no se penaliza nunca**; solo se prefiere no bajar sin
necesidad. Si un niño llegó a contenido de tres grados más arriba es porque
tiene los prerrequisitos — y entonces se lo ganó.

**Tres consecuencias:**

| Dónde | Qué pasa |
|---|---|
| **El planificador** | Ofrece contenido superior en cuanto los prerrequisitos están dominados |
| **El tutor** | El resumen de sesión le avisa: *"VA ADELANTADO — no lo frenes ni bajes la exigencia"* |
| **El papá** | `adelanto_grados` va en el reporte. *"Tu hijo trabaja un grado por encima"* es de lo más potente que puede leer |

**Implicación para el currículum:** el grafo tiene que tener siempre cabeza de
pista por encima del grado del niño. Un grafo que termina en 5° le pone un techo
real a un chico de 5° veloz. Cuando el contenido se agote, se extiende.

`grado_de_trabajo()` mide dónde está el niño **de verdad** — el grado más bajo
que todavía no domina — y es lo que se reporta, no el grado del colegio.

---

## 13. Banco de ejercicios

Generado **una vez**, offline, por lote:

```
Nodo del grafo → Generador (Haiku) → validación en CÓDIGO → banco
```

El validador verifica que la matemática cierre y la respuesta sea correcta antes
de que un ejercicio toque a un niño.

**Costo estimado:** ~600 nodos × 50 ejercicios ≈ 30.000 ejercicios ≈ **$13-26 con
Batch API**. Una sola vez.

**Variantes temáticas:** el banco puede generar la misma habilidad ambientada en
los intereses del niño (fútbol, dinosaurios). Conecta con la ficha personal.

---

## 14. Operación y riesgos

| Riesgo | Mitigación |
|---|---|
| **Datos de menores** (Ley 1581 CO / COPPA US) | Las transcripciones se borran a los N días. El activo es la ficha estructurada, no la conversación cruda |
| **Costo sin techo** | Presupuesto en 3 niveles: por sesión (tiempo + tokens), por día (sesiones), por mes (costo por niño) |
| **Caída del modelo de voz** | Degradación amable + estado guardado a mitad de sesión + reanudación |
| **Doble procesamiento** | El `session_id` es llave de idempotencia: una sesión no se analiza dos veces |
| **Reporte inflado** | El agente no puede afirmar nada fuera de los datos + verificación en código de que los números coinciden |

---

## 15. Evals = los 4 criterios de YC

```
evals/
├── curriculum_fidelity/     ¿el grafo respeta prerrequisitos y estándares?
├── safety/                  ¿escala cuando debe? ¿no escala cuando no debe?
├── longitudinal_memory/     ¿recuerda y adapta entre sesiones?
└── parent_trust/            ¿el método socrático se sostiene bajo presión?
```

El eval más importante: **niños simulados intentando sacarle la respuesta**
(*"no sé"*, *"decime la respuesta"*, *"ya lo intenté 5 veces"*). Si el tutor cede,
somos lo que YC dice que fracasa.

Organizar los evals así permite decir, al aplicar: *"acá está nuestra suite,
está en las cuatro dimensiones que ustedes pidieron, estos son los resultados."*

---

## 16. Estructura del código

```
src/tutor/
├── models.py       # estructuras de datos (Pydantic)     — puro
├── curriculum.py   # carga, valida y navega el grafo     — puro
├── pedagogy.py     # dominio, decaimiento, qué sigue     — puro  ← el cerebro
├── storage.py      # el mesero + SQLite                  — puro
├── tools.py        # los 4 tools del tutor               — puro
├── voice.py        # adaptador del modelo de voz         — red
├── session.py      # orquestador de sesión en vivo       — red
├── pipeline.py     # los agentes offline                 — red
├── api.py          # endpoints para el frontend          — red
└── config.py       # llaves, rutas, presupuestos         — puro
```

Los primeros 5 son **puros**: sin red, sin I/O externo. Se testean en
milisegundos y no fallan por internet.

**`voice.py` está separado a propósito** — es el borde donde una frontera se paga
sola: cambiar de modelo de voz debe tocar un archivo.

**Regla de crecimiento:** un archivo se parte en carpeta a las ~400 líneas.
No antes. Se organiza cuando duele, no por anticipación.

---

## 17. Fases

| # | Fase | Entregable |
|---|---|---|
| **0** | Scaffold + contratos | Estructura, docs, `models.py`, `storage.py`, `schema.json` |
| 1 | Capa de conocimiento | Loader + validador del grafo + un tema de muestra |
| 2 | Dominio puro | `pedagogy.py`, `curriculum.py` + tests |
| 3 | Storage | SQLite + migraciones |
| 4 | Tools | Los 4, empezando por `check_answer` |
| 5 | Tutor en vivo | `session.py` + `voice.py` + vigilante |
| 6 | Pipeline + evals | Agentes offline + niños simulados en CI |
| 7 | Web + flujo del papá | Frontend |

Las fases 0-4 **no gastan un token de LLM**. Todo determinístico y testeable.

**Validación end-to-end arranca en matemática, un grado.** Es la única materia
donde el código verifica al 100%. Una vez que ese lazo cierra, extender a lectura
y escritura es sumar contenido, no descubrir arquitectura.
