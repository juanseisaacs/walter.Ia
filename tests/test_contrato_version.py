"""El contrato de VERSIÓN entre el backend y la pestaña del niño.

El backend define lo que el tutor PUEDE pedir (las declaraciones de tools viajan
atadas al token) y el navegador define lo que SABE hacer con eso. Son dos
programas distintos, en dos lenguajes distintos, y **el segundo puede llevar
horas abierto sin enterarse de que el primero cambió**.

Pasó el 23/08 en `ses_4ed4e930e60f`, y el log del servidor lo muestra sin lugar
a dudas: `POST /api/sesiones` llegó ANTES del primer `GET /`. O sea que la
pestaña no se cargó de ese servidor — estaba abierta desde antes, con el
JavaScript anterior vivo en memoria. Mientras tanto el backend, recién
reiniciado, le decía al modelo que podía pedir `cantidades` para dibujar sumas.

    tutor: «no pude ponerte los pollitos en la pizarra ahora mismo»
    nino:  «Muéstrame, en el tablero, muéstrame.»
    tutor: «como que el tablero no me quiere funcionar hoy»

No falló la pizarra: hablaron dos versiones distintas, con el niño en el medio.

Este archivo comprueba que las dos puntas del arreglo siguen conectadas. Cada
una sola es inútil: un backend que anuncia su build y un front que no lo mira, o
un front que mira una clave que el backend dejó de mandar, fallan **en silencio**
— que es exactamente como falló la primera vez.
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
API_TS = RAIZ / "web" / "src" / "api.ts"
USE_TUTOR = RAIZ / "web" / "src" / "voz" / "useTutor.ts"


def _texto(ruta: Path) -> str:
    assert ruta.exists(), (
        f"No existe {ruta.relative_to(RAIZ)}. Si el archivo se movió, actualizá "
        f"la ruta acá: si no, este test pasa sin comprobar nada."
    )
    return ruta.read_text(encoding="utf-8")


def test_el_navegador_sabe_que_version_es_el_mismo():
    """El front tiene que poder decir con qué build está corriendo.

    Sale de `import.meta.url`, que en producción trae el nombre con hash que le
    puso Vite. Es un número de versión que nadie tiene que acordarse de subir:
    cambia exactamente cuando cambia el código.
    """
    ts = _texto(API_TS)
    assert "import.meta.url" in ts, "el front no tiene forma de saber qué versión es"
    assert "MI_BUILD" in ts


def test_el_navegador_compara_con_el_backend_y_se_recarga():
    ts = _texto(API_TS)
    assert "/salud" in ts, "el chequeo no consulta al backend"
    assert ".build" in ts, "no lee la versión que el backend anuncia"
    assert "location.reload()" in ts, "detecta que está viejo y no hace nada al respecto"


def test_el_chequeo_corre_ANTES_de_abrir_la_sesion():
    """El orden es la mitad del arreglo.

    Recargar con la sesión ya abierta deja una sesión huérfana contando contra
    el cupo diario del niño, y —peor— el niño ya oyó al tutor saludar. El
    chequeo va antes de `abrirSesion`, cuando todavía no hay nada que perder.
    """
    ts = _texto(USE_TUTOR)
    assert "recargarSiEstoyViejo" in ts, "nadie llama al chequeo"
    assert ts.index("recargarSiEstoyViejo()") < ts.index("api.abrirSesion"), (
        "el chequeo de versión quedó DESPUÉS de abrir la sesión"
    )


def test_el_chequeo_no_puede_entrar_en_bucle():
    """Si tras recargar seguimos viejos, el navegador está sirviendo su caché y
    recargar otra vez no arregla nada: sería un niño mirando una pantalla que
    parpadea para siempre. Se intenta UNA vez y después se dice."""
    ts = _texto(API_TS)
    assert "sessionStorage" in ts, "sin marca, una recarga que no arregla se repite sin fin"


def test_el_microfono_se_calla_mientras_el_tutor_habla():
    """LA CAUSA DE QUE EL TUTOR SE CORTARA A MITAD DE PALABRA.

    Medido con `python -m scripts.medir_fluidez` sobre las 8 transcripciones del
    23/08: **20 de 99 turnos del tutor quedaron partidos** —«¡Ah, ya lo veo!
    Mira,», «está en la pizarrita blanca justo»—. RBH lo dijo dentro de la
    sesión: «se corta y no terminas de hablar y te demoras un poco al regresar».

    El micrófono mandaba audio SIEMPRE, también mientras el tutor sonaba. El VAD
    del servidor corre con `START_SENSITIVITY_HIGH` —puesta a propósito para que
    el niño que habla bajito abra turno— y con ese oído el eco del propio tutor
    cuenta como "el niño empezó a hablar": el servidor le cortaba la generación.
    Por eso la frase queda partida también en la transcripción.

    El arreglo NO fue bajar la sensibilidad (eso devuelve el bug de Felipe: sus
    respuestas se perdían). Fue dejar de mandarle al servidor el eco del tutor.

    Este test mira el orden, que es lo único que importa: el `return` que retiene
    tiene que estar ANTES del `sendRealtimeInput`. Si alguien mueve el envío
    arriba, el bug vuelve entero y en silencio.

    Y mira la CONDICIÓN, que es la mitad que faltaba. Retener mientras
    `reproductor.hablando` fuera true tapó el caso largo y dejó dos huecos
    cortos: entre chunk y chunk —Gemini manda en ráfagas y la cola se vacía a
    mitad de frase— y la cola del parlante después de la última muestra. Por
    esos dos siguió cortándose: en `ses_0a6036dedf55`, 2 de 8 turnos, y el
    saludo de apertura partido en «¿tienes alguna». El niño: «no terminaste de
    hablar, como que se te cortó la frase».
    """
    ts = _texto(USE_TUTOR)
    inicio = ts.index("MIENTRAS EL TUTOR HABLA, EL AUDIO NO SALE")
    envio = ts.index("sendRealtimeInput", inicio)
    retencion = ts.index("pasarPorLaCola(retenidos, muestras", inicio)
    assert retencion < envio, "el audio vuelve a salir mientras el tutor habla"
    assert "silencioPcm16Base64" in ts[retencion:], (
        "sin buffer, interrumpir cuesta la primera sílaba"
    )

    # `hablando` pelado deja pasar el eco por los huecos: la condición tiene que
    # ser la que aguanta después del último sonido.
    condicion = ts[inicio:envio]
    assert "sonandoHace(MS_COLA_ECO)" in condicion, (
        "sin cola de guarda, el eco se escapa entre chunks y le corta la frase"
    )


def test_lo_retenido_sale_como_silencio_mientras_sea_eco():
    """Mientras el tutor suena, lo que sale de la cola va MUDO.

    Esos bloques son el eco del propio tutor: mandarlos le abriría al niño un
    turno sobre algo que nadie dijo, y con `START_SENSITIVITY_HIGH` le cortaría
    la generación a mitad de palabra. Solo salen con su audio de verdad cuando
    el barge-in ya confirmó que abajo estaba el niño.
    """
    ts = _texto(USE_TUTOR)
    assert "interrumpio: interrumpioDeVerdad" in ts, (
        "la cola ya no sabe si lo que lleva adentro es el niño o el eco del tutor"
    )
    cola = _texto(RAIZ / "web" / "src" / "voz" / "colaDelMicrofono.ts")
    assert "mudo: reteniendo && !interrumpio" in cola, (
        "la cola dejó de distinguir el eco del tutor de la voz del niño"
    )
    # Y del lado de `useTutor`, lo que sale mudo tiene que salir como SILENCIO y
    # no como nada: si el stream se para, el reloj del VAD se para con él.
    assert "bloque.mudo" in ts and "silencioPcm16Base64" in ts


def test_por_cada_bloque_que_entra_sale_exactamente_uno():
    """LA INVARIANTE QUE FALTABA, y sin ella el stream se alarga solo.

    `ses_31593f90ab26` (25/08): «creo que a veces mi audio le llega tarde, y
    como que al mismo tiempo que escucha está hablando».

    La cola era una COPIA: mientras el tutor sonaba se mandaba silencio y además
    se guardaba el bloque, y al confirmarse el barge-in la copia salía ENCIMA
    del silencio que ya había ocupado ese lugar en el tiempo. Medio segundo de
    audio de más por cada interrupción, que el stream no recupera nunca — se
    acumulan, y el servidor termina procesando lo que el niño dijo turnos atrás
    mientras el tutor ya está en otra cosa.

    Ahora la cola es el camino, no una copia: entra un bloque, sale un bloque.
    El test mira las dos mitades de eso — que el bloque enviado salga de la cola
    (`shift`) y no sea el recién capturado, y que no exista ningún envío del
    bloque actual en paralelo al de la cola.
    """
    ts = _texto(USE_TUTOR)
    inicio = ts.index("UN BLOQUE ENTRA, UN BLOQUE SALE")
    fin = ts.index("micRef.current = captura", inicio)
    bucle = ts[inicio:fin]

    assert "pasarPorLaCola(retenidos, muestras" in bucle, "el audio ya no entra por la cola"
    assert "aPcm16Base64(muestras)" not in bucle, (
        "el bloque recién capturado se manda por fuera de la cola: el stream se "
        "alarga y la voz del niño le llega al servidor cada vez más tarde"
    )

    # Y la cola en sí, que es donde vive la cuenta.
    cola = _texto(RAIZ / "web" / "src" / "voz" / "colaDelMicrofono.ts")
    assert "cola.push(muestras)" in cola and "cola.shift()" in cola, (
        "la cola dejó de ser el camino del audio y volvió a ser una copia"
    )


def test_el_tutor_callado_no_vuelve_a_sonar_encima_del_nino():
    """La otra mitad de «al mismo tiempo que me escucha, está hablando».

    El barge-in apaga el parlante, pero Gemini sigue mandando el resto del
    turno: esos bloques iban derecho al reproductor y el tutor volvía a sonar
    medio segundo después de que lo callaron.

    Y no se tiran, se retienen: si el barge-in fue un falso positivo el servidor
    nunca va a confirmar el corte, y tirarlos dejaría al tutor mudo a mitad de
    frase — peor que el bug. Vencido el plazo, retoma.
    """
    ts = _texto(USE_TUTOR)
    audio = ts.index("parte.inlineData?.data")
    programa = ts.index("reproductor.programar(parte.inlineData.data)", audio)
    guarda = ts[audio:programa]

    assert "turnoAbortadoRef.current" in guarda, (
        "el audio de un turno ya cortado vuelve al parlante encima del niño"
    )
    assert "enDudaRef.current.push" in guarda, (
        "el audio en duda se tira en vez de guardarse: un barge-in equivocado "
        "deja al tutor mudo a mitad de frase"
    )
    # Y las dos formas que tiene el servidor de confirmar el corte lo limpian.
    assert "turnoAbortadoRef.current = 0" in ts[ts.index("contenido?.interrupted") :], (
        "el servidor confirma el corte y la duda queda colgada"
    )


def test_el_saludo_tambien_esta_protegido():
    """EL TURNO MÁS EXPUESTO DE LA SESIÓN, y era el único sin cubrir.

    El micrófono se abre ANTES de mandar la apertura, así que entre el envío y
    el primer bloque de audio no hay reproductor que retenga nada: todo lo que
    capte el micro —una silla, alguien en la otra pieza— sale hacia un VAD en
    `START_SENSITIVITY_HIGH` que puede leerlo como que el niño ya está hablando
    y cortarle el saludo apenas empieza.

    Es un TECHO y no una espera: se levanta con la primera voz del tutor. Sin
    ese `= 0`, un saludo que nunca llega dejaría al niño con el micrófono mudo
    toda la sesión — mucho peor que el bug que se está tapando.
    """
    ts = _texto(USE_TUTOR)
    assert "MS_RETENER_APERTURA" in ts, "el saludo sale sin nadie reteniendo el micro"
    assert "retenerHastaRef.current = 0" in ts, "el techo tiene que poder levantarse"

    # Y se levanta con el AUDIO del tutor, no con cualquier mensaje del
    # servidor: la transcripción de lo que dijo el propio niño llega antes y
    # reabriría el micro justo en el hueco que esto viene a tapar. Es el mismo
    # error que ya se cometió con `esperandoMiradaRef`.
    audio = ts.index("parte.inlineData?.data")
    fin = ts.index("reproductor.programar(parte.inlineData.data)", audio)
    assert "retenerHastaRef.current = 0" in ts[audio:fin], (
        "el techo del saludo se levanta con la voz del tutor, no antes"
    )


def test_el_stream_de_audio_nunca_se_corta():
    """LA CAUSA RAÍZ DE QUE LA CONVERSACIÓN SE ENREDARA Y SE CAYERA.

    `ses_02805f3edba1` (24/08): 25 turnos, la voz del niño llegando tarde, las
    frases pisándose, y al final dos mudeces seguidas y la sesión muerta. RBH:
    *«parecía como si mi voz llegara tarde, y entonces como que se enredaba, y
    al final se cayó y no pudimos seguir»*.

    El arreglo del 23/08 resolvió un bug creando otro. Para que el eco del tutor
    no le cortara la generación, el micrófono dejó de mandar audio mientras el
    tutor hablaba — o sea, **cortó el stream**. Y la Live API dice:

        «`silenceDurationMs` only works within a continuous stream — it
         measures quiet periods, not stream interruptions.»

    El VAD del servidor no mide el paso del tiempo: mide el audio que le llega.
    Sin audio su reloj SE DETIENE, el turno del niño se queda colgado sin
    cerrar, y cuando el micrófono vuelve —varios segundos después— lo nuevo se
    pega con lo viejo como si fueran contiguos.

    La corrección es mandar SILENCIO en vez de nada: el eco no viaja (sigue en
    pie el 23/08) y el reloj del VAD sigue corriendo.

    Este test es el que importa de los dos: comprueba que en el camino de
    retención hay un ENVÍO y no un `return` pelado. Si alguien vuelve a sacarlo
    "porque no manda nada útil", el bug regresa entero y en silencio — y esta
    vez ya sabemos cómo se siente.
    """
    ts = _texto(USE_TUTOR)
    inicio = ts.index("MIENTRAS EL TUTOR HABLA, EL AUDIO NO SALE")
    # El bloque de envío va desde ahí hasta el final del callback del micrófono.
    fin = ts.index("micRef.current = captura", inicio)
    retencion = ts[inicio:fin]

    assert "silencioPcm16Base64" in retencion, (
        "el micrófono volvió a cortar el stream: sin audio, el reloj del VAD se "
        "detiene y el turno del niño no se cierra nunca"
    )
    assert "sendRealtimeInput" in retencion, (
        "se genera el silencio pero no se manda: el stream sigue cortado"
    )


def test_la_pausa_deliberada_cierra_el_stream_como_pide_la_api():
    """La única pausa real que queda: mientras el tutor mira una imagen.

    Ahí el micrófono SÍ se calla —hasta 8 s, ver `MS_ESPERANDO_MIRADA`— porque
    si no, el flujo le mantendría el turno abierto al niño y el `turnComplete`
    de la imagen no dispararía nada (`ses_6b430731226f`).

    Para ese caso la Live API pide avisar:

        «when the audio stream is paused for more than a second… an
         `audioStreamEnd` event should be sent to flush any cached audio.»

    Sin eso, lo que el niño alcanzó a decir antes de mandar la foto queda
    cacheado del lado del servidor y se pega con lo que hable después, como si
    no hubieran pasado ocho segundos en el medio.
    """
    ts = _texto(USE_TUTOR)
    assert "audioStreamEnd" in ts, "la pausa del micrófono no flushea el audio cacheado"
    # Y va ANTES de mandar la imagen: flushear después ya no separa nada.
    flush = ts.index("audioStreamEnd")
    imagen = ts.index("inlineData: { mimeType: \"image/jpeg\"", flush - 3000)
    assert flush < imagen, "el stream se cierra después de mandar la imagen: no separa nada"


def test_reconectar_no_cierra_la_sesion_del_backend():
    """LA OTRA MITAD DE «se cayó y no pudimos seguir» (`ses_02805f3edba1`).

    Reconectar existe para conservar la sesión: los ejercicios cargados, los
    turnos, la habilidad del día. Si el camino de reconexión llamara a
    `terminar()` —que es lo que hace el arranque normal— cerraría justo lo único
    que vale la pena salvar, y el niño terminaría igual que antes: empezando de
    cero.

    Es un error fácil de reintroducir, porque las dos ramas viven en la misma
    función y la del arranque normal SÍ tiene que cerrar.
    """
    ts = _texto(USE_TUTOR)
    inicio = ts.index("if (reconectandoRef.current) {")
    fin = ts.index("} else if (sesionRef.current) {", inicio)
    rama = ts[inicio:fin]
    assert "terminar(" not in rama, (
        "la rama de reconexión cierra la sesión del backend: no queda nada que "
        "reconectar"
    )
    assert "soltarRecursos(" in rama, "hay que soltar el socket viejo o quedan dos vivos"


def test_el_banco_de_ejercicios_sobrevive_a_la_reconexion():
    """Al reconectar, el backend manda `ejercicios: []` A PROPÓSITO: el
    navegador ya los tiene y puede haber usado la mitad.

    Si el front los asignara igual, el banco quedaría vacío y el tutor se
    quedaría sin nada que darle al niño — o peor, se los repetiría."""
    ts = _texto(USE_TUTOR)
    assert "if (sesion.ejercicios?.length) {" in ts, (
        "el banco se reemplaza sin mirar si vino vacío"
    )


def test_la_reconexion_esta_acotada():
    """Sin tope, un canal que se cae solo deja al niño en un ciclo de silencios
    de medio minuto cada uno. El contador NO puede reiniciarse al reconectar:
    si se reiniciara en `soltarRecursos` —por donde pasa la reconexión— el tope
    sería decorativo."""
    ts = _texto(USE_TUTOR)
    assert "RECONEXIONES_ANTES_DE_RENDIRSE" in ts, "la reconexión no tiene tope"
    reset = ts.index("reconexionesRef.current = 0")
    inicio_terminar = ts.index("const terminar = useCallback(")
    assert reset > inicio_terminar, (
        "el contador se reinicia fuera de `terminar`: la reconexión lo borraría "
        "en cada vuelta y el tope no serviría de nada"
    )


def test_la_reconexion_no_mata_el_audiocontext():
    """EL BUG DE «solo veo al muñeco hablar» (`ses_6c6fb58aafbb`).

    `ReproductorContinuo.iniciar()` lo dice en su primera línea: hay que
    llamarlo DENTRO de un gesto del usuario o el navegador deja el contexto
    suspendido.

    Una reconexión no viene de un gesto: la dispara el reloj de la mudez. La
    primera versión cerraba el reproductor y creaba otro — o sea, creaba uno
    muerto. Los chunks llegaban, se programaban contra un reloj detenido, y no
    sonaba nada. El personaje se seguía animando porque lo mueve el estado y no
    el sonido, así que desde afuera parecía que el tutor hablaba:

        nino: «solo veo como al muñeco hablar, pero no estás hablando»
        nino: «se cerró y ahora ya no te escucho. Solo te puedo leer»

    El contexto que se creó al empezar SÍ nació en un gesto. Se conserva.
    """
    ts = _texto(USE_TUTOR)
    inicio = ts.index("if (reconectandoRef.current) {")
    fin = ts.index("} else if (sesionRef.current) {", inicio)
    rama = ts[inicio:fin]
    assert "soltarRecursos(true)" in rama, (
        "la reconexión cierra el AudioContext y crea otro fuera de un gesto: "
        "el niño ve al personaje hablar y no oye nada"
    )

    # Y el reproductor se REUSA, no se reemplaza: crear uno nuevo acá es
    # exactamente el mismo bug por la otra puerta.
    assert "reproductorRef.current ?? new ReproductorContinuo()" in ts, (
        "se crea un reproductor nuevo aunque ya haya uno vivo"
    )


def test_hay_un_vigilante_FUERA_de_la_pestana():
    """LA LECCIÓN ESTRUCTURAL, y la razón de que esto fuera whack-a-mole.

    Todos los vigilantes del sistema viven DENTRO del navegador: la mudez, el
    reloj de sesión, el techo de tokens, la reconexión. Todos son `setTimeout`
    en la pestaña.

    **Un vigilante que vive adentro de lo que vigila no puede detectar que eso
    muera.** Por eso cada forma nueva de morirse nos tomaba por sorpresa: se
    llevaba puesto al vigilante junto con todo lo demás.

    `ses_610e057cfd91` quedó `activa`, sin `fin` y con 0 tokens; en el log no
    hay `/cerrar` ni `/reconectar`. Para el backend seguía viva.

    Dos piezas, y las dos hacen falta:
      · el LATIDO, que el navegador manda mientras está vivo — sin él, mirar los
        turnos daría por muerto a un niño que está dibujando en la hoja;
      · el REAPER, que corre en el backend en su propio reloj.
    """
    ts = _texto(USE_TUTOR)
    assert "api.latido(" in ts, "el navegador no late: el reaper no puede ver nada"

    api_py = (RAIZ / "src" / "tutor" / "api.py").read_text(encoding="utf-8")
    assert "_barrer_abandonadas" in api_py, "nadie barre las sesiones abandonadas"
    assert "asyncio.create_task" in api_py, "el reaper está definido pero no corre"


def test_la_pestana_que_se_va_cierra_su_sesion():
    """El `useEffect` de limpieza corre al DESMONTAR React, no cuando el
    navegador se lleva la página entera. Ahí un `fetch` se cancela a mitad de
    vuelo y la sesión queda huérfana — con su cupo tomado y sin llegar al
    Analista.

    `pagehide` y no `beforeunload`: es el único confiable en móvil, donde el
    sistema mata pestañas de fondo sin avisar. Y `sendBeacon` y no `fetch`,
    porque el navegador se compromete a entregarlo aunque la página ya no esté.
    """
    ts = _texto(USE_TUTOR)
    assert '"pagehide"' in ts, "nada escucha que la pestaña se vaya"
    assert "cerrarConBeacon" in ts, "se cierra con fetch, que se cancela al irse la página"
    assert "sendBeacon" in _texto(API_TS), "no usa el único método que sobrevive al cierre"


def test_la_app_entera_tiene_red_de_error():
    """La mitad visible de «al final desapareció».

    El límite de error existía solo alrededor del tablero: la lección se aprendió
    ahí y se aplicó solo ahí. Un error en el personaje, en el visor de la cámara
    o en el propio `App` seguía blanqueando la pantalla — React desmonta todo y
    el niño se queda mirando blanco sin saber qué pasó.
    """
    main = (RAIZ / "web" / "src" / "main.tsx").read_text(encoding="utf-8")
    assert "SinTumbarLaSesion" in main, "la app entera sigue sin red de error"
    assert "respaldo" in main, (
        "sin respaldo, el límite de error muestra `null`: la misma pantalla en "
        "blanco que viene a evitar"
    )


def test_todo_cierre_del_navegador_dice_su_motivo():
    """FIN DE LAS INVESTIGACIONES FORENSES.

    Cuatro veces seguidas RBH dijo «se desapareció» y cuatro veces averiguar por
    qué fue media hora de log del servidor terminando en una hipótesis. La causa
    no era ninguno de los bugs: era que **el sistema no registraba su propia
    causa de muerte**. Todo cierre pasaba por un booleano.

    Cada camino que cierra la sesión tiene que decir cuál es. Si alguien agrega
    uno nuevo sin etiqueta, la próxima vez volvemos a adivinar.
    """
    ts = _texto(USE_TUTOR)
    motivos = [
        "nino_termino",  # el botón
        "techo_tokens",
        "techo_tiempo",
        "mudez",
        "reconexion_fallo",
        "otra_pestana",
        "desmontaje",
        "arranque_nuevo",
        "pestana_cerrada",  # el beacon, en api.ts
    ]
    faltan = [m for m in motivos if m not in ts and m not in _texto(API_TS)]
    assert not faltan, f"estos cierres no dicen por qué: {faltan}"


def test_el_dibujo_del_nino_no_se_borra_al_mandarlo():
    """LO QUE PIDIÓ EL NIÑO, con todas las letras (`ses_74b6cc7667ae`):

        «Sería bueno que cuando yo te envío algo que yo escribí en el tablero,
         NO SE DESAPAREZCA, sino que tú me corrijas encima de la palabra.»

    Se borraba en el instante en que la mandaba, así que escuchaba «fíjate que
    el palito de la h tiene que subir un poco más» mirando una hoja en blanco —
    sin la letra de la que le estaban hablando, y sin poder corregirla.
    """
    ts = _texto(USE_TUTOR)
    inicio = ts.index("const enviarDibujo")
    fin = ts.index("[mostrarleAlTutor", inicio)
    enviar = ts[inicio:fin]
    assert "setHoja(null)" not in enviar, "vuelve a borrarle el dibujo al mandarlo"
    assert "setDibujoEnviado(true)" in enviar, "el niño no sabe si salió"


def test_el_navegador_corta_si_el_nino_se_fue():
    """LO QUE EL REAPER NO PUEDE HACER, Y CUESTA PLATA DE VERDAD.

    El reaper del backend cierra la fila en la base. **No apaga el micrófono**:
    si la pestaña sigue viva, el audio sigue viajando a Google y Google sigue
    cobrando. Son dos vigilantes que miran cosas distintas —uno la pestaña
    muerta, el otro el niño ausente con la pestaña viva— y hacen falta los dos.

    Medido sobre dos recargas de US$10: **US$0,038 por minuto**, y **US$6,89 de
    US$20 se fueron en sesiones que nadie estaba usando**, una de ellas de 117,7
    minutos. Un tercio de todo el gasto.

    El techo de 45 minutos no alcanzaba: son US$1,71 cada vez que un niño se
    levanta y se va.
    """
    ts = _texto(USE_TUTOR)
    assert "MS_SIN_EL_NINO" in ts, "nada corta la sesión si el niño se va"
    assert "nino_inactivo" in ts, "el cierre por inactividad no dice su motivo"

    # Y NO puede cortar mientras el niño trabaja en silencio: dibujando en la
    # hoja o acomodando el cuaderno para la foto. Es la misma trampa que casi
    # se comete con el reaper, y sería un arreglo peor que el bug.
    inicio = ts.index("MS_SIN_EL_NINO) return;")
    bloque = ts[inicio - 1200 : inicio]
    assert "hojaRef.current" in bloque, "le cerraría la sesión a un niño dibujando"
    assert "esperandoMiradaRef.current" in bloque, "cortaría mientras el tutor mira una foto"
