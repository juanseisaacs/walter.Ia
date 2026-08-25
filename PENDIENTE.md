# Pendiente — retomar acá

_Última poda: 2026-08-24._

> Este archivo se **poda**, no solo se agrega. El 20/08 tenía 25 secciones y
> ocho de los pendientes marcados en rojo ya estaban hechos hacía días — leerlo
> daba la sensación de una montaña que no existía. Un pendiente resuelto que
> sigue escrito acá no es memoria: es ruido, y el ruido esconde lo que sí falta.

---

## ✅ Dónde estamos parados

El circuito completo cierra **y está probado con voz real**: el niño habla, el
tutor usa el banco, `check_answer` verifica, el Analista escribe el dominio, el
planificador de mañana arranca con la evidencia de hoy, el reporte lo cuenta y
el papá lo lee en el panel. Más la cámara, la pizarra y la hoja de dibujo.

- **676 tests** de Python · **195** del front · **evals 45/45** (los 3 casos
  agregados después no se han corrido) · lint en cero
- **~100 sesiones de voz**, todas nuestras — ningún niño ajeno todavía
- La pantalla del niño tiene prueba de punta a punta con navegador y sesión
  Live real: `python -m scripts.e2e_voz` (14/14 el 22/08)
- **78 habilidades** (1° a 5°): 54 de matemáticas —el MEN numérico completo—,
  13 de lectura y 11 de escritura, con triple anclaje · **2.052 ejercicios
  validados**, ninguna habilidad vacía
- 5 niños en la base, todos de prueba

### Cómo levantarlo

```bash
cd web && npm run build && cd ..      # solo si se tocó la interfaz
python -m uvicorn tutor.api:app --port 8000
```
→ **http://localhost:8000** · la pizarra suelta en **/pizarra**

### ⚠️ Los dos comandos que se corren SIEMPRE (24/08)

```bash
python -m scripts.listo_para_hablar   # ANTES de entregar un enlace
python -m scripts.revisar_sesion      # DESPUÉS de cada sesión
```

El primero abre una sesión Live de verdad. El 24/08 se entregaron cuatro
enlaces "verificados" y ninguno servía: `POST /api/sesiones` daba 200 en los
cuatro y Google contestaba *«prepayment credits are depleted»*. **Un 200 del
backend no prueba que el niño pueda hablar.**

El segundo junta en una pantalla lo que estaba en cinco lugares — cierre,
aprendizaje, método, fluidez y costo. Sin él, diagnosticar una sesión costaba
media hora y terminaba en una hipótesis; con él, diez segundos. Ese ciclo de
forense repetida fue lo que se comió los días 23 y 24.

---

## 🔵 Sin verificar con voz real: el arreglo del stream (25/08)

Los tres defectos de `ses_31593f90ab26` están corregidos y con tests
(`web/src/voz/colaDelMicrofono.ts`, 15 casos), pero **lo único que prueba que la
conversación se siente fluida es una conversación**. Lo que hay que mirar
después de la próxima sesión, con `python -m scripts.medir_fluidez`:

| columna | qué significa | contra qué se compara |
|---|---|---|
| `cortados` | el tutor partido a mitad de palabra | 38% en `ses_31593f90ab26`; 11% en el acumulado |
| `niño✁` | el turno del niño que empieza a mitad | 10,3% el 20/08 · 6,8% el 24/08 |
| `sin voz` | turnos que el niño NO OYÓ | tiene que ser **cero**. Si aparece, el vigilante de la voz hizo su trabajo y hay que leer por qué |

Y ya no hace falta ir a la consola del navegador: **`revisar_sesion` muestra el
diario de la voz** — latencias, tools con su duración, mudez, barge-in y voz
muda, con el minuto en que pasó cada cosa. Lo que hay que mirar ahí:

- **`barge_in_falso` repetido** → `UMBRAL_BARGE_IN` está bajo y el eco lo dispara.
- **un `tool` de más de 2 s** → ese es el silencio que el niño lee como «se fue
  a buscar la respuesta». Es la hipótesis abierta de `ses_fd1b97ff577e`, todavía
  sin confirmar con datos.
- **`voz_muda`** → tiene que ser cero.

---

## 💵 Costos — medido, no estimado (24/08)

Dos recargas de US$10 agotadas: **US$20 en 520 minutos → US$0,038 por minuto.**
A 20 minutos diarios son **~US$23 al mes por niño**, que es un número de negocio
y hay que mirarlo antes de poner precio.

**US$6,89 de los US$20 se fueron en sesiones que nadie usaba** — una de 117,7
minutos. Ya no puede volver a pasar: hay dos vigilantes distintos, el reaper
del backend (pestaña muerta, `ABANDONO_SEG`) y el corte por inactividad del
navegador (niño ausente con la pestaña viva, `MS_SIN_EL_NINO`). Tope por
incidente: US$0,15.

Lo que falta acá: **el gasto no se registra en dólares en ningún lado.** Hoy hay
que reconstruirlo a mano desde `tokens_consumidos` y los minutos, y 35 de 94
sesiones tenían `tokens_consumidos = 0` porque el navegador no alcanzaba a
reportar. Eso último debería estar resuelto (beacon + reaper + `motivo_cierre`),
pero hay que confirmarlo con datos nuevos antes de creerlo.

---

## 🔴 Lo único que mueve la aguja

**Cinco niños que no seamos nosotros, una semana.**

> **Acordado el 24/08:** antes de eso, **cinco sesiones seguidas sin tocar el
> código entre una y otra**, corriendo `revisar_sesion` después de cada una.
> La sesión `ses_9c5a9c436312` cerró limpia en las cinco dimensiones —banco
> usado, dominio escrito, auditoría 4/4, cero mudeces— y aun así se sintió como
> que no funcionaba, porque no había cómo verlo. Cinco pantallas juntas dicen
> si hay un patrón o si estamos reaccionando a la última impresión.

El cuello de botella dejó de ser técnico hace días. Falta evidencia de que
alguien lo usa y vuelve, y eso no se simula ni se construye:

1. **¿Vuelve un niño sin que se lo pidan?** Es el dato que ningún competidor
   tiene y que ninguna feature reemplaza.
2. **¿Aprende?** Todo el sistema mide dominio y nadie verificó que ese número
   corresponda a aprendizaje real. Un pre/post simple lo responde.
3. **¿Aguanta 20 minutos?** Un niño de 7 se distrae, contesta con monosílabos y
   se levanta. El único usuario ha sido RBH, que quiere que funcione.

⚠️ Construir features antes de esto es sumar superficie sobre una hipótesis sin
validar.

---

## 🟡 Lo que decide RBH — nadie más puede

**1. El método de lectura.** Silábico, fonético, global o mixto. Esa elección
define el grafo entero de lectura: el orden de los nodos, qué es prerrequisito
de qué, cómo se ve un ejercicio. **Destraba los dos tercios del producto que hoy
no existen** — el producto promete lectura, escritura y aritmética, y solo hay
aritmética. Ojo: los DBA de Lenguaje del MEN **no descomponen la
decodificación**, así que esos nodos van a ser criterio nuestro, declarado como
propio (`FUENTES.md` §2.3).

> **Evidencia nueva (21/08, `ses_cdb0b7fae50f`).** Al niño se le ofreció
> fracciones y contestó *"eh, no, quiero practicar escribir la w bien"*. Trabajó
> nueve turnos en eso. La sesión cerró con `habilidades_trabajadas: []` y no
> movió una sola fila de `dominio`: **16.573 tokens que el papá no va a ver en
> ningún reporte.** El Analista hizo bien en no inventar una habilidad de
> matemáticas — pero cuando el niño ELIGE escritura y el sistema no tiene dónde
> anotarlo, el que pierde es el papá.

**2. Diálogos modelo.** Cinco o seis conversaciones de ejemplo: el niño dice
esto, el tutor debería responder así, y esto otro sería inaceptable. Cada una se
vuelve un test. Es lo que convierte "me parece que va bien" en algo medible, y
lo que haría que "antes cantaba mejor" deje de ser suerte. Hay material de sobra
en las sesiones reales.

**3. Cuánto pregunta el onboarding**, y si el del papá es por texto o por voz.
El motor no sabe qué le llega: cambiarlo es la pantalla, no la arquitectura. Va
**después** del método de lectura — la entrevista pregunta distinto según cómo
vayamos a enseñar a leer.

### Aplazados con costo escrito (`ARCHITECTURE.md` §19)

- **Pruebas Saber 3° y 5°.** El argumento más fuerte frente a un papá
  colombiano. El límite lo pone la propia fuente: sin simulacros, sin ansiedad.
- **Abrir las cinco áreas.** Cuesta el patrón de `id`, el enum `Materia`, un
  YAML por área, el banco y las 4 suites de evals. Y los DBA de las áreas nuevas
  **no están verificados**: la única fuente que los tenía estaba corrida un
  grado (`FUENTES.md` §2.6). Abrir un área empieza por bajar su PDF del MEN.

---

## 🟢 Lo que puedo hacer yo, sin esperar a nadie

- **Los nodos base de lectura**, en cuanto esté decidido el método (§7.2).
- **Completar `proporcionalidad.directa`**: quedó con 10 ejercicios en vez de 26
  porque el generador le sigue poniendo unidades a la respuesta ahí. Un minuto.
- **Corregir los trazos feos.** Los 60 glifos de `trazos.ts` se escribieron sin
  ver el render. Con que RBH mire `/pizarra` → "Ver todos los trazos" y diga
  cuáles están torcidos, se arreglan: es una línea por carácter.
- **Limpiar la base.** Hay dos Felipe (el onboarding corrió dos veces) y datos
  de prueba mezclados.

### La letra pegada (cursiva), que el niño pidió y no existe

`ses_eadfa6137a37` (23/08): «me dijeron que en letra pegada, ¿cómo así?». La
pizarra escribe letra suelta —los 60 glifos de `trazos.ts`— y no hay cursiva.

En Colombia la cursiva se enseña en 1° y 2°, así que no es un capricho: es la
tarea que le mandaron. Cuesta un juego de glifos nuevo con sus enlaces entre
letras, que es bastante más que 60 trazos sueltos.

Mientras no exista, el tutor tiene que **decir que no la tiene y seguir** — sin
prometer que "ya está avisando", que es lo que hizo (ver `BITACORA.md`).

### La mudez tiene red, pero sigue sin causa

`ses_87aba17c8c6c` (22/08): el tutor se calló a mitad de sesión y no volvió. Se
puso la red —tope de 8 s en las tools, vigilante de 10 s que empuja y después
cierra avisando, y marca en la transcripción— pero **no se supo por qué pasó**:
la única evidencia estaba en la consola del navegador y se fue con la pestaña.

Lo que hace falta la próxima vez que ocurra, en este orden:

1. **No cerrar la pestaña.** La consola tiene `[tool]`, `[latencia]`, `[live]` y
   ahora `[mudez]` — con eso se distingue una tool colgada de un turno que el
   VAD no cerró.
2. **Buscar `MARCA_DE_MUDEZ` en `data/transcripts/`.** Si aparece, el vigilante
   funcionó y hay al menos un episodio contado.
3. Recién ahí decidir si hace falta guardar los logs del navegador en algún
   lado. Hoy sería infraestructura para un fallo que ocurrió una vez.

---

## ⚪ Abierto, sin urgencia

### De la Constitución (adoptada el 18/08, ver `ARCHITECTURE.md` §18)

- **La excepción de fe declarada** (§7). Hoy **toda** pregunta religiosa se
  devuelve a la familia. Implementarla pide tres cosas en orden: campo declarado
  por el padre —nunca inferido del niño—, pregunta en el onboarding, y revisión
  legal. `test_la_seguridad_no_implementa_la_excepcion_de_fe_declarada` falla el
  día que alguien lo haga: está puesto para que la decisión se tome mirando.
- **Confianza por dominio** (§3.3.6). Un niño puede sentirse capaz en fútbol y
  derrotado en matemáticas. `RegistroDominio.nivel` es competencia medida, no
  confianza sentida: son dos números distintos. ⚠️ Cuando se implemente nace en
  `None` y llega en `None` hasta el prompt — la lección de la fase 6.
- **Aviso suave al papá por tema de familia** (§7.4, §8.6): religión,
  sexualidad, política, noticias difíciles. No es un riesgo, es un aviso — un
  evento distinto de `escalate_safety`.
- **Que el Vigilante no escale travesuras.** El tutor ya distingue riesgo de
  travesura; falta confirmar que el Vigilante y el reporte tampoco conviertan
  una confesión menor en un evento. Vale un caso en `evals/safety/`.
- **Documento legal dedicado** — consentimientos, niveles de alerta,
  bifurcación intrafamiliar, retención, COPPA / Ley 1581. Es el pendiente #1 de
  la propia Constitución.
- **Diálogos modelo Nivel 1** (abuso, autolesión) — la Constitución es explícita
  en que se escriben **con el psicólogo infantil, nunca antes**.

### La cámara abre una puerta a la trampa

Con cámara el niño puede mostrar el ejercicio y esperar que el tutor lo resuelva.
Es la misma línea de siempre —ayudar ≠ hacer— por un camino nuevo: decir el
problema ya es trabajo, enfocar la cámara no. Tres formas sin cubrir: la página
entera de la tarea, la hoja de respuestas, y la foto en vez del intento.

Faltan las reglas propias de la cámara: ante varios ejercicios, elegir UNO y
preguntar por dónde empezaría; no leer en voz alta un enunciado que el niño
puede leer; y que **una foto no cuente como intento** en la escalera.

### El perfil acumula donde debería consolidar

`datos_suyos` está impecable a las 19 sesiones (tres líneas, limpias): tiene la
regla más clara del prompt del Analista. Los otros campos no:

- `intereses`: "desafíos matemáticos" · "Retos matemáticos" · "matemáticas"
- `frustraciones`: **"matemáticas"** — al mismo tiempo que figura como interés
- `motivadores`: seis, tres de ellos solapados

Es lo que el propio prompt advierte ("si a los seis meses esta ficha es una
lista de cien cosas, no sirve para nada"), y ya está pasando. Va al prompt de
sesión, así que además pesa contra el techo. Arreglarlo toca la salida del
Analista — la operación que la fase 7 dejó marcada como la más cara — así que
va con evals detrás, no de paso.

### El tutor ya saluda primero — falta ver si alcanza

Resuelto el 22/08. El tutor abre la conversación apenas el niño entra:
`session.abrir()` manda una instrucción de apertura que el navegador dispara al
conectar, y el texto vive en `knowledge/prompts/apertura*.md` — distinto el
primer día que los siguientes, como se decidió.

Verificado contra Gemini real (`scripts.e2e_voz`, 14/14): el primer día dice
*«¡Hola! Yo soy Walter. Vamos a estudiar juntos y te voy a acompañar un buen
rato, no solo hoy. Oye, ¿a ti te gustan los dinosaurios?»* — se presenta y hace
una sola pregunta, que es el guion de `primer_encuentro.es.md`.

**Lo que falta es saber si sirve.** Que el tutor hable primero elimina la causa
que dejaba 19 de 71 sesiones vacías, pero eso es una hipótesis hasta que haya
sesiones nuevas con las que compararlo. La medición es de una línea: contar
otra vez quién abre la conversación, dentro de un par de semanas.

Y queda una pregunta abierta que solo se contesta viendo a un niño: **si no
contesta el saludo, ¿el tutor insiste?** Hoy se queda callado esperando, que es
volver al mismo silencio un turno más tarde.

### Una de cada tres sesiones se abre y se cierra sin un solo turno

Medido el 22/08 sobre los datos reales: **19 de 62 sesiones tienen la
transcripción en 0 bytes**. Se abrió la sesión, se emitió el token efímero, se
cerró y nadie dijo una palabra. Salió a la luz investigando por qué 21 sesiones
no tenían auditoría — no la tienen porque no hay nada que auditar, y eso es
correcto; el problema es el 31 %.

Cada una de esas sesiones **gasta un token de Gemini y cuenta contra
`MAX_SESIONES_DIA = 3`**, así que un niño puede quedarse sin su tercera sesión
del día por dos recargas de página. Y una de ellas duró **117,7 minutos con
cero turnos**: una pestaña abierta y olvidada, que es el mismo agujero que el
corte por duración de abajo.

Antes de arreglarlo hay que saber cuál de las tres es: recargas de la página
durante el desarrollo, el navegador abriendo sesión antes de que el niño toque
el botón, o sesiones que mueren al conectar. Lo dice el log del servidor
cruzado con `inicio`/`fin`, no hace falta código nuevo para averiguarlo.

### Hay dos Felipe, y uno sobra

`n_hPPbkPYr` y `n_drlyRRIU` son el mismo niño: el onboarding corrió dos veces.
Las sesiones están todas en el primero (20 sesiones contra 0), así que el
segundo es una ficha huérfana.

Borrarlo es una línea, pero **`ON DELETE CASCADE` se lleva su dominio y sus
sesiones**, así que antes hay que mirar que de verdad no tenga nada — no
después. Es el tipo de limpieza que conviene hacer con la base a la vista, no
en un script que se corre a ciegas.

### El motor cerró el círculo — falta que un niño lo recorra

El papá ya lo ve: el reporte semanal y el panel cuentan qué método se usa y, si
cambió, la razón exacta redactada en código. La verificación estricta del
reporte no lo tumba (tiene test propio) y sin técnicas medidas no se afirma nada.

Lo que falta es lo de siempre: **nadie ha recorrido el ciclo entero todavía**.
Hacen falta al menos 4 sesiones seguidas del mismo niño en la misma habilidad
para que el motor llegue a abandonar una técnica y probar la rival. Con 62
sesiones repartidas entre 5 niños y temas distintos, hoy no hay ninguna cadena
así. Hasta que la haya, el «se probó, se midió, se cambió» es un mecanismo
verificado en simulación, no en un niño.

### Las 6 técnicas no tienen efecto verificado

Todas declaran fuente y respaldo, y todas tienen `efecto_verificado: false` —
nadie contrastó el tamaño del efecto contra el metaanálisis original. Está
puesto así a propósito para que se vea, y hay un test que falla el día que
alguien lo ponga en `true` sin decir contra qué lo contrastó.

Cerrarlo es media tarde de lectura por técnica. Antes de eso conviene saber
cuáles se usan de verdad: con 6 técnicas y 3 sesiones cada una, agotar la
biblioteca son 18 sesiones, y no tiene sentido verificar la evidencia de una
que el motor nunca llegue a probar.

### Lo que Juan pidió y todavía no está

De la sesión del 22/08 quedaron dos cosas sin hacer:

- **Dibujar «33 gallinas y 24 patos».** Los emojis ya salen dentro de `grupos`,
  pero `grupos` es *N grupos de M cosas iguales*: no hay forma de mostrar dos
  cantidades de cosas DISTINTAS. Es justo lo que el niño pedía cuando dijo «me
  gustaría poder ver las gallinas y los patos», y hoy el tutor tiene que
  contestarle que no puede. Sería un tipo nuevo en el enum, con su handler y su
  test de contrato: medio día, riesgo bajo.
- **La latencia que él nota.** *«Es que te demoras un poquito a veces en
  responder.»* Van cuatro medidas del clic a «Te escucho» —2.078, 2.109, 3.250,
  1.641 ms— sin controlar la red, así que no dan para concluir nada. Lo que
  falta medir es otra cosa: el silencio DENTRO de la conversación, que es lo que
  el niño siente. La consola ya lo imprime desde el 21/08; falta leerlo.

### Lectura y escritura ya tienen banco — falta que un niño las trabaje

Las 24 habilidades de `lenguaje.yaml` tienen sus ~26 ejercicios validados y el
planificador ya rota entre las tres materias. Lo que no se ha visto es una
sesión de voz de verdad sobre un nodo de lenguaje.

Tres cosas que hay que MIRAR la primera vez, y que ningún test cubre:

- **Si `check_answer` entiende cómo el niño contesta de verdad.** Se agregó
  `NOMBRE_DE_LETRA` porque un niño dice «eme», no «m» — pero eso salió de
  pensarlo, no de oírlo. Las respuestas de lenguaje son mucho más abiertas que
  un número, y el modo de fallar es el caro: decirle INCORRECTO al que acertó.
- **Si los nodos abiertos son trabajables.** Los siete sin verificación
  (comprensión, párrafo, texto narrativo) dependen de que el tutor los sostenga
  socráticamente sin clave de respuestas. `REQUIERE_JUICIO` está bien resuelto
  en código; lo que falta es ver qué hace el tutor con eso en una sesión.
- **Si `esc.grafia.trazo_de_letras` tiene sentido por voz.** El niño tendría que
  trazar y mostrar por cámara. La visión funciona desde el 21/08, pero este
  nodo nunca se probó y es el más dudoso de los 24.

### Al motor de técnicas le faltan lectura y escritura

Hay 6 técnicas = 3 pares rivales: **1 par de matemáticas** (concreto ↔
estructura) y **2 genéricos**. **Cero de lectura, cero de escritura** — y ya hay
24 habilidades de lenguaje. En una sesión de rimas o de párrafo siempre cae en
`el_explica`, que es la genérica.

Buscando eso apareció que `numero_puro` decía `aplica_a: []` («con todas») y su
texto es puro aritmético —*«nada de historias, el ejercicio es la cuenta, 47 más
28»*—: el motor podía activarla en una sesión de lectura. Ya está acotada a
matemáticas.

Lo que falta escribir son 3-4 pares nuevos con su bloque de evidencia. En
lectura inicial existe el cuerpo de evidencia más fuerte de toda la primaria
—fónica sistemática contra lenguaje integral—, que es exactamente la forma de
par rival que este motor necesita. **RBH quedó de mandar la investigación**
(22/08); hasta entonces no se inventa nada.

### Dos preguntas de plata sin responder

**¿Una sesión que se abre y se cierra sin hablar, paga?** Hay 25 de 66 así. Si
el prompt se manda al conectar, cada una costó ~16.000 tokens por nada — serían
~$4 de los $10 de la primera recarga. Se mide en dos minutos: abrir una sesión,
cerrarla sin decir nada, mirar la factura.

**¿El costo por minuto se mantiene plano en sesiones largas?** El modelo de
costos —16.234 fijos + 779/min— se ajustó con sesiones de 0,4 a 17,4 minutos, y
**solo hay UNA de más de 10**. Con eso se proyectó que 30 min diarios salen
~$11,88/niño/mes, pero el contexto se acumula, así que el costo por minuto
podría crecer. Una sola sesión de verdad de 25-30 minutos lo resuelve.

### Lo demás, chico

- **El último hash de la cadena no se publica en ningún lado.** La cadena de
  veredictos impide retocar el histórico, pero vive en el mismo disco: quien la
  reescriba ENTERA desde cero puede fabricar una consistente. El cierre es
  anclarlo afuera — el hash del extremo en el correo semanal al papá, por
  ejemplo. Cuesta poco y convierte la garantía en verificable por un tercero.
- **La verificación del reporte solo mira números.** Una afirmación cualitativa
  sin respaldo pasa. Verificarlo pediría un segundo modelo, y la regla del
  proyecto es que la verificación es código.
- **La latencia percibida no estaba medida.** Desde el 21/08 la consola imprime
  `[latencia] N ms de silencio antes de contestar` — de la última sílaba del
  niño al primer audio del tutor. Adentro va el VAD (900 ms para un niño de 8,
  `SILENCIO_FIN_TURNO_MS`), la red y el modelo. Si el número se parece al VAD,
  el silencio lo ponemos nosotros y se baja ahí. Falta una sesión que lo mida.

### Medido y descartado

❌ **Prompt caching en los agentes offline.** El mínimo cacheable son 1024
tokens y los cuatro prompts están por debajo (medido el 18/08). Solo
`method_auditor` calificaría, y el ahorro son céntimos al mes. Se vuelve a mirar
si algún prompt offline crece mucho.

---

## Cerrado desde el 18/08 — por qué este archivo encogió

| Era un 🔴 | Qué pasó |
|---|---|
| El modo Pedido no se puede activar | Hay botón "Traigo una tarea" en la pantalla del niño |
| `request_camera` es un stub | Funciona: leyó las letras de una gorra y contó cinco dedos |
| No existe la primera sesión del niño | `primer_encuentro.es.md`, condicionado a `madurez_vinculo == 0` |
| El prompt está a 208 caracteres del techo | Adelgazado 7,3 KB moviendo el porqué a `knowledge/product/`; techos bajados a 36.000 y 35.000 |
| Falta una sesión de voz real | 35 sesiones reales |
| Referencias DBA provisionales | Triple anclaje, auditado nodo por nodo (`FUENTES.md` §2.5) |
| Enlaces mágicos en memoria | En la base desde el 18/08 |
| Frases cortadas, VAD sin calibrar | Silencio 1500 → 900 ms, oído más sensible, y barge-in local en el navegador |
| El dominio llevaba seis sesiones congelado | El tutor usa el banco; `habilidades_trabajadas` se llena |
| Un acierto se leyó como error | `Veredicto.NO_SE_ENTENDIO`; el playbook repregunta en vez de corregir |
| "Se siente lento" | Era `vite dev`. La API monta el build; el onboarding pasó de 7,2 s a 3,6 s por turno |
| La sesión larga se descartaba entera | La extracción pasó a tool use: el JSON dejó de llegar cortado |
| El tutor no sabía qué le contó el niño de sí mismo | `PerfilPersonal.datos_suyos` |
| El tutor inventaba lo que veía (foto y dibujo) | La imagen va dentro del turno, no por el canal de video. `scripts/verificar_vision.py` lo mide con un control que no se puede adivinar |
| El tablero afirmaba de más ("¿ya ves las dos?") | El tool devuelve QUÉ quedó en pantalla y con qué colores; dos fracciones se comparan con `comparar_con` en una sola llamada |
| El tablero no podía mostrar una lista de palabras | Escena `lista`: hasta cuatro, una por renglón y cada una de un color |
| El dominio se perdía en silencio | `clasificar_senales` cuenta lo que entra y lo que se cae, con el MISMO predicado que decide (`_destino`). Lo perdido sale como WARNING y `procesar_pendientes` lo imprime |
| Un id inventado por el Analista se descartaba | Si la sesión trabajó un solo nodo se corrige, igual que el id ausente. Con dos o más no se toca: ahí sí hay algo que decidir |
| La alerta de seguridad iba a un correo inventado | `_email_del_papa` ignoraba `nino.email_papa` con un docstring que decía que el campo no existía. Existía desde el onboarding |
| `aviso_de_reporte()` no lo disparaba nadie | `_avisar()` ya estaba escrita entera en el script y `main()` no la llamaba. Se conectó (`--sin-avisar` la suprime) |
| `MAX_MINUTOS_SESION` no lo consultaba nadie | `excedio_duracion()` tenía test propio y cero llamadores. Ahora corta la recarga y el techo viaja al navegador |
| 7 errores de lint | Eran 20. En cero. Uno escondía un `F811`: dos tests con el mismo nombre, y el primero no corría desde que se escribió |
