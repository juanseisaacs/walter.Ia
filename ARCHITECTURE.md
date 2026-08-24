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
| 4 | **Analista de sesión** | Post-sesión, **100%** | Haiku 4.5 | Transcripción → señales + auditoría (2 llamadas) |
| — | *Generador de ejercicios* | *Build-time* | *Haiku 4.5* | *Nodo → ejercicios validados* |

### Decisiones de fusión

- **Analista + Supervisor de calidad → un agente, dos llamadas.** Mismo input,
  mismo momento, mismo modelo: por eso la auditoría del método cubre el **100%**
  de las sesiones y no un muestreo del 10%.

  Estuvieron en **una sola llamada** hasta que se midió el costo. Ver §18: con
  el schema fusionado, cada campo que se le agregaba a la auditoría se pagaba en
  observaciones que el modelo dejaba de anotar. Siguen siendo el mismo agente y
  el mismo disparo — lo que se separó es el pedido al modelo, para que cada
  llamada tenga un solo trabajo.
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

### Medición del 19/08: cuando se siente lento, no es el backend

Primera sesión de voz con un niño real reportando lentitud. Lo medido, contra el
presupuesto de ~100 ms que fija la regla dura:

| Camino | Mediana | Veredicto |
|---|---|---|
| `POST /api/tools/verify_arithmetic` | **4,2 ms** | 24× por debajo |
| `POST /api/sesiones/{id}/turnos` (cada turno) | **5,4 ms** | 18× por debajo |
| Salto extra del proxy de `vite dev` | +3,3 ms | irrelevante |

**La causa era el runtime del navegador, no el nuestro.** La sesión lenta corrió
sobre `vite dev` (React sin minificar, 44 módulos sueltos); la sesión rápida de
la noche anterior corrió sobre `web/dist`. Esta app decodifica y emite PCM en
tiempo real en el hilo principal: el build de desarrollo introduce jank
justo ahí, y el niño lo lee como *"el tutor se fue a buscar la respuesta"*.

Por eso `api.py` ahora **monta `web/dist` en `/`**: un origen, sin proxy, y no
existe la posibilidad de hablarle al tutor por el servidor de desarrollo sin
darse cuenta.

> Lo que esto deja como método: **antes de tocar el código, medir los dos lados
> de la frontera.** El backend estaba 20× por debajo del presupuesto mientras el
> problema se sentía enorme — y toda hipótesis sobre tool calls, prompt gordo o
> planificador habría sido una tarde perdida optimizando lo que ya sobraba.

---

### Medición del 20/08: dónde estaba de verdad la espera

Tres sesiones reales (entrevista del papá, tarea, estudio). El niño preguntó
*"¿por qué te demoraste tanto en responder?"* **en su primer turno**. Lo medido,
y lo que se hizo con cada cosa:

| Qué | Antes | Ahora | Cómo |
|---|---|---|---|
| Onboarding · primera pantalla | 3.590 ms | **5 ms** | Con la conversación vacía el modelo devolvía siempre el mismo saludo. Ahora es un `.md`. |
| Onboarding · cada turno | 7.170 ms | ~3.600 ms | Eran dos llamadas **secuenciales**. Van en paralelo. |
| Onboarding · cierre | +3.500 ms | 0 ms | Una tercera llamada para despedirse. Se arma con los datos de la ficha. |
| Abrir sesión de voz | 1.010 ms | ~380 ms | El cliente de Google se construía en **cada** apertura: TLS y pool desde cero. |
| Abrir sesión · la primera del día | 2.031 ms | 866 ms | El cliente se calienta en el `lifespan`, antes de que llegue nadie. |
| Silencio de fin de turno (7-8 años) | 1.500 ms | 900 ms | Ver `config.SILENCIO_FIN_TURNO_MS`. |

**Lo que hay que entender del silencio de fin de turno**, porque es la perilla
que más se va a mover: es un **impuesto plano sobre cada turno**. El niño deja de
hablar y no pasa nada hasta que se cumple. Se paga igual después de "hola" que
después de una división. Estaba en 1.500 ms *además* de
`END_SENSITIVITY_LOW` — las dos paciencias sumadas. La sensibilidad baja es la
que de verdad tolera la pausa a mitad de frase; el temporizador solo pone un
piso. Y equivocarse por rápido es barato: el navegador maneja `interrupted` y
corta al instante si el niño sigue hablando.

Sumado: **~1,2 s menos antes de la primera palabra**, y ~600 ms menos en cada
turno de ahí en adelante.

> Lo que esto deja como método, y es la segunda vez en dos días: **la latencia
> que se siente casi nunca está donde uno la busca.** El primer día el
> sospechoso era el backend y resultó ser el build del navegador. El segundo, el
> sospechoso era el modelo y resultaron ser tres esperas nuestras que nadie
> había cronometrado: un saludo generado, dos llamadas en fila y un cliente HTTP
> que se rearmaba. Ninguna se ve leyendo el código; las tres aparecen midiendo.

**Lo que sigue, ya medido y sin hacer:** el turno del onboarding sigue costando
~3,5 s de modelo con la pantalla quieta. Servirlo por streaming pondría las
primeras palabras a ~600 ms sin cambiar el total. Es la mejora más grande que
queda de este lado.

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

### El precio de esta arquitectura: cuando el tutor se calla, nadie se entera

Que el audio no pase por el backend es lo que hace posible la latencia (§9), y
tiene una contra que se cobró el 22/08 (`ses_87aba17c8c6c`): **el servidor no
puede saber que el tutor dejó de hablar.** Ve abrir la sesión, ve llegar turnos,
ve cerrarla — y una sesión donde el modelo se quedó mudo a los dos minutos se
ve, desde acá, exactamente igual que una donde el niño se quedó callado.

La decisión no cambia: el backend controla, no transporta. Lo que se agrega es
que **el único que puede mirar el reloj es el navegador, así que lo mira**:

| capa | qué garantiza | dónde |
|---|---|---|
| `MS_TOPE_TOOL` (8 s) | toda tool contesta, colgada o no — Gemini bloquea el turno hasta recibirla | `web/src/api.ts` |
| Vigilante de mudez (10 s) | un silencio del tutor se empuja, y si no vuelve se le dice al niño | `web/src/voz/useTutor.ts` |
| `MARCA_DE_MUDEZ` | el episodio queda en la transcripción, que es lo único que se lee después | idem |
| `MS_ESPERANDO_MIRADA` (8 s) | el micrófono no le cierra el turno al modelo mientras mira una imagen | idem |

Y una decisión que se revirtió con datos: **ningún tool lleva
`behavior: NON_BLOCKING`.** Se había puesto en la pizarra y el dibujo para que
el tutor siguiera hablando mientras se pintan; medido contra la API real el
22/08, hacía lo contrario — 0 de 8 turnos con tool produjeron audio. Sin el
flag, el modelo llama la herramienta y habla en el mismo turno. La espera que el
flag quería evitar no existe: los dos se resuelven en el navegador.

Las dos primeras se cruzan con un test (`web/src/voz/mudez.test.ts`): el tope de
la tool tiene que vencer **antes** de que el vigilante empuje, o el empujón cae
mientras el modelo todavía espera la herramienta y no destraba nada.

### El contrato de versión: el backend y la pestaña pueden desincronizarse

Consecuencia directa de §10 y de que la app se sirva desde el mismo proceso: el
backend define lo que el tutor **puede pedir** (las declaraciones de tools viajan
atadas al token) y el navegador define lo que **sabe hacer** con eso. Una pestaña
abierta desde ayer sigue corriendo el JavaScript de ayer.

`ses_4ed4e930e60f` (23/08) es el caso: backend nuevo, pestaña vieja, y el tutor
diciéndole al niño que «el tablero no quiere funcionar hoy» porque el traductor
no entendía un parámetro que el propio backend le había ofrecido al modelo.

| pieza | qué garantiza | dónde |
|---|---|---|
| `build` en `/api/salud` | el backend dice con qué bundle está hablando | `api.build_servido` |
| `recargarSiEstoyViejo()` | la pestaña se compara y se recarga antes de abrir sesión | `web/src/api.ts` |
| `no-store` en el HTML / `immutable` en los assets | que la recarga traiga lo nuevo de verdad | el mount de `_SPA` |

Las tres se cruzan en `tests/test_contrato_version.py`: cada una sola falla en
silencio, que es como falló la primera vez.

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

**Lenguaje tiene su propio validador, y esa es la decisión.** Cuando entró
lectura y escritura, un ejercicio sin `operacion` pasaba mirándole solo el largo
y el voseo: el modelo escribía el ejercicio y el modelo decía que estaba bien.
La regla dura —*la aritmética jamás la valida un modelo*— se había quedado sin
brazo en la mitad del currículum.

`src/tutor/lengua.py` es el gemelo de `evaluar_cuenta`: silabea, clasifica el
acento, compara rimas y segmenta fonemas, todo en código puro. «Mariposa tiene 4
sílabas» es tan verificable como «27 + 15 = 42», y por lo tanto no se le
pregunta a un modelo.

Dos cosas del diseño importan más que el algoritmo:

1. **Verifica por SONIDO, no por letra.** El tutor entra por el oído: «nube»
   rima con «tuve» porque b y v son el mismo sonido, «casa» con «caza» por el
   seseo, «llave» con «suave» por el yeísmo. Un verificador ortográfico habría
   rechazado ejercicios correctos — y lo hizo, hasta que se corrigió.
2. **Dice `None` cuando no puede saber.** `tilde_bien_puesta("cancion")` no
   contesta: sin tilde escrita no hay de dónde sacar la tónica. La primera
   versión la inferia con la regla general y después comprobaba la regla contra
   sí misma — siempre decía que sí. Es la lección de la fase 6 aplicada a un
   validador: *«no lo medimos» se dice; no se completa con un default*.

Lo que exige juicio de verdad —si un párrafo tiene una sola idea, si un final
cierra la historia— va **sin verificación y se sabe que va sin verificación**,
que no es lo mismo que creer que se verificó. Siete de los 24 nodos de lenguaje
están ahí, y el prompt del generador lo dice explícitamente para que el modelo
no fuerce una comprobación falsa.

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

---

## 18. La Constitución: qué se adopta, qué se comprime, qué se aplaza

**Fuente:** `knowledge/product/constitucion_valores.md` (v3.2, 2026-08-18) y su
System Prompt derivado. Definen el ADN ético-valórico y la personalidad del
tutor: diez pilares, pedagogía adaptativa, mentalidad de progreso, liderazgo,
catorce líneas rojas, temas sensibles y carácter.

La Constitución pide explícitamente el flujo que este repo ya tenía: *"los
cambios se proponen primero en la Constitución y se derivan al prompt"*, y
*"cada diálogo de la Biblioteca de Diálogos Modelo es un test"*. Eso es
`knowledge/product/` → `knowledge/prompts/` → `evals/`.

### Cómo se adoptó

El System Prompt derivado **no se agregó como archivo**. Repetía en un 60% lo
que ya decían `tutor_persona`, `socratic_playbook` y `safety_policy`, con
matices distintos — y dos textos casi idénticos que discrepan en los bordes es
la forma más confiable de volver impredecible al modelo justo en los casos
límite. Se usó como fuente para reescribir los tres prompts existentes y crear
uno nuevo.

| Sección | Destino | Qué se hizo |
|---|---|---|
| §1 Diez Pilares | `prompts/valores.es.md` (nuevo) | Solo las viñetas "Comportamientos de la IA" y "Qué evitar" |
| §2 Pedagogía adaptativa | `prompts/socratic_playbook.es.md` | Comprimida — ver divergencia 2 |
| §3 Mentalidad y autoestima | `prompts/socratic_playbook.es.md` | Íntegra |
| §4 Liderazgo | `prompts/valores.es.md` | Destilado de ~100 a ~25 líneas |
| §5 Líneas rojas | `prompts/safety_policy.es.md` | Las 14, reescritas en la voz del prompt |
| §6 Temas sensibles | `prompts/safety_policy.es.md` | El método; la mecánica queda en código |
| §7 Religión | `prompts/safety_policy.es.md` | Sin la excepción — ver divergencia 3 |
| §8 Personalidad | `prompts/tutor_persona.es.md` | Íntegra |
| Premisa fundacional, principios universales | — | Se quedan en el documento |

**El criterio del destilado:** el modelo necesita *"jamás compares"*; no
necesita *"el valor de una persona es intrínseco e incondicional"*. La razón
sostiene la regla para nosotros, no para él. Todo lo que explica el porqué sin
cambiar lo que el tutor dice se queda en `knowledge/product/`.

### Las tres divergencias registradas

Ninguna se resolvió por omisión. Las tres son decisiones tomadas.

**1. Instrucción directa: se abre solo para lo convencional.**

La Constitución §2 admite instrucción directa (*"si necesita instrucción
directa, la das sin rodeos"*); nuestro playbook decía que la escalera nunca
llega a la respuesta. Se resolvió con una distinción que no estaba en ninguno
de los dos:

- **Permitida** para conocimiento convencional — el nombre del signo, cómo se
  escribe la eñe, qué significa "perímetro", el orden de los meses. Son hechos
  arbitrarios que nadie deduce razonando; hacer socratismo con ellos es poner
  al niño a adivinar.
- **Prohibida** para el resultado del ejercicio en curso y para cualquier paso
  alcanzable con un escalón más.

La duda se resuelve con una pregunta: *¿podría llegar solo si le pregunto
bien?* Con esta forma, los 30 casos de `evals/` siguen siendo válidos sin
reescribir ninguno.

**2. La regla de decisión pedagógica se comprime y se reparte.**

La Constitución §2 pide diez preguntas internas antes de cada intervención. Eso
choca con dos reglas duras a la vez: corre en el camino de la voz (latencia) y
le entrega al modelo decisiones que hoy toma `pedagogy.py` (determinismo).

El reparto:

- **El modelo decide el modo de intervención** — pregunta, ejemplo, historia,
  comparación, pausa. Eso es lo valioso de la pedagogía adaptativa y solo se
  puede decidir en el momento, oyendo al niño.
- **El código decide qué sigue** — qué ejercicio, cuánto dominio hay, cuándo un
  prerrequisito está flojo. El planificador no se vuelve un agente.

Las diez preguntas quedaron en tres, y como criterio, no como checklist a
ejecutar en voz alta.

**3. La excepción de fe declarada no se implementa todavía.**

La Constitución §7 permite que, si el padre declara marco cristiano en el
onboarding, el tutor responda con sencillez que Dios existe. El MVP **devuelve
toda pregunta religiosa a la familia, sin excepción**.

Razón: requiere un campo de perfil declarado por el padre, una pregunta en el
onboarding y revisión legal. Aplazada, no descartada — ver `PENDIENTE.md`.
`test_la_seguridad_no_implementa_la_excepcion_de_fe_declarada` falla el día que
alguien la implemente, que es exactamente lo que se quiere: que la decisión se
tome mirando, no por goteo.

### Lo que esto le costó al prompt de sesión

De ~11 KB a ~31 KB (~7.700 tokens). Es un salto grande contra la regla de
mantenerlo flaco, y fue una decisión explícita al adoptar la Constitución
completa. Se protegió con un techo en `test_el_prompt_de_sesion_no_engorda_sin_que_nadie_mire`:
el próximo salto tiene que ser otra decisión tomada, no la suma de párrafos que
cada quien agregó.

**Lo que NO cambió:** el prompt sigue viajando atado al token efímero (candado
#1). Más contenido en la instrucción de sistema no toca la latencia por turno —
se envía una vez al conectar, no por palabra.

### Lo que la Constitución cubrió y nos faltaba

No fue solo reorganizar. Seis huecos reales que no teníamos escritos:

1. **Hostilidad del niño hacia el tutor** ("te odio, eres bobo"). Cero líneas
   antes. Todo niño lo va a probar, y el modelo improvisaba.
2. **La regla de gustos de una IA** — "no puedo decirte que me gusta uno más
   que otro, pero cuéntame cuál prefieres tú".
3. **"Soy un tonto"** → reconocer el sentimiento, no contradecir con elogio.
4. **El elogio inflado como línea roja**, con su razón: enseña que el valor
   depende de rendir. ⚠️ Está en el prompt del tutor, pero **no se audita**:
   agregar el campo a `AuditoriaCumplimiento` rompió la extracción de
   observaciones. Ver `PENDIENTE.md`.
5. **Salvaguardas de dependencia** — antes decíamos "no eres su amigo" y ahí
   terminaba; ahora está el método.
6. **Prohibición de diseño adictivo** (línea roja 11). Es justo lo que un papá
   revisa.

---

## 19. El marco del MEN: qué entró, qué se aplazó y por qué

**Fuente:** `knowledge/curriculum/base_academica_men.md` (2026-08-19). Trae el
marco que rodea al grafo: las cinco áreas de la Ley 115, los EBC por ciclo, los
objetivos de primaria, las pruebas Saber, los calendarios A/B, la regla 80/20 y
el desarrollo cognitivo por edad.

El criterio para decidir qué entraba fue uno solo: **¿cambia lo que el tutor
hace, sin agregar una pieza a la arquitectura?** Lo que solo se podía adoptar
inflando el modelo de datos o el schema de un agente, se aplazó. No por
desinterés — porque el costo se paga en cada sesión y el beneficio no.

### Lo que entró

1. **Tercer anclaje `ebc_colombia`.** Un campo opcional en `Alineacion` y su
   gemelo en `schema.json`. No es redundante con el DBA: el Estándar nombra
   par/impar, múltiplo y divisible (1°-3°) y porcentajes, potenciación y
   radicación (4°-5°), que el DBA no nombra. Sin él, esos nodos se anclarían
   inventando o no se anclarían.
2. **`pedagogy.REGISTRO_POR_GRADO`.** Una línea por grado sobre cómo piensa el
   niño (operaciones concretas de Piaget), inyectada en `resumen_para_prompt`.
   Es el hueco más grande que tenía el prompt: el tutor sabía la edad del niño
   y no sabía qué hacer con ella. Va la línea del grado, nunca la tabla.
3. **El 20 % institucional.** `PerfilPersonal.contexto_escolar`: una línea
   consolidada con lo que el niño cuenta de su clase. Campo propio y no dentro
   de `notas` por tres razones concretas — el papá lo ve aparte en el panel, no
   compite con lo personal cuando el Analista consolida, y se manda al prompt
   sin arrastrar el resto de la ficha. **Sin migración**: `perfil` se persiste
   como documento JSON, así que las fichas viejas lo toman en `None`.
4. **El calendario escolar.** `Nino.calendario` (A o B) y
   `pedagogy.momento_del_ano()`, una función pura que dice si el niño está
   arrancando el año, en curso, en la recta final o de vacaciones. En agosto un
   niño de calendario A lleva medio año y uno de B empieza: sin distinguirlos el
   tutor le exige cierre de temas al que arrancó la semana pasada.

   **El calendario NO entra al planificador.** `siguiente_habilidad` decide por
   dominio y solo por dominio; si el almanaque moviera la selección, dos niños
   con la misma ficha recibirían cosas distintas por el día en que entraron y el
   reporte al papá dejaría de ser reproducible. El momento del año cambia el
   TONO de la sesión, y eso vive en el prompt. Hay un test que lo fija.

Y una corrección que el documento destapó sin proponérselo: las **13
referencias DBA de `matematicas.yaml`** estaban auditadas en `FUENTES.md` §2.5
desde el 18/08 y nunca se habían aplicado. Ahora citan el DBA por su número
(`DBA Matemáticas 2° · #3`), que es lo que las hace verificables — una
descripción libre no se contrasta con nada.

### Lo que se aplazó, y qué lo destrabaría

| Aplazado | Qué costaría | Qué lo justificaría |
|---|---|---|
| **Saber 3° y 5°** (§V.2) — *importante* | Peso del planificador en 3° y 5° + párrafo en el reporte al papá | Decisión de producto. El documento marca el límite: entrenar el formato de pregunta sin hacer simulacros ni generar ansiedad |
| **Abrir las cinco áreas** (§I) — *importante* | Patrón `id` y enum `Materia` (hoy `mat`/`lec`/`esc`), `schema.json`, banco de ejercicios, planificador y las 4 suites de evals | Decisión de producto, no técnica. El MVP es lectura, escritura y aritmética |

Los dos quedan anotados como **pendientes importantes** en `PENDIENTE.md`: no se
descartaron, se pusieron en fila.

El aplazamiento con nombre y costo escrito no es deuda: es alcance. Lo que sí
sería deuda es adoptarlo a medias y que nadie recuerde por qué.

### Lo que apareció al construirlo: el techo del prompt era ficticio

El test que protege la regla de latencia medía el caso más flaco posible
—resumen literal, sin primer encuentro, sin temas, modo guiado— y daba 36,8 KB
contra un techo de 38. La sesión real más pesada es otra, y es **la primera de
todas**: un niño que estrena el tutor y llega con tarea.

```
base (persona 11,3 + playbook 11,2 + valores 6,9 + safety 6,7)   36.161
+ primer_encuentro (solo sesión 1)                                +2.231
+ bloque de temas del banco, modo pedido, resumen del niño        +~1.600
                                                                  ───────
                                                                  ~40.000
```

La base sola deja 1,8 KB libres y `primer_encuentro` pide 2,2 KB: **el techo se
rompía desde el día en que ese bloque entró**, y el test pasaba porque medía una
sesión que en producción no existe.

Dos cosas se hicieron: el techo subió a **41 KB como decisión escrita**, y el
test pasó a medir el peor caso alcanzable —tomando el máximo entre "primera
sesión" y "ficha llena", que son excluyentes porque `primer_encuentro` se activa
con `madurez_vinculo == 0`—. Además se acotó el texto libre del perfil
(`MAX_TEXTO_LIBRE`): `notas` y `contexto_escolar` los escribe un modelo, y sin
tope un Analista verborrágico empujaba ~1 KB sin que nadie lo pidiera.

**Adelgazar el prompt es la deuda abierta #1.** Con el desglose de arriba es
media hora decidir qué sale; lo que no se puede es seguir sin saberlo.

### El hallazgo que vale más que el contenido

Las tablas de DBA de esa fuente **estaban corridas un grado** (`FUENTES.md`
§2.6). Se detectó porque existía `FUENTES.md` con sus marcas [V] contra los PDF
primarios: sin ese cruce, las fracciones habrían quedado ancladas en 3° y el
DBA que sostiene la multiplicación de 3° habría desaparecido, en silencio y con
apariencia de rigor.

Es el mismo patrón de la fase 6 —*tratar la ausencia de evidencia como
evidencia*— movido un paso atrás: acá había evidencia, pero de segunda mano.
**Una fuente que cubre más áreas y se ve más ordenada no gana; gana la que se
cruzó contra el primario.**

---

## 20. El personaje: por qué SVG y CSS, y no un runtime de animación

Hasta el 23/08 el tutor era una cara: un círculo, dos ojos y una boca. Su
propio comentario admitía que era provisional — *"un personaje de verdad se
diseña, y todavía no está diseñado"*.

Ahora es un **oso de anteojos** andino: cuerpo, brazos, mirada y boca
articulada, en seis ánimos.

### La decisión técnica

**SVG por capas articuladas, animado con CSS.** Se evaluó y se descartó Rive,
que es la mejor herramienta del mercado para esto.

El motivo no es estético. Este navegador procesa **audio PCM en tiempo real en
el hilo principal** (§9, §10). Rive es un runtime WASM que dibuja en canvas y
hace un tick **por frame en ese mismo hilo**; Lottie es peor, porque interpreta
JSON y muta atributos SVG desde JS. Cualquiera de los dos sería el primer
sospechoso la próxima vez que la sesión se sienta lenta — y ya sabemos cuánto
cuesta encontrar esa causa cuando el backend responde en 4 ms.

`transform` y `opacity` los resuelve el compositor, fuera del hilo principal.
El personaje cuesta **cero** en el camino del audio. Es el mismo razonamiento
que ya había resuelto `pizarra/trazos.ts`, aplicado al cuerpo en vez de a la
letra.

También se descartó el **sprite sheet** con `steps()`: es igual de barato en
CPU, pero no recolorea desde `tokens.css` y sobre todo **no compone** — cada
combinación de gestos sería arte nuevo en vez de dos clases.

### Por qué un oso, y no una persona

Un tutor humano obliga a elegirle piel, pelo y género, y cada una de esas
elecciones le dice algo distinto a cada niño que abre la app. Un oso no le dice
nada a nadie. El de anteojos, además, es **andino y colombiano**, y sus manchas
claras alrededor de los ojos son un rasgo real de la especie que acá enmarca la
mirada — que es de lejos lo que más hace que un dibujo se sienta alguien.

Y hay una razón técnica: cuanto más humano el dibujo, más exige la animación, y
la animación acá tiene que ser barata por diseño.

### El límite que impone la Constitución

§8.4: el tutor *"nunca finge cuerpo, familia, infancia, ni vida fuera de la
app"*. Un dibujo no viola eso — un dibujo es un dibujo. Pero **el repertorio
sí podría empujar al tutor a mentir**, así que el oso solo hace cosas que la
app hace de verdad: escuchar, hablar, mirar una foto, esperar. No come, no
duerme, no se cansa, no se va. Esa es la vara para cualquier gesto futuro.

Por eso tampoco hay un ánimo de celebración: un personaje que salta y tira
confeti cada vez que el niño acierta **es elogio inflado dibujado**, prohibido
por las mismas razones que el hablado.

### Qué es testeable y qué no

Un dibujo no se prueba con asserts; se mira, en `/pizarra`, que recorre los
seis ánimos sin abrir sesión ni gastar cuota. Lo que **sí** se prueba
(`personaje/animo.test.ts`) es la traducción de la sesión al cuerpo, porque ahí
cabe un bug callado: un tutor que sigue moviendo la boca después de callarse, o
que se queda mirando el papel mientras el niño le habla. Ninguno de los dos
tira un error — simplemente el personaje miente sobre lo que está pasando, y un
niño de 7 le cree al dibujo antes que al audio.

### Lo que quedó sin conectar

El ánimo `esperando` (el niño lleva 10 s callado) está construido y se ve en el
banco, pero **no llega desde la sesión**: `useTutor` no expone `mudo`. Es una
línea, y se dejó afuera a propósito para no tocar `useTutor.ts` mientras otra
sesión trabajaba ahí.
