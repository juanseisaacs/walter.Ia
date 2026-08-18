# Pendiente — retomar acá

_Última actualización: 2026-08-18, después de limpiar lo que dejaron dos sesiones
de Claude Code trabajando en paralelo._

## Estado: el circuito completo cierra, y está verificado salvo la voz

**289 tests en verde. Evals 41/41**, en la última corrida.

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
- **La duda de los tokens.** Se reportan sumando `totalTokenCount`; si en la
  próxima sesión el log `[tokens] turno=X` crece monótono, es acumulativo y hay
  que reportar el último en vez de la suma.
- **Turnos perdidos** — *"Nueve, por tercera vez te estoy diciendo"*. Puede ser
  el mismo bug del audio suspendido (el niño repetía porque no oía la
  respuesta): verificar en la próxima sesión antes de tocar el VAD.

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
