/**
 * LAS PERILLAS DE LA CONVERSACIÓN, Y POR QUÉ VALE CADA UNA.
 *
 * Cada número de acá se movió por algo que pasó en una sesión real, y el
 * comentario que lo acompaña es la mitad que importa: sin él, el próximo que
 * quiera "afinar la latencia" mueve un umbral y devuelve un bug que costó un
 * día entero encontrar.
 *
 * Viven fuera de `useTutor` porque el hook llegó a 2.317 líneas y eso tuvo un
 * precio medible: el 25/08 se metieron dos regresiones seguidas ahí adentro —
 * un stream que se alargaba solo y un turno de audio que se descartaba— y las
 * dos fueron de no poder ver el archivo entero. La regla del repo dice que se
 * parte a las ~400 líneas y que se organiza CUANDO DUELE. Dolió.
 *
 * Están agrupadas por lo que gobiernan:
 *
 *   · el micrófono y el eco    — `UMBRAL_BARGE_IN`, `BLOQUES_RETENIDOS`, …
 *   · los tres vigilantes      — `MS_MUDEZ`, `MS_VOZ_MUDA`, `MS_VOZ_SIN_ACUSE`
 *   · las marcas que dejan     — `MARCA_DE_*`, lo que se lee en la transcripción
 *
 * Los tres vigilantes miran los tres lados de la conversación, y cada uno nació
 * de una sesión donde ese lado falló sin que nadie se enterara:
 *
 *   | vigilante           | qué mira                          |
 *   |---------------------|-----------------------------------|
 *   | `MS_MUDEZ`          | el tutor no contesta              |
 *   | `MS_VOZ_MUDA`       | el tutor contesta y no se le oye  |
 *   | `MS_VOZ_SIN_ACUSE`  | el niño habla y nadie lo oye      |
 */

/** Cada cuántos turnos se reporta al backend. Bajo = más seguro, más llamadas. */
export const TURNOS_POR_REPORTE = 2;

/**
 * Volumen (RMS) desde el que se considera que el niño está hablando de verdad,
 * y no que se coló el eco del propio tutor por los parlantes.
 *
 * El micrófono pide `echoCancellation`, así que lo que queda del tutor es
 * residuo: bien por debajo de esto. Una voz normal a medio metro anda en 0,03 a
 * 0,15. Si el tutor llegara a cortarse solo, este número sube; si al niño le
 * cuesta interrumpir, baja.
 */
export const UMBRAL_BARGE_IN = 0.045;

/**
 * Cuánto tiene que sostenerse esa voz antes de callar al tutor.
 *
 * Los bloques del micrófono son de ~64 ms: esto son tres seguidos. Una sílaba
 * los llena; una tos o un golpe en la mesa, no.
 */
/** Cuánto se calla el micro esperando que el tutor mire una imagen.

    Es un PISO de seguridad: lo normal es que el micro vuelva antes, en cuanto
    el tutor arranca a hablar.

    Eran 2 segundos, y ese número estaba puesto a ojo. Medido el 22/08 contra la
    API real (`scripts/verificar_dibujo.py`), lo que tarda el tutor en soltar su
    primer bloque de audio DESPUÉS de una imagen:

        1.250 ms · 1.328 ms · 3.188 ms      (y 7.328 ms tras un empujón)

    O sea que el micro se reabría A MITAD del procesamiento de la imagen, el
    audio entrante le cerraba el turno al modelo y el tutor se quedaba con la
    frase por la mitad — «¡Te quedó muy bien», y nada más. Se vio en dos de tres
    corridas con micrófono simulado, y es el silencio de `ses_5d101caf627f`.

    Ocho segundos cubre el peor caso medido con margen, y no cuesta lo que
    parece: el micro no espera los ocho segundos, espera a que el tutor hable. */
export const MS_ESPERANDO_MIRADA = 8000;

/** Lo que viaja junto al dibujo del niño. Es prompt, y por eso se prueba. */
export const AVISO_DEL_DIBUJO =
  "[Sistema: este es el dibujo que acaba de hacer el niño. ARRANCA diciendo " +
  "qué ves —la forma, los trazos, hacia dónde van— y recién después dile si " +
  "está o no está bien. Si le pediste una letra y dibujó otra, o le quedó al " +
  "revés, o no se entiende, DÍSELO: corregir es para lo que estás. Y cuando " +
  "algo esté bien, di CUÁL: 'la curva de abajo te salió cerradita' vale; 'te " +
  "quedó súper bien' NO VALE NUNCA, tampoco después de describirlo — es la " +
  "frase que le enseña que da igual cómo lo haga. No menciones este aviso.]";

export const MS_PARA_CORTAR = 200;

/**
 * Profundidad de la LÍNEA DE RETARDO del micrófono, en bloques de ~64 ms.
 *
 * Esto era un buffer "por si acaso": mientras el tutor sonaba se mandaba
 * silencio Y ADEMÁS se guardaba una copia del bloque, y al confirmarse el
 * barge-in esa copia salía *encima* del silencio que ya había ocupado su lugar
 * en el tiempo. Cada interrupción le metía al stream medio segundo de audio de
 * más, y el servidor quedaba procesando lo que el niño había dicho medio
 * segundo antes. **La deriva no se recuperaba nunca: se sumaba interrupción
 * tras interrupción**, hasta que el tutor contestaba a algo de tres turnos
 * atrás mientras el niño ya estaba en otra cosa. Es lo que RBH describió el
 * 25/08 como «mi audio le llega tarde, y al mismo tiempo que escucha habla»
 * (`ses_31593f90ab26`).
 *
 * Ahora la cola no es una copia: es el camino. Por cada bloque que entra sale
 * exactamente uno —silencio si era eco, el audio de verdad si el barge-in se
 * confirmó—, así que el stream avanza al mismo ritmo que el reloj de pared y no
 * se alarga nunca.
 *
 * El fondo tiene que cubrir lo que tarda el barge-in en confirmar la voz
 * (`MS_PARA_CORTAR` = 4 bloques) más un margen: el bloque con la primera sílaba
 * de la interrupción sigue adentro cuando se decide, y por eso sale íntegro.
 * Más fondo del necesario no ayuda y cuesta: es el hueco que el stream aguanta
 * mientras la cola se llena, al principio de cada turno del tutor.
 */
export const BLOQUES_RETENIDOS = 5;

/**
 * Cuánto se sigue reteniendo el micrófono DESPUÉS de que el tutor dejó de sonar.
 *
 * El eco no termina con la última muestra: queda la cola del parlante en la
 * sala y el retraso del propio micrófono. Y entre chunk y chunk la cola se
 * vacía sin que el tutor haya terminado nada. En los dos huecos el micro
 * soltaba audio con la voz del tutor adentro y el VAD del servidor le cortaba
 * la frase — ver `ReproductorContinuo.sonandoHace`.
 *
 * 300 ms cubre los dos y es menos que `MS_PARA_CORTAR` + un bloque: si el niño
 * arranca a hablar justo en ese borde, el barge-in todavía no lo había
 * confirmado, así que no se le come ninguna interrupción real.
 */
export const MS_COLA_ECO = 300;

/**
 * Tras callar al tutor, cuánto se espera a que el servidor lo confirme.
 *
 * El barge-in local apaga el parlante, pero Gemini sigue mandando el resto del
 * turno: **iban derecho al reproductor y el tutor volvía a sonar encima del
 * niño**, medio segundo después de que lo callaron. Esa es la mitad de
 * «al mismo tiempo que me escucha, está hablando» — la otra mitad era la
 * deriva de `BLOQUES_RETENIDOS`.
 *
 * No alcanza con tirar esos bloques: si el barge-in fue un falso positivo —una
 * silla, un eco fuerte— el servidor nunca va a cortar nada y el tutor se
 * quedaría mudo a mitad de frase, que es peor que el bug que se está tapando.
 * Así que se RETIENEN: si el servidor confirma el corte (`interrupted`) o el
 * turno termina, se tiran; si en este plazo no dijo nada, el barge-in se
 * equivocó y el tutor retoma donde iba.
 *
 * Un falso positivo cuesta entonces una pausa, no el turno. El plazo cubre el
 * viaje del audio hasta el VAD y su decisión, con margen.
 */
export const MS_ESPERA_CORTE_SERVIDOR = 900;

/**
 * Techo de lo que se retiene el micro esperando la PRIMERA palabra del tutor.
 *
 * El saludo es el turno más expuesto de la sesión: el micrófono se abre antes
 * de mandar la apertura, así que entre el envío y el primer chunk sonando no
 * hay nada que retenga, y todo lo que capte —una silla, alguien en la otra
 * pieza— sale hacia un VAD sensible que puede cortarle el saludo apenas
 * empieza.
 *
 * Es un TECHO, no una espera: se levanta en cuanto suena el primer bloque de
 * audio. Existe para que un saludo que nunca llega no deje al niño con el
 * micrófono mudo toda la sesión.
 */
export const MS_RETENER_APERTURA = 4000;

/**
 * Cuánto se le aguanta al tutor sin decir nada después de que el niño terminó
 * de hablar, antes de darlo por mudo.
 *
 * Diez segundos es una eternidad en una conversación —el tutor real contesta
 * en uno o dos— y esa holgura es a propósito: este reloj no está para apurarlo,
 * está para que un silencio que ya no va a terminar no dure para siempre.
 */
export const MS_MUDEZ = 10_000;

/**
 * Cuánto se espera DESPUÉS del empujón, que no es lo mismo.
 *
 * Medido el 22/08: cuando el modelo se traba y hay que empujarlo, su respuesta
 * tardó **15.281 ms** en arrancar — cinco veces lo que tarda un turno sano.
 * Volver a empujarlo a los 10 s sería atropellarlo justo cuando iba a hablar.
 */
export const MS_MUDEZ_TRAS_EMPUJON = 18_000;

/** Cuántos empujones antes de aceptar que no vuelve.
 *
 * Uno. Con dos, el niño acumula 46 s hablándole a una pantalla antes de que
 * alguien le diga algo — más de lo que aguanta un chico de 7. Así el peor caso
 * es 10 s de silencio + un intento + 18 s = 28 s hasta que la pantalla habla. */
export const EMPUJONES_ANTES_DE_RENDIRSE = 1;

/** Cuántas veces se reconecta el canal de voz antes de darlo por perdido.
 *
 * Una. El empujón destraba al modelo cuando el canal está sano; si después del
 * empujón sigue mudo, lo roto es el canal, y eso no se arregla hablándole más
 * fuerte — se arregla con un socket nuevo sobre la misma sesión.
 *
 * Pero una sola vez, y el contador NO se reinicia cuando el tutor vuelve a
 * hablar (a diferencia de los empujones). Si el canal se cae dos veces en la
 * misma sesión, el problema no es el socket: reintentar sin fin dejaría al niño
 * en un ciclo de silencios de medio minuto cada uno, que es peor que decirle la
 * verdad y dejarlo empezar de nuevo. */
export const RECONEXIONES_ANTES_DE_RENDIRSE = 1;

/**
 * Cuánto puede haber audio programado SIN SONAR antes de dar la voz por muda.
 *
 * ── EL VIGILANTE QUE FALTABA ─────────────────────────────────────────────
 *
 * Hay un vigilante para el tutor que no contesta (`MS_MUDEZ`) y otro para la
 * pestaña abandonada (`ABANDONO_SEG`). No había ninguno para el caso en que el
 * tutor contesta, la transcripción llega, el muñeco mueve la boca — y por el
 * parlante no sale nada. El niño lo descubre solo, y tarda:
 *
 *   · `ses_91c13b1747a2`: «¿por qué dejaste de hablar y solo estoy viendo el
 *     texto?» — el contexto de audio estaba suspendido.
 *   · `ses_6c6fb58aafbb`: «solo veo como al muñeco hablar, pero no estás
 *     hablando» — el contexto se había recreado fuera del gesto del usuario.
 *   · `ses_660ce383567d`: «estás hablando y hablando y como que no se escucha,
 *     solo leo lo que estás diciendo» — un turno retenido de más por el
 *     barge-in.
 *
 * Tres veces el mismo síntoma y tres causas distintas. Por eso esto no vigila
 * ninguna causa: vigila el SÍNTOMA — hay trozos programados y ninguno suena
 * (`ReproductorContinuo.vozMuda`). Cualquier causa futura cae en la misma red.
 *
 * Cuatro segundos: los trozos de Gemini duran bastante menos, así que en una
 * voz sana siempre termina alguno dentro de ese plazo. Un chunk largo no
 * alcanza a disparar un falso positivo.
 */
export const MS_VOZ_MUDA = 4_000;

/** Cada cuánto se mira. No hace falta más fino: la recuperación tarda más. */
export const MS_ENTRE_CHEQUEOS_DE_VOZ = 1_000;

/**
 * Cuánta VOZ DEL NIÑO puede salir sin que vuelva una sola sílaba transcripta.
 *
 * ── EL TERCER VIGILANTE, Y EL ÚNICO LADO QUE FALTABA ─────────────────────
 *
 * Los otros dos miran al tutor: que conteste (`MS_MUDEZ`) y que se le oiga
 * (`MS_VOZ_MUDA`). Este mira al niño, y tapa un agujero que era estructural:
 *
 *   **`vigilarMudez` se arma cuando llega transcripción del niño.** O sea que
 *   el vigilante del silencio depende de que la voz del niño llegue — y "la voz
 *   del niño no llega" es justamente el fallo que nadie estaba mirando.
 *
 * Se vio entero en `ses_60ea3b164f17` (25/08), y por primera vez con datos: el
 * diario de la voz muestra el último evento a los 3:42 y la sesión cerrada a
 * los 4:54. **Setenta segundos sin un solo evento** — ni latencia, ni tool, ni
 * mudez. Camila habló, nadie la oyó, y como su voz no llegó tampoco se armó el
 * reloj que habría empujado al tutor. La sesión murió en silencio y ella tuvo
 * que tocar el botón de terminar.
 *
 * Seis segundos es voz de verdad, no un carraspeo: se cuenta solo el audio que
 * SALE (el que va mudo por el eco del tutor no cuenta) y solo por encima del
 * umbral del barge-in.
 */
export const MS_VOZ_SIN_ACUSE = 6_000;

/** Lo que queda escrito cuando el niño habló y su voz no llegó a ningún lado. */
export const MARCA_DE_SORDERA = "[el niño habló acá y su voz no llegó]";

/** Lo que queda escrito en la transcripción cuando la voz se pierde.
 *
 * Es la mitad que convierte esto en algo diagnosticable: sin marca, una sesión
 * en la que el niño no oyó nada se ve idéntica a una sana — la transcripción
 * llega igual, porque llega por otro camino. Ver `medir_fluidez`. */
export const MARCA_DE_VOZ_MUDA = "[el niño no oyó esto: la voz no sonaba]";

/**
 * Cuánto silencio DEL NIÑO antes de dar por terminada la sesión.
 *
 * ESTE ES EL QUE NO GASTA PLATA A LO TONTO, y faltaba.
 *
 * El reaper del backend cierra nuestra fila, pero **no apaga el micrófono**:
 * si la pestaña sigue viva, el audio sigue viajando a Google y Google sigue
 * cobrando. Medido sobre las dos recargas de US$10: **US$0,038 por minuto**, y
 * **US$6,89 de US$20 se fueron en sesiones que nadie estaba usando** — una de
 * ellas de 117,7 minutos. Un tercio de todo el gasto.
 *
 * El techo de 45 minutos no alcanza: son US$1,71 por cada vez que un niño se
 * levanta y se va.
 *
 * Cuatro minutos es holgado a propósito. Un chico pensando calla veinte
 * segundos, no cuatro minutos; y si de verdad está trabajando —dibujando en la
 * hoja, acomodando el cuaderno para la foto— eso NO cuenta como silencio (ver
 * `hayAlguienTrabajando`). El error caro es cerrarle la sesión a un niño que
 * está ahí.
 */
export const MS_SIN_EL_NINO = 240_000;

/** El empujón. Es prompt —lo lee el modelo—, y por eso se prueba. */
export const AVISO_DE_MUDEZ =
  "[Sistema: el niño terminó de hablar hace rato y tú no has dicho nada. " +
  "Retoma tú AHORA: dile en una frase corta que se te fue el sonido un " +
  "momentico y pregúntale en qué iban. No inventes por qué pasó y no " +
  "menciones este aviso.]";

/** Lo que queda escrito en la transcripción cuando el tutor se calla.
 *
 * Sin esto la mudez es el único fallo del producto que no deja rastro: la
 * transcripción se ve igual que una donde el niño se aburrió y se fue. Va con
 * el prefijo entre corchetes que ya usan las marcas de sistema, así el Analista
 * la lee como evento y no como algo que alguien dijo. */
export const MARCA_DE_MUDEZ = "[el tutor no contestó: se quedó callado]";
