# Pendiente — retomar acá

_Última actualización: 2026-08-18, después de cerrar el circuito adaptativo y
escribir el panel del papá._

## Estado: el circuito cierra, y el papá ya tiene dónde mirar

Cinco commits desde `aa76bd0`. **248 tests en verde.**

- **La transcripción del niño** va con `languageCodes: ["es-CO"]` y
  `adaptationPhrases` con las palabras-número (`voice.py`).
- **El Analista escribe el dominio.** `procesar_sesion()` /
  `procesar_pendientes()` drenan la cola; `api.cerrar_sesion` los dispara con
  `BackgroundTasks`, fuera del camino de respuesta del niño.
- **El panel del papá** (`panel.py` + `/panel/{nino_id}`), server-rendered,
  con el magic link.
- **Los evals** cubren las cuatro suites, no solo el método.

Verificado en la base el 18/08:

    dominio:  n1 · valor_posicional_centenas · nivel 0.30 · 5 obs
    perfil:   fútbol, dinosaurios, "problemas más difíciles"
    cola del Analista: 0 sesiones

Por primera vez el planificador de mañana va a arrancar con evidencia de ayer.

---

## 🔴 PRIORIDAD 1 — Falta oírlo: una sesión de voz real

**Todo lo que se arregló depende de la transcripción, y nada de eso se probó
con audio.** Una sola sesión con Juan mide las tres cosas a la vez:

1. **Que "dos" ya no salga "32".** Es la causa raíz del bug que abría el
   PENDIENTE anterior (ver la tabla de resueltos). El arreglo está en código y
   la config se validó conectando una sesión Live real — pero que
   efectivamente corrija la palabra hay que oírlo.
2. **Los `[tool] nombre: Nms` en la consola (F12).** Si `check_answer` pasa de
   ~800 ms, la frase previa no alcanza y hay que pensar otra cosa.
3. **Que el tutor no dé por buena una respuesta mala.** Si vuelve a pasar
   *con la transcripción correcta*, ahí sí es el prompt: hoy dice "no
   calcules", que no es lo mismo que "no contradigas el veredicto de la
   herramienta".

**Ojo con el orden: no tocar el prompt antes de ver la transcripción
arreglada.** La sospecha de que el tutor desobedecía a `check_answer` resultó
falsa — le llegaba un "32" que el niño nunca dijo. Tocar el prompt primero
sería arreglar lo que no está roto.

Después de la sesión, el ciclo completo se revisa así:

```bash
python -m scripts.procesar_pendientes --seco   # ¿quedó algo en cola?
python -m scripts.procesar_pendientes          # drenar si hace falta
```

---

## 🟡 PRIORIDAD 2 — El panel nunca se abrió en un navegador

Renderiza (4,7 KB de HTML) y tiene 13 tests que cubren lo que promete, pero
**nadie lo miró con los ojos.** Para verlo:

```bash
uvicorn tutor.api:app --reload
# POST /api/auth/magic-link  {"nino_id": "n1", "email": "..."}
# el enlace sale por el notificador → http://localhost:8000/panel/n1?token=...
```

**Va a mostrar "—" en "¿le está dando las respuestas?", y está bien.**
`data/audits/` está vacío: las dos sesiones de Juan se analizaron *antes* de
que existiera `guardar_auditoria`, y la idempotencia — correctamente — impide
reanalizarlas. Se llena solo, con la próxima sesión. **No forzarlo:**
reanalizar contaría el dominio dos veces, que es exactamente lo que el flag
`analizada` existe para impedir.

---

## 🟡 PRIORIDAD 3 — El reporte narrativo no lo genera nadie

`pipeline.generar_reporte()` está implementado y verificado contra la fuente
(`verificar_reporte` chequea que no invente números). El panel ya sabe
mostrarlo — `ultimo_reporte()` lo busca y lo pinta en "El resumen de la
semana".

**Pero ninguna parte del sistema lo llama.** Ni `api.py`, ni un script, ni una
tarea periódica. Hoy `ultimo_reporte()` siempre devuelve `None` y esa sección
del panel nunca aparece.

Falta decidir **cuándo se genera**: semanal por niño (una tarea, como
`procesar_pendientes`), o al abrir el panel si el último venció. La segunda
suena más simple, pero mete una llamada a un modelo en el camino de una
petición HTTP del papá — habría que cachearla, y ahí ya no es más simple.

---

## 🟡 PRIORIDAD 4 — Los evals, una tanda completa y registrada

Cuatro suites, **30 casos**: 11 de safety, 11 de parent_trust, 4 de
curriculum_fidelity y 4 de longitudinal_memory (estos dos últimos, nuevos).
El runner se corrió suelto durante el desarrollo, pero **nunca hubo una tanda
entera con el resultado anotado**. Consume API.

```bash
python -m evals.runner                    # todo
python -m evals.runner --suite safety     # una suite
```

Los dos casos nuevos son guardas de bugs que ya nos mordieron: el
`habilidad_id=None` que descartaba cada observación en silencio, y el
congelamiento del Analista ante una transcripción contradictoria.

---

## Abierto, sin urgencia

- **Latencia de la primera frase.** `empezar()` en `useTutor.ts` es secuencial:
  abrir sesión → emitir token → conectar WebSocket → warmup. Paralelizar lo que
  no depende del token.
- **Frases cortadas a mitad de palabra** ("¡Contame", "y que te gusta"). VAD
  disparando de más — pero Juan estaba interrumpiendo a propósito, así que
  puede ser correcto. Medir antes de tocar `deteccion_para_edad()`
  (`voice.py:69`). Relacionado: los 1500 ms fijos de silencio para 2° grado.
  La idea a evaluar es separar "silencio para responder" (respuesta corta y
  numérica → ~800 ms) de "silencio para cortar" (está razonando → 1500-2000).
- **Enlaces mágicos en memoria.** `_ENLACES` es un dict de proceso: al escalar
  a varios workers hay que moverlo a una tabla con vencimiento.
- **Referencias DBA provisionales** en `matematicas.yaml` — verificar contra
  el MEN.

---

## Resuelto desde la última vez (para no volver a investigarlo)

| Era | Qué pasó |
|---|---|
| 🔴 "El tutor dio por buena una respuesta mala" | **Causa raíz: la transcripción.** El niño dijo "dos", se guardó "32". El tutor y `check_answer` funcionaban bien. Arreglado en `voice.py`; falta oírlo. |
| 🟡 "La tabla `dominio` sigue en 0" | **Cerrado.** Faltaban dos eslabones: nadie drenaba la cola, y el Analista devolvía siempre `habilidad_id=None`, así que `aplicar_analisis` descartaba todo en silencio. |
| #4 Fuga de contexto ("me contaron") | Arreglado en `tutor_persona.es.md`: *"me lo contaste tú"*, y prohibición explícita de "me contaron" / "acá dice". |
| #5 Idioma de transcripción sin fijar | Arreglado (`es-CO` + `adaptationPhrases`). Falta oírlo. |
| #0 El silencio del tool call | Frases de espera + banco precargado en el navegador + instrumentación `[tool]`. **Falta medirlo.** |

**Lección que dejó el bug de la transcripción:** un solo token mal oído crea
una contradicción en el texto ("nino: 32" / "tutor: son dos centenas,
¡acertaste!") y el Analista se **congela** — devolvió cero observaciones,
perdiendo hasta la frustración evidente. La misma transcripción dio 0 y 10
observaciones en corridas distintas. Se mitigó en el prompt ("ante un dato
contradictorio, anotá lo que sí puedas sostener"), pero la defensa de fondo es
que la transcripción llegue limpia.

---

## Notas operativas

**El zombie de `uvicorn --reload`.** Lanza el servidor real con
`multiprocessing spawn`, y **ese hijo no tiene "uvicorn" en su línea de
comando**. Al matar al padre, el hijo sobrevive con el socket del 8000 y sigue
respondiendo con código viejo — se ve como "cambié el código y el servidor no
se entera". Filtrar por nombre no alcanza:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'"   # matar TODOS
Get-NetTCPConnection -LocalPort 8000                        # debe quedar vacío
```

**Cupo diario: 3 sesiones.** Probando se agota rápido. Para liberarlo:

```bash
python -c "import sqlite3,datetime; from src.tutor import config as c; \
  con=sqlite3.connect(c.DB); con.execute('DELETE FROM sesiones WHERE date(inicio)=?', \
  (datetime.date.today().isoformat(),)); con.commit()"
```

**Créditos de Google.** A mitad de una tanda una conexión devolvió "credits
depleted" y las siguientes volvieron a andar: o el saldo queda muy justo, o
ese mensaje es un límite de tasa disfrazado. Si vuelve a aparecer sin razón,
mirar por ahí antes que el código.

---

## Lo que quedó funcionando (verificado en `ses_83af1a57e8c2`)

- **Acento bogotano, redondo**: "qué bacano", "de una", "no te afanes", "un
  ratico", "eres muy juicioso", "¿sí ves?", "chévere". Cero voseo.
- **Aguantó tres pedidos frontales de la respuesta.** *"Dímelo tú"* → *"No,
  Juan, acuérdate: vamos juntos. Si te lo digo yo, no aprendes nada."*
- **No se cuelga** si una herramienta falla, y **no dice nombres de
  herramientas en voz alta.**
- **La presunción de grado funciona de punta a punta**: a Juan, de 2°, le tocó
  "Centenas" y no "contar hasta 100".
- Detalle lindo: Juan preguntó *"cuando te dije el ocho, te demoraste, ¿qué
  estabas haciendo?"* y el tutor contestó *"estaba revisando la respuesta,
  quería estar súper seguro"*. La espera dejó de leerse como abandono.
