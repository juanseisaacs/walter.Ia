# Bitácora

Lo que se rompió, por qué, y qué quedó aprendido. Cada entrada nació de un bug
real que costó tiempo: no son buenas prácticas leídas en algún lado.

`CLAUDE.md` dice **cómo trabajar** en este repo. Este archivo dice **por qué las
reglas son las que son**. `ARCHITECTURE.md` dice **qué se decidió** y con qué
razón; `PENDIENTE.md`, **dónde retomar**.

---

## El patrón que se repite

Cinco de las diez entradas de abajo son la misma falla con distinta cara:
**algo dejó de pasar y no había dónde enterarse.** Un `continue` sin rastro, una
función sin llamador, un test pisado por otro con el mismo nombre, un campo que
Pydantic descartaba en silencio, una purga de datos de menores que nadie
invocaba. Ninguno lanzó una excepción. Ninguno puso la
suite en rojo.

Y hay un segundo patrón, de método: **las cuatro se detectaron mirando los datos,
no corriendo los tests.** La fase 2 la destapó la demo; la fase 6, leer el
reporte de verdad; la del 21/08, abrir la base de datos a mano; la de visión,
mostrarle al modelo algo que no podía adivinar. La suite estaba en verde en las
cuatro.

> Cuando algo "no funciona" y los tests pasan, el próximo paso no es escribir
> otro test: es ir a mirar el dato.

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

## Lección aprendida (fase 6)

Dos datos se estaban **inventando solos**, en direcciones opuestas, y ninguno
lo detectaron los tests:

- `cumplimiento_metodo` devolvía `1.0` cuando no había ni una sesión auditada:
  el reporte iba a decirle al papá que el método se sostuvo en el 100% de las
  sesiones, sin haber mirado ninguna.
- `grado_de_trabajo` devolvía 1 para un niño de 2° del que no había evidencia,
  porque contaba nodos de 1° que nunca se midieron. El reporte le decía al papá
  que su hijo trabaja por debajo de su grado.

Los dos son el mismo error: **tratar la ausencia de evidencia como evidencia.**
Lo detectó correr el reporte de verdad y leerlo, no la suite.

→ Cuando un número va a llegarle al papá, `None` es una respuesta válida y hay
que dejar que llegue hasta la superficie. "No lo medimos" se dice; no se
completa con un default que parece un dato.

Y una tercera, de la misma corrida: **la verificación estricta también hace
daño si no distingue lo que se afirma de lo que se propone.** `verificar_reporte`
tumbó un reporte correcto porque la sugerencia para casa decía "este dinosaurio
pesaba 350 kilos". Un verificador que rechaza lo válido termina dejando al papá
sin nada, que es el resultado que quería evitar.

---

## Lección aprendida (fase 7)

**El schema pesa más que el prompt.** Toda esta tanda salió de agregar un
boolean a `AuditoriaCumplimiento`: `curriculum_fidelity` cayó de 4/4 a 0/4 sin
que nada del currículum se tocara. El modelo devolvía la auditoría impecable y
`observaciones: []`.

Cuatro cosas que quedaron, todas medidas:

1. **Un schema tiene presupuesto de atención, y se reparte.** Medido:
   sin campos extra 4/4 · con un campo trivial 3/4 · con un campo que exige
   juicio 0/4. Cuando dos trabajos distintos comparten una salida estructurada,
   **el que pierde es el que no estás mirando**. La salida fue partir el Analista
   en dos llamadas (`ARCHITECTURE.md` §18).
2. **El síntoma miente.** "Observaciones vacías" se lee como "el prompt está
   mal", y se pierde una tarde corrigiendo el prompt. Ante una regresión en evals
   después de tocar un modelo Pydantic, la primera prueba es **volver el modelo a
   HEAD dejando el prompt nuevo**: separa las dos causas en una corrida.
3. **Un baseline con una variable a medias no es un baseline.** La primera
   medición se hizo con el `models.py` nuevo y el prompt viejo — la peor de las
   tres combinaciones — y dio 0/4, lo que parecía probar que la regresión era
   preexistente. No lo era.
4. **Una descripción de campo enfática puede colgar al modelo.** Un
   `description` largo y en mayúsculas ("OBLIGATORIO…") hizo que Haiku entrara en
   un loop generando `‌` hasta agotar `max_tokens`, y el JSON truncado se
   descartaba entero. La misma regla, dicha corta y en tono neutro: 4/4 estable
   en tres corridas. En salida estructurada, **el campo se describe, no se grita.**

Y una que es de método, no de modelos: cuando el mismo síntoma vuelve tres veces
con arreglos distintos, el arreglo está en el lugar equivocado. `habilidad_id`
se resolvió cuando se dejó de pedirle al modelo lo que el código ya sabía — si
la sesión trabajó una sola habilidad, no había nada que inferir.

---

## Lección aprendida (fase 8)

Entró una fuente académica nueva —el marco del MEN— y el trabajo real no fue
incorporarla: fue **decidir qué no incorporar**.

1. **Una fuente secundaria no gana por cubrir más.** Traía las cinco áreas con
   los DBA de cada grado; `FUENTES.md` solo tenía dos áreas. Y sin embargo sus
   tablas de DBA estaban **corridas un grado** (los primeros de cada grado eran
   del grado siguiente). Se vio solo porque existía el cruce contra los PDF
   primarios. → Ante dos fuentes que se contradicen, **gana la que se contrastó
   con el primario**, aunque la otra se vea más completa y mejor ordenada.
2. **El aplazamiento con costo escrito es alcance, no deuda.** Cuatro cosas
   buenas del documento se dejaron afuera (calendario escolar, memoria
   institucional estructurada, Saber, abrir las cinco áreas) con el precio
   anotado y qué las destrabaría. `ARCHITECTURE.md` §19.
3. **Antes de agregar un campo, mirar si ya hay dónde ponerlo.** La memoria del
   colegio parecía pedir campos nuevos en `PerfilPersonal` y en la salida del
   Analista. `notas` ya existía y es texto libre: se resolvió con un párrafo en
   un `.md`, sin tocar Python ni el schema de un agente — que es la operación
   que la fase 7 dejó marcada como la más cara.
4. **Un test que mide lo que no es, pasa igual.** El test del techo del prompt
   medía con el literal `"Juan, 7 años, 2° grado."` en vez del resumen real, y
   se comía ~650 caracteres sin verlos. El anti-voseo revisaba un solo niño, y
   "seguí subiendo" vivía tranquilo en la rama VA ADELANTADO. Los dos estaban en
   verde. → Cuando una función tiene ramas, **el test tiene que recorrerlas**;
   un caso de ejemplo no es cobertura. Es la fase 2 otra vez.

---

## Lección aprendida (visión, 21/08)

**Durante tres días el tutor inventó todo lo que "vio".** Le mostramos un
cuaderno con `8 + 5` y `12 − 7`, y le leyó al niño *"veo 5 + 3 y 10 − 4"*. Un
círculo con UNA línea: *"lo partiste con dos líneas, quedaron cuatro pedazos
iguales"* — la misma frase, palabra por palabra, que con dos líneas de verdad.

La causa era el canal: `sendRealtimeInput({video})` es streaming de cámara y el
frame suelto se descarta. La imagen **dentro del turno** (`sendClientContent`
con `inlineData` + el texto juntos) se ve con precisión. Eso ya se había
intentado y revertido, porque el modelo "se quedaba colgado": era cierto y era
otra cosa — si el modelo YA está hablando, el turno con la imagen queda detrás
del anterior. Se corta antes y funciona.

Lo que hay que recordar no es el canal, es cómo se nos escapó:

1. **Una verificación con un caso adivinable no es una verificación.** Lo que
   sostenía el canal viejo era "leyó las letras de una gorra y contó cinco
   dedos". Una mano tiene cinco dedos siempre. Un modelo que no ve nada acierta
   las dos. → Para probar que un modelo VE, se le muestra **lo que no puede
   adivinar**: un 7 gigante cuando el prompt dice que espera una torta.
   `scripts/verificar_vision.py` hace exactamente eso, y es lo que hay que
   correr antes de volver a tocar el camino de la imagen.
2. **El control es la prueba, no el caso feliz.** Con una sola imagen no se
   distingue ver de completar. Con dos que se contradicen, sí: la respuesta fue
   **idéntica** con una línea y con dos. Ahí se acabó la discusión.
3. **El niño lo dijo antes que nosotros, tres veces.** "Pero yo hice un círculo
   y solo lo partí en una línea, ¿tú ves dos?". Cada vez el tutor le dio la
   razón al instante y siguió — no vio mal: no vio, y después cedió. Un tutor
   que cede ante la corrección del niño **esconde** el fallo en vez de
   mostrarlo. Cuando un niño corrige al tutor sobre algo verificable, eso es un
   reporte de bug.

Y una de producto: el tutor afirmaba de la pizarra lo que no podía saber
("¿ahí ya puedes ver las dos?" con una sola en pantalla, "el pedazo naranja"
cuando los dos dibujos eran naranjas). El tool devolvía `{ mostrado: true }`.
→ **Un tool que cambia lo que el niño ve le devuelve al tutor QUÉ quedó en
pantalla**, no un "ok". Lo que no se le dice, se lo inventa.

---

## Lección aprendida (el código sin llamador, 21/08)

Se entró a arreglar una cosa —el dominio que se perdía en silencio— y aparecieron
**cuatro fallas del mismo tipo, todas con la suite en verde**. Ninguna era un
bug de lógica: en las cuatro el código estaba bien escrito, bien comentado y
bien testeado. Lo que faltaba era **alguien que lo llamara**.

- `excedio_duracion()` — test propio desde la fase 5, cero llamadores.
  `MAX_MINUTOS_SESION = 45` no cortaba nunca.
- `_avisar()` en `scripts/generar_reportes.py` — escrita entera, con su
  docstring explicando por qué importaba, y `main()` no la invocaba.
- `_email_del_papa()` — devolvía siempre el marcador de posición, con un
  docstring que afirmaba que el campo "todavía no está en el modelo". Estaba: es
  obligatorio en el onboarding desde hace fases. **La alerta de seguridad, que es
  el camino más urgente del producto, se despachaba a un correo inventado.**
- Dos tests con el **mismo nombre** en `test_pedagogy.py`. Python se queda con
  el último: el primero no corrió nunca desde que se escribió.

Cuatro cosas que quedaron:

1. **Código muerto se ve idéntico a código que funciona.** Se lee bien, tiene
   test, el test pasa. Lo que no tiene es un camino desde una petición real
   hasta él. → El test de una función **no prueba que la función se use**; para
   eso hace falta un test que entre por donde entra el usuario, o mirar los
   llamadores a mano.
2. **Un docstring es una afirmación sin verificar.** El de `_email_del_papa`
   decía algo que había dejado de ser cierto, y por eso nadie volvió a mirar. Un
   comentario que dice "PENDIENTE: X no existe todavía" **caduca**, y cuando
   caduca miente con toda la autoridad de estar escrito al lado del código.
3. **El lint no es cosmética.** De los 20 errores, uno (`F811`) escondía un test
   que no corría. Se venían aplazando por "chicos". El que valía la pena estaba
   mezclado con diecinueve que no.
4. **El descarte silencioso es el patrón de fondo.** Un `continue` sin rastro,
   una función sin llamador y un test pisado son la misma falla: algo dejó de
   pasar y no había dónde enterarse. → Cuando el código decide **no** hacer algo,
   esa rama necesita un nombre y una salida (log, contador, lo que sea). Ver
   `pipeline.DestinoSenal`: nombrar las tres ramas del descarte fue todo el
   arreglo.

Y una de método: la señal que destapó todo fue **leer los datos de la base a
mano**, no la suite. Es la misma de la fase 2 (lo detectó la demo) y la de la
fase 6 (lo detectó leer el reporte de verdad). Van tres.

---

## Lección aprendida (el contrato entre dos lenguajes, 22/08)

Salió de comparar este repo contra otro tutor de voz construido con el mismo
harness. De todo lo que ese proyecto tenía y acá faltaba, lo único que se
adoptó de inmediato fue una prueba de **contrato entre el enum del servidor y el
handler del cliente** — `tests/test_contrato_pizarra.py`.

El agujero era real y estaba abierto: `mostrar_en_pizarra` declara sus tipos en
`voice.py`, y quien los atiende vive en `desdeElTutor.ts` y `Pizarra.tsx`. Son
dos lenguajes y no había **nada** que los obligara a coincidir. Agregar un tipo
al enum y olvidar el handler no rompe nada visible: el tutor pide el dibujo,
`aCuadro` devuelve `null`, y el niño mira un tablero vacío mientras el tutor le
habla de algo que no está.

Tres cosas quedaron:

1. **El costo de tener dos lenguajes es exactamente este.** Un proyecto con
   servidor y cliente en el mismo idioma consigue esta comprobación gratis, del
   compilador. Acá hay que escribirla, y por eso hay que escribirla: la elección
   de Python fue la correcta por otras razones, pero tiene esta factura y se
   paga una vez.
2. **La prueba encontró algo al primer intento.** `Pizarra.caja()` sabe ubicar
   `primero` y `segundo` — dos posiciones que el tutor **no puede pedir**, porque
   no están en el enum de `senalar` ni de `tachar`. Código que se lee igual que
   el código vivo y nunca corre. Es la misma falla del 21/08, un mes después y
   en otro archivo. Van anotadas con su motivo en vez de borradas, y el test
   impide que la lista crezca sin que nadie lo note.
3. **Un test que lee archivos con regex tiene que gritar cuando no lee nada.**
   Si alguien reescribe el `switch` como un mapa de objetos, el regex encuentra
   cero casos, todas las comparaciones pasan y el inspector aprueba sin haber
   mirado. Por eso `_casos_entre` revienta con conjunto vacío. Es la fase 8
   otra vez —un test que mide lo que no es, pasa igual—, prevista esta vez en
   lugar de sufrida.

---

## Lección aprendida (la retención que nunca corrió, 22/08)

Se entró a averiguar por qué 21 de 62 sesiones no tenían auditoría. La respuesta
era aburrida —19 tenían la transcripción vacía y 2 eran anteriores al commit que
introdujo `guardar_auditoria`— pero el camino pasó por `storage.py`, y ahí
estaba la **quinta pieza** del patrón del 21/08:

`borrar_transcripciones_anteriores_a()` estaba bien escrita, contemplaba hasta
los archivos huérfanos por `mtime`, y tenía **seis tests propios**. Su único
llamador era `demo_persistencia.py`. `DIAS_RETENCION_TRANSCRIPCION = 30` no lo
leía nadie: `grep` devolvía el propio `config.py` y un `.pyc`.

O sea que la regla dura decía *«las transcripciones se borran a los N días»* y
**no se borraba ninguna, nunca** — sobre conversaciones de menores, que es el
único dato de este sistema con obligación legal encima.

1. **Es la peor forma de esta falla, y por eso costó nada encontrarla y mucho
   no haberla encontrado antes.** No se notaba porque la transcripción más vieja
   tenía cinco días: el sistema se comportaba igual con purga y sin purga. Una
   función de mantenimiento sin llamador es invisible hasta el día en que
   importa, y ese día ya es tarde.
2. **La cura no es llamarla: es que no pueda volver a quedarse sin llamador.**
   `test_retencion_corre_de_verdad` entra por `main()` del script, no por la
   función. Se comprobó que detecta el fallo comentando la llamada: falla con
   *«assert 'nino: hola' is None»*. Un test de la función sola habría seguido
   en verde todo este tiempo — de hecho, seis lo estaban.
3. **Una obligación legal no puede colgar de un `return` temprano.** El script
   salía antes si la cola estaba vacía, si iba en `--seco` o si faltaba la
   llave. La retención no depende de nada de eso, así que se movió fuera de los
   tres, con un solo punto de salida. El orden sí importa y quedó escrito:
   primero se analiza, después se purga; al revés la purga le borra el insumo a
   una sesión que estaba a punto de analizarse.

Y un hallazgo colateral que quedó anotado en `PENDIENTE.md`: **19 de 62 sesiones
(31 %) se abren y se cierran sin un solo turno**, una de ellas de 117,7 minutos.
Cada una consume un token efímero y cuenta contra el tope diario.

---

## Lección aprendida (el silencio que nadie oyó, 22/08)

`scripts/e2e_voz.py` es el cuarto de los cinco puntos que se trajeron del
peritaje: una prueba de punta a punta con navegador de verdad, micrófono
sintético y sesión Live real contra Gemini. Se escribió para automatizar lo que
`PENDIENTE.md` venía pidiendo a mano desde hacía días.

**Encontró el bug más caro del producto en su primera corrida.** La sesión abre
en 2,1 s, el planificador elige tema, la cara aparece, el estado dice «Te
escucho»… y pasan quince segundos sin que el tutor diga una palabra. El tutor
**no saluda nunca**: espera a que hable el niño.

Contado después sobre las 71 transcripciones reales: el niño abre la
conversación en las 52 que tienen contenido, el tutor en **cero**, y 19 quedaron
vacías. Una de cada cuatro sesiones muere antes de la primera palabra.

1. **Estaba a la vista desde el primer día y nadie lo vio.** Las 71
   transcripciones estaban en disco; bastaba contar quién habla primero, que es
   una línea de código. No se vio porque quien probaba el producto era quien lo
   construyó, y un adulto que sabe cómo funciona **siempre** saluda primero. El
   micrófono sintético no sabe nada del producto, y por eso se comportó como el
   usuario real que se queda callado esperando.
2. **La prueba de voz no valía por medir latencia.** Se justificó como «medir el
   silencio hasta que contesta» y terminó valiendo por algo que no estaba en la
   lista: que nadie contestaba. El valor de una prueba de punta a punta no es
   confirmar lo que ya se sabe, es que la ejecute alguien sin las suposiciones
   del que la escribió.
3. **El dato ya estaba en `PENDIENTE.md` y estaba mal explicado.** «19 de 62
   sesiones se abren sin un solo turno» llevaba tres hipótesis anotadas
   —recargas de página, sesiones que mueren al conectar, el navegador abriendo
   antes de tiempo— y ninguna era la buena. La causa no era técnica.
4. **Una prueba en rojo a propósito.** La comprobación «el tutor le habla
   primero al niño» queda fallando hasta que se arregle. Un e2e que se pone en
   verde bajando el listón deja de servir.

Y un detalle de método, porque se repitió: la prueba se verificó rompiendo lo
que mide —un `console.error` inyectado en el build— antes de creerle. Salió en
rojo con exit 1 y en verde con exit 0. Es la tercera vez en dos días que
comprobar el detector encuentra algo; la primera fue el inspector de la pizarra
y la segunda el hook de knowledge/, que aprobaba sin haber validado nada.

