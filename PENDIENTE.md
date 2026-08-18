# Pendiente — retomar acá

_Última actualización: 2026-08-18, después de cerrar el reporte al papá y correr
los evals completos._

## Estado: el circuito completo cierra, y está verificado salvo la voz

Once commits desde `aa76bd0`. **267 tests en verde. Evals 30/30**, estable en
dos corridas seguidas.

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
