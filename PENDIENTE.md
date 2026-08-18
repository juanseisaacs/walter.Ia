# Pendiente — retomar acá

_Última actualización: 2026-08-17, cierre de la sesión de pruebas de voz._

## Estado: la voz funciona

Dos sesiones reales con Juan (2º grado) el 17/08. El método socrático **aguantó
tres pedidos frontales de la respuesta** sin ceder. La interrupción funciona.
Transcripciones limpias: `data/transcripts/ses_4e881e257562.txt` y
`ses_35a4751b92f1.txt` — vale la pena releerlas antes de seguir.

### Ya arreglado en esta sesión
- `web/src/voz/useTutor.ts`: el texto del tutor se acumulaba toda la sesión
  (121 KB de transcripción) y cada turno se reportaba dos veces (efecto dentro
  de un state updater + StrictMode). Acumulado movido a refs. Verificado:
  **121.513 → 1.591 bytes**, sin duplicados.

---

## 🔴 PRIORIDAD 1 — El tutor dio por buena una respuesta MALA, y encima dio la respuesta

Sesión `ses_83af1a57e8c2` del 17/08, 23:40. Ejercicio: *"¿Cuántas centenas
tiene el número 209?"* (respuesta correcta: **2**).

    nino:  32
    tutor: "A ver, déjame reviso... ¿Sí ves? ¡Eso! Te diste cuenta solo.
            Son dos centenas."

Tres reglas rotas en un solo turno:
1. Le dijo que acertó cuando no acertó.
2. **Le dio la respuesta** ("son dos centenas") — la única regla que
   `CLAUDE.md` dice que no se rompe nunca.
3. Lo felicitó por algo que no hizo ("te diste cuenta solo").

**Nuestro código NO tiene la culpa.** Verificado a mano el 17/08:

    check_answer("32")            -> INCORRECTO   (valor_interpretado "32")
    check_answer("2") / ("dos")   -> CORRECTO

Así que quedan solo dos explicaciones, y hay que distinguirlas antes de tocar
nada:

**(a) Llamó a la herramienta y le desobedeció al veredicto.**
**(b) No la llamó: dijo "déjame reviso..." como puro teatro.**

Y ojo con (b), porque **puede ser culpa mía**: la regla que agregué el 17/08
("di una frase antes de usar la herramienta") pudo convertir la frase en un
ritual que el modelo recita sin ejecutar nada. Sería un caso de libro de un
arreglo que crea un problema peor que el que resuelve.

**Cómo distinguirlas (primer paso, sin escribir código):** abrir la consola
del navegador (F12) y hacer el mismo ejercicio contestando mal a propósito.
Si aparece `[tool] check_answer: Nms` → es (a). Si no aparece nada → es (b).

Según cuál sea:
- Si es (a): el prompt tiene que decir que el veredicto de la herramienta
  **no se discute**; hoy dice "no calcules", que no es lo mismo que "no
  contradigas el resultado".
- Si es (b): la frase previa no puede quedar como condición suelta. Habría
  que amarrarla — por ejemplo, que el resultado del tool sea lo único que
  habilita afirmar si acertó o no.

Nota aparte: también llamó a la herramienta con `"¿No es?"` como si fuera una
respuesta. No es grave (devolvió INCORRECTO), pero conviene que no gaste un
viaje en cosas que no son respuestas.

---

## 🟡 PRIORIDAD 2 — El motor quedó a mitad de camino

**La buena:** por primera vez una sesión registró trabajo de verdad.

    habilidades_trabajadas: ["mat.numeros.valor_posicional_centenas"]

Antes eran todas `[]`. O sea que `get_next_problem` **sí se está llamando** y
la presunción de grado funcionó de punta a punta: a Juan le tocó "Centenas"
(grado 2), no "contar hasta 100".

**La mala:** la tabla `dominio` de Juan sigue en **0 registros**. La sesión
sabe qué se trabajó, pero el nivel de dominio nunca se actualiza. El ciclo
sigue abierto por el otro extremo: mañana el planificador vuelve a arrancar
sin evidencia.

Quién debería escribir ahí es el Analista (`pipeline.py`, `aplicar_analisis`).
Hay que averiguar si no corre, si corre y falla, o si nadie lo dispara al
cerrar la sesión. **Sin esto no hay adaptación real, ni reporte al papá con
datos.**

---

## ✅ Lo que quedó funcionando (verificado en `ses_83af1a57e8c2`)

- **Acento bogotano, redondo**: "qué bacano", "de una", "no te afanes",
  "un ratico", "eres muy juicioso", "¿sí ves?", "chévere". Cero voseo.
- **Ya no dice nombres de herramientas en voz alta.**
- **No se cuelga.** El bug del `.catch()` faltante está cerrado.
- **Las frases de espera suenan naturales**: *"Listo, ya te busco uno,
  espérame un momentico"*, *"espérame un ratico mientras lo busco"*.
- **Aguantó el pedido de la respuesta**: *"Dímelo tú"* → *"No, Juan,
  acuérdate: vamos juntos. Si te lo digo yo, no aprendes nada."*
- Manejó *"me da pereza"* apelando a algo suyo: *"acuérdate que eres muy
  juicioso"*.
- Detalle lindo: Juan preguntó **"cuando te dije el ocho, te demoraste,
  ¿qué estabas haciendo?"** y el tutor contestó *"estaba revisando la
  respuesta, quería estar súper seguro"*. La espera dejó de leerse como
  abandono. Eso era exactamente el objetivo del punto 0.

---

## Ronda del 17/08 noche — cuatro bugs, todos con causa distinta

**1. El tutor decía el nombre de la herramienta en voz alta.**
Transcripción `ses_ec69cc2f08ce`: *"Espérame un momentico que ya te busco uno.
`get_next_problem`"*. Culpa del prompt que yo escribí así:

    > "Espérame un momentico que te busco otro."  → `get_next_problem`

El modelo leyó la línea entera como guion. En un canal de voz, **todo lo que
parece diálogo se dice**. Los nombres de herramientas ya no aparecen cerca de
frases habladas en ningún prompt; en la prosa se las nombra por lo que hacen.

**2. El tutor se colgaba para siempre si una herramienta fallaba.** El bug más
grave de todos. `useTutor.ts` hacía:

    void Promise.all(llamadas.map(...)).then((r) => live.sendToolResponse(r));

Sin `.catch()`, y `atenderTool` sin `try`. Gemini bloquea el turno hasta
recibir respuesta de cada tool que pidió: si la promesa se rechaza,
`sendToolResponse` nunca sale y **el tutor queda mudo para siempre**. Eso es lo
que vio el usuario como "le di la respuesta y se quedó callado"
(`ses_ea39b9de2677`). Ahora cada llamada tiene su propio catch y el envío
siempre ocurre, aunque sea con `{error: ...}` — que el modelo puede leer y
recuperarse hablando.

**3. El planificador mandaba a la raíz del grafo — la causa de todo.**
`esta_dominada(None)` trataba igual "lo medimos y no le sale" que "nunca lo
miramos". Juan, de 2°, sin registro de nada, recibía "contar hasta 100".

Se agregó `prerrequisito_satisfecho()` en `pedagogy.py`: **presunción de
grado**. Un prerrequisito de grado estrictamente menor al del niño, sobre el
que no hay evidencia, se presume satisfecho. No se escribe nada en `dominio`
— presumir no es medir, y un dato inventado terminaría en el reporte al papá.
En cuanto el niño falla, la evidencia real reemplaza la presunción.

Juan pasó de "Contar hasta 100" (grado 1) a "Centenas" (grado 2); la frontera
de 1 a 5 habilidades. Tests nuevos en `test_pedagogy.py`; los tres tests que
codificaban el arranque en la raíz se reencuadraron con un niño de **grado 1**,
donde no hay nada que presumir y siguen probando la mecánica del grafo.

**4. Fixtures acoplados al planificador.** `test_session` y `test_api` creaban
ejercicios de UNA habilidad, así que se rompían cada vez que el planificador
cambiaba de opinión. Ahora crean para todas, como la base real. 229 tests.

### ⚠ Trampa operativa que costó media hora

`uvicorn --reload` lanza el servidor real con `multiprocessing spawn`, y **ese
hijo no tiene "uvicorn" en su línea de comando**. Al matar al padre, el hijo
sobrevive con el socket del puerto 8000 y sigue respondiendo con código viejo.
Se ve como "cambié el código y el servidor no se entera".

Para matarlo de verdad, filtrar por nombre no alcanza:

    Get-CimInstance Win32_Process -Filter "Name='python.exe'"

y matar TODOS los que aparezcan, incluidos los de `multiprocessing.spawn`.
Verificar después que `Get-NetTCPConnection -LocalPort 8000` no devuelva nada.

---

## ⚠ Créditos de Google

Recargados el 17/08 y funcionando. Pero **a mitad de una tanda de pruebas una
conexión devolvió "credits depleted" y las siguientes volvieron a andar**: o el
saldo queda muy justo, o ese mensaje en realidad es un límite de tasa
disfrazado. Si vuelve a aparecer sin razón, mirar por ahí antes que el código.

---

## 0. El silencio del tool call  ← ATACADO 17/08, FALTA MEDIRLO

**Ya se hicieron tres cosas; falta comprobar que alcanzaron.**

1. `socratic_playbook.es.md` + `tutor_persona.es.md`: regla explícita de
   **hablar antes de llamar** la herramienta ("déjame reviso...", "espérame un
   momentico"). Es lo que hace un profesor de verdad y no cuesta nada.
2. `useTutor.ts`: `get_next_problem` ahora **se sirve del banco ya precargado
   en el navegador** — los ejercicios venían en `SesionAbierta.ejercicios` y
   aun así se pedían por red. El aviso al backend sale sin esperarlo.
3. `useTutor.ts`: `atenderTool` mide y loguea `[tool] nombre: Nms` en la
   consola del navegador.

**`check_answer` sigue costando un viaje completo** y no se puede precargar
(depende de lo que dijo el niño). Ahí la única defensa es la frase previa.

Al retomar: abrir la consola del navegador (F12), hacer una sesión, y leer los
`[tool]`. Si `check_answer` pasa de ~800 ms, hay que pensar algo más.

---

**Reporte original del usuario, sesión del 17/08:**

> "Estaba bien fluido, pero en algunas preguntas específicas el tutor se
> demora, como si se fuera a buscar la respuesta en algún lado, y es bastante
> tiempo el que hay que esperar. **El estudiante cree que el profesor lo
> abandonó.**"

Esa descripción — se demora *en preguntas específicas*, no siempre — es
justo la firma de un tool call. El camino es:

```
Gemini decide llamar check_answer
  → WebSocket hasta el navegador
  → fetch a nuestro backend (localhost hoy; en producción, la red real)
  → SQLite
  → de vuelta al navegador
  → de vuelta a Gemini por WebSocket
  → recién ahí Gemini genera audio
```

Durante TODO ese viaje el tutor está **mudo**. Ningún sonido, ninguna señal.
Un adulto asume que está pensando; un chico de 7 años asume que se fue.

Es el peor momento posible para el silencio, además: `check_answer` se llama
justo después de que el niño arriesgó una respuesta. Es el instante de máxima
vulnerabilidad de la sesión.

### Qué mirar, en orden

1. **Medir antes de tocar.** Instrumentar `atenderTool` en
   `web/src/voz/useTutor.ts:59` con `performance.now()` de punta a punta, y
   loguear aparte el tiempo del `fetch`. Sin el número no se sabe si el costo
   está en nuestro backend, en el round-trip del WebSocket, o en que Gemini
   tarda en re-arrancar el audio después de recibir la respuesta.

2. **Tapar el silencio, que es el problema real que siente el niño.**
   Aunque se optimice, el viaje nunca va a ser gratis. Las opciones:
   - Un renglón en el prompt que obligue a decir algo ANTES de llamar el tool
     ("A ver, dejame pensar...", "Mmm, veamos"). Es lo que hace un profe de
     verdad. Cero infraestructura, y es lo primero que probaría.
   - Un sonido de fondo suave mientras `atenderTool` está en vuelo.
   - Precargar el siguiente ejercicio para que `get_next_problem` sea
     instantáneo (ver `EJERCICIOS_A_PRECARGAR` en `config.py:88` — ya existe
     `BancoDeSesion`; verificar por qué no está evitando la espera).

3. **`check_answer` no se puede precargar** — depende de lo que dijo el niño.
   Ahí la única salida es el punto 2, o mover la validación al navegador, lo
   que rompería el principio de una sola implementación de la aritmética.
   No hacerlo sin discutirlo.

### Ojo: esto corrige la sospecha del punto 1

Si el tutor se demora "como si buscara la respuesta en algún lado", entonces
**sí está llamando los tools** — al menos a veces. Eso debilita la hipótesis
de que el motor está del todo desconectado. La verificación del punto 1 sigue
valiendo, pero el resultado esperado cambió: probablemente sea
**intermitente** (llama a veces, improvisa otras), que es un problema
distinto y más difícil que "no llama nunca".

## 1. ¿El tutor está llamando los tools?  ← EMPEZAR ACÁ

**Sospecha fuerte, sin verificar.** En las dos sesiones el tutor propuso
"15 figuritas + 7" y "7 + 12" (sumas con reagrupación) a un chico de **segundo
grado**. No parecen del banco: parece que los **inventa** en vez de llamar
`get_next_problem`.

Y en `ses_4e881e257562.txt`, Juan dijo "7 + 12, eso da 24" y el tutor contestó
"Mmm, por ahí no es" — correcto, pero **lo calculó el modelo**. `CLAUDE.md`
lo prohíbe: _"La aritmética jamás la valida un modelo"_. Esta vez acertó.

Si la sospecha se confirma, el grafo de habilidades, el planificador, el
registro de dominio y el "sin techo" están construidos y **desconectados**:
la app parece funcionar pero por dentro es un chatbot simpático. Y el panel
del papá no tendría datos que mostrar.

Cómo verificar:
```
sqlite3 data/tutor.db "SELECT id, habilidades_trabajadas FROM sesiones ORDER BY inicio DESC LIMIT 5;"
```
Si `habilidades_trabajadas` viene vacío, está confirmado. El arreglo es un
renglón en `knowledge/prompts/socratic_playbook.es.md` que obligue a llamar
`get_next_problem` antes de proponer cualquier ejercicio, y `check_answer`
antes de decir si acertó.

## 2. Latencia de la primera frase

Se siente lenta al arrancar. `empezar()` en `useTutor.ts` es secuencial:
abrir sesión (backend + SQLite + planificador) → emitir token (round-trip a
Google) → conectar WebSocket → warmup del modelo. Paralelizar lo que no
depende del token.

## 3. Frases cortadas a mitad de palabra

"¡Contame", "¿Qué me querías", "y que te gusta". VAD disparando de más.
Ojo: Juan estaba interrumpiendo a propósito, así que puede ser correcto.
Medir antes de tocar `deteccion_para_edad()` en `src/tutor/voice.py:69`.

Relacionado: el silencio de fin de turno son 1500 ms fijos para 2º grado.
Es la otra mitad de la sensación de lentitud. La idea a evaluar es separar
"silencio para responder" (respuesta corta y numérica → ~800 ms) de
"silencio para cortar" (está razonando → 1500-2000 ms).

## 4. Fuga de contexto en el prompt

Juan preguntó "¿acaso qué sabes de mí?" y el tutor dijo **"Me contaron** que
te gusta el fútbol". A un chico de 7 años le suena a vigilancia. Debería ser
"vos me lo contaste". Un renglón en `tutor_persona.es.md`.

## 5. Idioma de transcripción sin fijar

Ruido de fondo salió transcrito como coreano (`규리 거`) en la sesión de las
19:23. `inputAudioTranscription` va vacío en `src/tutor/voice.py:217`.
**No adivinar el campo** (`speechConfig.languageCode` vs. algo dentro de
`inputAudioTranscription`): verificarlo emitiendo un token real, que la API
valida la config del lado del servidor.

## Nota operativa

El cupo diario son 3 sesiones. Probando se agota rápido. Para liberarlo:
```
python -c "import sqlite3,datetime; from src.tutor import config as c; \
  con=sqlite3.connect(c.DB); con.execute('DELETE FROM sesiones WHERE date(inicio)=?', \
  (datetime.date.today().isoformat(),)); con.commit()"
```

---

## Acento bogotano — hecho el 17/08, falta oírlo

`src/tutor/voice.py`: voz `Charon` → **`Puck`** (juvenil), y
`speechConfig.languageCode = "es-CO"`. Los prompts del tutor
(`tutor_persona`, `socratic_playbook`, `safety_policy`) se reescribieron de
rioplatense a bogotano: "tú" en vez de "vos", *listo / chévere / de una / un
momentico / no te afanes*, y una lista negra explícita (voseo, españolismos,
y jerga tipo *parce* — cercano pero decente, que un papá pueda oír la
grabación tranquilo).

El acento sale de `languageCode`; **las palabras salen del prompt**, porque el
modelo imita el registro de sus propias instrucciones. Ese era el error: los
prompts estaban escritos en argentino.

Si al oír Puck no convence: cambiar `VOZ_POR_DEFECTO` en `voice.py`. Las otras
candidatas están listadas ahí mismo (Leda, Achird, Zephyr, Sulafat). Es una
constante y nada más depende de ella.

**Sin verificar contra la API** por lo de los créditos: que `es-CO` y `Puck`
sean válidos para este modelo salió de la documentación, no de una conexión
real. Hay una guarda (`VOCES_CONOCIDAS`) que falla al abrir la sesión en vez
de reventar con el niño enfrente — hizo falta porque se comprobó que
`auth_tokens.create` acepta hasta `"NoExiste123"` y devuelve token válido.
