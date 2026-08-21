"""Tests de la configuración de voz.

Sin API key: todo lo que importa acá es cómo se arma la configuración y que
quede atada al token. La conexión real la hace el navegador.
"""

from datetime import datetime

import pytest

from tutor.curriculum import cargar_grafo
from tutor.models import Nino
from tutor.pedagogy import resumen_para_prompt
from tutor.voice import (
    DECLARACIONES_TOOLS,
    SAMPLE_RATE_ENTRADA,
    SAMPLE_RATE_SALIDA,
    ConfiguracionSesion,
    DeteccionFinTurno,
    EmisorFalso,
    cargar_prompt,
    construir_instruccion_sistema,
    deteccion_para_edad,
)


def _config(resumen: str = "Juan, 7 años, 2° grado.", modo: str = "guiado") -> ConfiguracionSesion:
    return ConfiguracionSesion(
        instruccion_sistema=construir_instruccion_sistema(resumen, modo),
        deteccion=deteccion_para_edad(7),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Parámetros de audio: requisitos del API, no preferencias
# ─────────────────────────────────────────────────────────────────────────────


def test_sample_rates_son_los_que_exige_gemini():
    """16k entrada / 24k salida. Con otros valores no entiende o cambia el tono."""
    assert SAMPLE_RATE_ENTRADA == 16_000
    assert SAMPLE_RATE_SALIDA == 24_000


# ─────────────────────────────────────────────────────────────────────────────
# Fin de turno: la perilla para niños
# ─────────────────────────────────────────────────────────────────────────────


def test_los_mas_chicos_reciben_mas_paciencia():
    """Un nene de 5 arma la frase mientras habla; uno de 10 ya responde como adulto.
    Un solo valor para todos molesta a los dos extremos."""
    assert deteccion_para_edad(5).silencio_ms > deteccion_para_edad(7).silencio_ms
    assert deteccion_para_edad(7).silencio_ms > deteccion_para_edad(10).silencio_ms


def test_espera_mas_que_un_default_de_adulto():
    """Cortarle la frase mientras piensa es lo peor que puede pasar acá.

    Bajado de 1200 a 800 el 20/08, y es una decisión medida, no un aflojar:

    · La paciencia real la da `END_SENSITIVITY_LOW`, que sigue puesta. Ese es el
      ajuste que tolera la pausa a mitad de frase. Este número es solo un piso, y
      el piso lo paga TODO turno — también "hola" y "sí".
    · Adelantarse no rompe nada: el navegador maneja `interrupted` y corta la
      reproducción al instante si el niño sigue hablando. Llegar tarde sí costó:
      en `ses_764305b3c3ed` el niño preguntó "¿por qué te demoraste tanto?" en su
      primer turno.

    El piso se mantiene por encima de un default de adulto (500-800 ms). Si un
    niño se siente cortado mientras piensa, se sube
    `config.SILENCIO_FIN_TURNO_MS` — y este test es el que obliga a que eso sea
    una decisión y no un descuido.
    """
    assert deteccion_para_edad(7).silencio_ms >= 800
    assert deteccion_para_edad(7).sensibilidad_fin == "END_SENSITIVITY_LOW", (
        "si se saca la sensibilidad baja, el temporizador corto sí corta al niño"
    )
    assert deteccion_para_edad(5).silencio_ms > deteccion_para_edad(10).silencio_ms


def test_la_deteccion_se_serializa_para_gemini():
    d = DeteccionFinTurno(silencio_ms=1500).a_dict_gemini()
    assert d["automaticActivityDetection"]["silenceDurationMs"] == 1500
    assert "startOfSpeechSensitivity" in d["automaticActivityDetection"]


# ─────────────────────────────────────────────────────────────────────────────
# Prompts: son datos, no código
# ─────────────────────────────────────────────────────────────────────────────


def test_los_cuatro_prompts_existen_y_no_estan_vacios():
    for nombre in ("tutor_persona", "socratic_playbook", "valores", "safety_policy"):
        assert len(cargar_prompt(nombre)) > 200, f"{nombre} está vacío o es un stub"


def test_un_prompt_faltante_falla_ruidosamente():
    with pytest.raises(FileNotFoundError):
        cargar_prompt("no_existe")


def test_la_instruccion_junta_las_cinco_partes():
    texto = construir_instruccion_sistema("Juan, 7 años, 2° grado.")
    assert "hermano mayor" in texto, "falta la persona"
    assert "escalera" in texto.lower(), "falta el método"
    assert "no hay una lección de valores" in texto.lower(), "faltan los valores"
    assert "escalate_safety" in texto, "falta la política de seguridad"
    assert "Juan" in texto, "falta el niño"


def test_el_modo_pedido_agrega_su_instruccion():
    guiado = construir_instruccion_sistema("Juan.", modo="guiado")
    pedido = construir_instruccion_sistema("Juan.", modo="pedido")
    assert "no es hacerle la tarea" in pedido
    assert "no es hacerle la tarea" not in guiado


def test_el_playbook_prohibe_dar_la_respuesta():
    """Si alguien afloja esta línea del .md, el producto deja de ser el producto."""
    playbook = cargar_prompt("socratic_playbook").lower()
    assert "nunca das la respuesta" in playbook


def test_la_politica_de_seguridad_cubre_lo_esencial():
    politica = cargar_prompt("safety_policy").lower()
    for tema in ["datos personales", "secreto", "ante la duda"]:
        assert tema in politica, f"la política no menciona: {tema}"


# ─────────────────────────────────────────────────────────────────────────────
# Lo que trajo la Constitución (knowledge/product/constitucion_valores.md)
#
# Cada uno de estos protege una decisión razonada. Si uno falla, alguien aflojó
# una línea del .md — y los .md no los revisa el compilador.
# ─────────────────────────────────────────────────────────────────────────────


def test_el_playbook_separa_la_convencion_del_resultado():
    """La única puerta abierta a explicar derecho, y su candado.

    Sin este par, "no enseñas de una sola manera" se lee como permiso para
    resolverle el ejercicio. Ver ARCHITECTURE.md §18, decisión 1.
    """
    playbook = cargar_prompt("socratic_playbook").lower()
    assert "no se descubren pensando" in playbook, "falta la puerta"
    assert "el resultado del ejercicio que están haciendo" in playbook, "falta el candado"
    assert "no hay escalón 5" in playbook, "la escalera dejó de tener techo"


def test_los_valores_prohiben_el_elogio_inflado():
    """Línea roja 14. Es la más fácil de violar sin darse cuenta: suena a cariño."""
    valores = cargar_prompt("valores").lower()
    for frase in ["eres un genio", "eres el mejor", "eres increíble"]:
        assert frase in valores, f"el prompt no veta explícitamente: {frase}"
    assert "el elogio inflado hace" in valores, "falta la razón, y sin razón no se sostiene"


def test_los_valores_no_predican():
    """El ADN es cristiano; la expresión es universal (Constitución §7).

    Si una de estas palabras aparece en el prompt del tutor, el destilado se
    hizo mal: la doctrina se queda en el documento fundacional.
    """
    valores = cargar_prompt("valores").lower()
    for palabra in ["dios", "jesús", "biblia", "cristian", "oración", "pecado"]:
        assert palabra not in valores, f"se coló doctrina en el prompt: {palabra}"


def test_la_seguridad_no_implementa_la_excepcion_de_fe_declarada():
    """Decisión aplazada, no descartada (Constitución §7, ARCHITECTURE.md §18).

    El MVP devuelve TODA pregunta religiosa a la familia. Si algún día se
    implementa el marco de fe declarado por el papá, este test falla — y ese es
    el punto: que la decisión se tome mirando, no por goteo.
    """
    politica = cargar_prompt("safety_policy").lower()
    assert "se conversan mejor con tus" in politica, "falta la devolución a la familia"
    assert "nunca oras con él" in politica, "falta la prohibición"
    for marca in ["si la familia es cristiana", "marco de fe", "familia cristiana"]:
        assert marca not in politica, f"se implementó la excepción sin decidirla: {marca}"


def test_la_seguridad_distingue_el_riesgo_de_la_travesura():
    """Constitución §6.2.8. Escalar todo destruye la confianza que hace útil escalar."""
    politica = cargar_prompt("safety_policy").lower()
    assert "no se escala y no se reporta como un evento" in politica
    assert "escalas el riesgo, no la travesura" in politica


def test_el_tutor_llega_a_la_sesion_con_su_nombre():
    """Sin nombre fijo el modelo se inventa uno distinto cada sesión, y un tutor
    que ayer se llamaba otra cosa no es el que lo conoce desde marzo."""
    from tutor import config as cfg

    texto = construir_instruccion_sistema("Juan, 7 años.")
    assert cfg.NOMBRE_TUTOR in texto, "el tutor no sabe cómo se llama"
    assert "nunca te presentas con un nombre distinto" in texto.lower()


def test_la_voz_no_usa_regionalismos_cerrados():
    """El registro es colombiano neutro: un toque, no un disfraz. Las palabras
    muy locales las entiende menos gente que el producto quiere alcanzar."""
    persona = cargar_prompt("tutor_persona").lower()
    assert "chévere" in persona, "se perdió el toque colombiano"
    assert "español colombiano neutro" in persona, "se perdió el registro neutro"
    for jerga in ["parce", "güevón", "sisas"]:
        assert jerga in persona, f"dejó de vetarse la jerga: {jerga}"


def test_los_valores_no_invaden_lo_academico():
    """El riesgo del prompt de valores es que el tutor pare una suma para dar una
    lección de liderazgo. Formar es cómo trata al niño, no un tema con turno."""
    valores = cargar_prompt("valores").lower()
    assert "nunca interrumpes lo académico" in valores
    assert "el tema entra solo si el niño lo trae" in valores


def test_el_prompt_de_sesion_no_engorda_sin_que_nadie_mire():
    """Regla dura: el prompt de sesión se mantiene flaco (ARCHITECTURE.md §9).

    Al adoptar la Constitución completa pasó de ~11 KB a ~31 KB. Ese salto fue
    una decisión tomada; el próximo tiene que ser otra decisión tomada, no el
    resultado de que cada quien agregue su párrafo.

    Subido a 38 KB el 18/08, y esta es la decisión: entraron "Los ejercicios no
    los inventas tú" en el playbook y la lista de temas del banco. Las dos
    cambian lo que el tutor HACE — sin ellas improvisaba los ejercicios y la
    sesión no escribía dominio. No es doctrina: es qué tiene en la mano.

    Queda dicho que el prompt está gordo (~36,7 KB de un techo de 38) y que
    adelgazarlo es deuda abierta. NO es costo — entra una vez por sesión, ~$0,20
    al mes, medido el 18/08. Es latencia de la primera frase.

    ═══ 19/08: el techo de 38 KB era inalcanzable, y el test no lo veía ═══

    Medía el caso más flaco posible —resumen literal, sin primer encuentro, sin
    temas, modo guiado— y daba 36,8 KB. La sesión REAL más pesada es otra, y es
    la primera de todas: un niño que estrena el tutor y llega con tarea.

        base (persona 11,3 + playbook 11,2 + valores 6,9 + safety 6,7)  36,161
        + primer_encuentro (solo sesión 1)                              +2,231
        + bloque de temas del banco                                       +~550
        + modo pedido                                                     +~250
        + resumen del niño                                                +~800
        ────────────────────────────────────────────────────────────────────────
                                                                        ~40,000

    O sea: la base sola deja 1,8 KB libres, y `primer_encuentro` pide 2,2 KB. El
    techo se rompía desde el día en que ese bloque entró — el test pasaba porque
    medía una sesión que en producción no existe.

    **La decisión (tomada, no descuidada): el techo sube a 41 KB y el test mide
    el peor caso alcanzable.** Un número honesto que se rompe cuando algo crece
    vale más que uno bonito que nunca se ejerce. No es costo (~$0,20 al mes,
    medido el 18/08); es latencia de la primera frase, y adelgazar el prompt
    queda como la deuda abierta #1 — con el desglose de arriba, es media hora de
    trabajo decidir qué sale.

    Nótese que la primera sesión y el perfil lleno son excluyentes:
    `primer_encuentro` se activa con `madurez_vinculo == 0`, cuando el Analista
    todavía no escribió nada. Por eso el peor caso se mide dos veces y se toma
    el mayor, en vez de sumar cosas que no coexisten.
    
    ═══ 20/08, tarde: el techo BAJA de 41.000 a 36.000 ═══

    Llegó a 40.995 de 41.000 —cinco caracteres libres— y ahí dejó de ser deuda
    para ser una pared: la instrucción siguiente no cabía.

    Se pagó como corresponde: moviendo el porqué a `knowledge/product/` y
    dejando las reglas. `tutor_persona` 11.911 → 7.792, `socratic_playbook`
    12.132 → 8.935. **No se quitó ni una regla** — los tests de este archivo son
    la prueba, porque fijan las frases que no se pueden perder.

    Lo que salió: la despedida de la relación (pasa UNA vez y se leía en CADA
    sesión, el mismo patrón que `primer_encuentro`), las anécdotas que
    justificaban cada regla, y las secciones que decían dos veces lo mismo.

    El peor caso quedó en 34.902, y el techo baja a 36.000 en el mismo
    movimiento: uno que quedó a 6 KB de distancia deja de avisar nada, y la
    grasa vuelve sin que nadie lo note.
    """
    grafo = cargar_grafo()
    temas = [(h.id, h.nombre.es) for h in list(grafo)[:6]]
    receso = datetime(2026, 6, 25, 10, 0)  # la guía de momento más larga

    # (a) Primera sesión con tarea: perfil vacío, pero carga `primer_encuentro`.
    estrena = Nino(id="a", nombre="Sofía", edad=10, grado=5)

    # (b) Sesión 40 con tarea: sin `primer_encuentro`, pero con la ficha llena.
    veterano = Nino(id="b", nombre="Sofía", edad=10, grado=5)
    veterano.perfil.intereses = ["fútbol", "dinosaurios", "minecraft", "patinaje"]
    veterano.perfil.motivadores = ["competir contra el reloj", "explicarle a su hermano", "retos"]
    veterano.perfil.frustraciones = ["que le digan que va lento", "los problemas largos", "ruido"]
    veterano.perfil.estilo_comunicacion = "directo, sin vueltas, con humor"
    veterano.perfil.notas = "N" * 400  # el Analista desbordado: lo recorta `pedagogy`
    veterano.perfil.contexto_escolar = "C" * 400
    veterano.perfil.madurez_vinculo = 12

    peor = 0
    for nino, primer in ((estrena, True), (veterano, False)):
        texto = construir_instruccion_sistema(
            resumen_para_prompt(nino, grafo, receso),
            modo="pedido",
            temas=temas,
            tema_principal=temas[0][0],
            primer_encuentro=primer,
        )
        peor = max(peor, len(texto))

    assert peor < 36_000, (
        f"el peor caso del prompt de sesión llegó a {peor} caracteres. "
        "Antes de subir el techo: ¿qué párrafo cambia lo que el tutor DICE? "
        "Lo que solo explica el porqué va en knowledge/product/."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Los 4 tools
# ─────────────────────────────────────────────────────────────────────────────


def test_estan_declarados_los_tools():
    nombres = {t["name"] for t in DECLARACIONES_TOOLS}
    assert nombres == {
        "check_answer",
        "verify_arithmetic",
        "get_next_problem",
        "request_camera",
        "escalate_safety",
        "mostrar_en_pizarra",
        "pedir_dibujo",
    }


def test_los_tools_de_la_pizarra_no_cortan_el_habla():
    """LA CONDICIÓN PARA QUE LA PIZARRA SIRVA EN VEZ DE ESTORBAR.

    Un tool normal corta el turno: el modelo se calla, espera la respuesta y
    arranca de nuevo. Es exactamente el silencio del que Felipe se quejó
    ("¿te fuiste? ¿por qué te quedas callado?", ses_c973ffe7b267).

    Con NON_BLOCKING el tutor sigue hablando mientras el tablero se pinta —
    escribe y explica a la vez, como un profesor. Sin esto, cada dibujo le
    devuelve al niño la latencia que costó dos días sacar.
    """
    for nombre in ("mostrar_en_pizarra", "pedir_dibujo"):
        tool = next(t for t in DECLARACIONES_TOOLS if t["name"] == nombre)
        assert tool.get("behavior") == "NON_BLOCKING", f"{nombre} cortaría el habla"


def test_la_pizarra_no_le_pide_coordenadas_al_modelo():
    """El tutor dice QUÉ mostrar, nunca DÓNDE.

    Pedirle `x, y` obliga al modelo a hacer cálculo de maquetación —es malo en
    eso— y produce elementos superpuestos, fuera de pantalla o de tamaños
    inconsistentes, que además no se adaptan entre un celular y un portátil.
    """
    tool = next(t for t in DECLARACIONES_TOOLS if t["name"] == "mostrar_en_pizarra")
    campos = set(tool["parameters"]["properties"])
    assert not (campos & {"x", "y", "x1", "y1", "ancho", "alto", "color", "tamano"}), (
        "la pizarra volvió a pedir coordenadas: el layout lo resuelve ella"
    )


def test_check_answer_le_dice_al_modelo_que_no_calcule_el():
    """La aritmética no la valida un modelo. Tiene que estar dicho en el tool."""
    for nombre in ("check_answer", "verify_arithmetic"):
        tool = next(t for t in DECLARACIONES_TOOLS if t["name"] == nombre)
        assert "tú no calculas" in tool["description"]
        assert "tal cual" in tool["parameters"]["properties"]["respuesta_nino"]["description"]


def test_las_descripciones_de_los_tools_no_hablan_en_voseo():
    """Son parte del prompt efectivo, y el modelo imita el registro de sus
    instrucciones: es la lección que costó la sesión del 17/08. Un tutor bogotano
    con tools escritas en argentino termina mezclando."""
    texto = " ".join(t["description"] for t in DECLARACIONES_TOOLS).lower()
    for voseo in ["vos ", "calculás", "tenés", "querés", "usalo", "dale"]:
        assert voseo not in texto, f"voseo en las declaraciones: {voseo}"


def test_escalate_safety_empuja_a_escalar_ante_la_duda():
    tool = next(t for t in DECLARACIONES_TOOLS if t["name"] == "escalate_safety")
    assert "duda" in tool["description"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# La configuración que viaja atada al token
# ─────────────────────────────────────────────────────────────────────────────


def test_la_config_de_gemini_lleva_todo_lo_necesario():
    d = _config().a_dict_gemini()
    assert d["responseModalities"] == ["AUDIO"]
    assert d["systemInstruction"]
    assert d["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"]
    assert d["realtimeInputConfig"]["automaticActivityDetection"]
    assert len(d["tools"][0]["functionDeclarations"]) == len(DECLARACIONES_TOOLS)


def test_pide_transcripcion_de_las_dos_puntas():
    """Sin transcripción no hay Analista, ni Vigilante, ni auditoría del método."""
    d = _config().a_dict_gemini()
    assert "inputAudioTranscription" in d
    assert "outputAudioTranscription" in d


def test_la_transcripcion_de_entrada_fija_idioma_y_sesga_los_numeros():
    """El `{}` vacío dejaba autodetectar: el ruido salía coreano y "dos" salía
    "32", congelando al Analista. La entrada va con idioma fijo y palabras-número."""
    entrada = _config().a_dict_gemini()["inputAudioTranscription"]
    assert entrada["languageCodes"], "sin idioma fijo, autodetecta y falla con ruido"
    assert "dos" in entrada["adaptationPhrases"], "sesga hacia las palabras-número"


def test_el_emisor_falso_no_toca_la_red():
    emisor = EmisorFalso()
    token = emisor.emitir(_config())
    assert token.token.startswith("falso-")
    assert len(emisor.emitidos) == 1


def test_lo_que_se_ata_al_token_incluye_seguridad_y_metodo():
    """EL CANDADO #1: el navegador recibe un token, no una configuración.
    No puede cambiar la persona, el método ni la política de seguridad."""
    emisor = EmisorFalso()
    emisor.emitir(_config())

    atado = emisor.emitidos[0].a_dict_gemini()["systemInstruction"]
    assert "nunca das la respuesta" in atado.lower()
    assert "escalate_safety" in atado


def test_el_bloque_del_modo_pedido_no_vosea():
    """El prompt no se puede contradecir a sí mismo sobre cómo habla.

    `tutor_persona.es.md` veta el voseo argentino, pero el bloque del modo
    Pedido vivía hardcodeado en `voice.py` y quedó en voseo cuando los .md se
    reescribieron a colombiano neutro: el mismo prompt decía "nunca vosees" y
    dos párrafos después voseaba ("Usá eso como material: aplicás la MISMA
    escalera"). El modelo imita el registro de lo que lee, y dos registros en
    una instrucción son dos tutores.

    Se mide el DELTA entre los dos modos, que es exactamente el texto escrito
    en Python. Buscar el voseo en el prompt entero no sirve: la persona lista
    esas mismas formas para vetarlas.
    """
    guiado = construir_instruccion_sistema("Juan, 7 años.", modo="guiado")
    pedido = construir_instruccion_sistema("Juan, 7 años.", modo="pedido")
    solo_pedido = pedido.replace(guiado, "").lower()

    assert solo_pedido.strip(), "el modo pedido dejó de agregar su bloque"
    for forma in ["usá", "aplicás", "tenés", "querés", "mirá", "decile", "cerrá", "dale"]:
        assert forma not in solo_pedido, f"voseo en el bloque del modo pedido: {forma!r}"


def test_el_primer_encuentro_solo_entra_la_primera_vez():
    """El patrón que mantiene el prompt flaco: lo que aplica a veces, entra a
    veces. Un tutor que en la sesión 40 sigue leyendo cómo presentarse gasta
    atención en algo que ya pasó, además de gastar espacio.
    """
    normal = construir_instruccion_sistema("Juan, 7 años.")
    primera = construir_instruccion_sistema("Juan, 7 años.", primer_encuentro=True)

    assert "Hoy se conocen" in primera
    assert "Hoy se conocen" not in normal, "el guion del primer día quedó pegado siempre"
    assert "Yo no te doy las respuestas" in primera, "falta el acuerdo que más se prueba"


def test_el_primer_encuentro_tambien_cabe_bajo_el_techo():
    """El caso especial es el MÁS pesado, así que es el que hay que medir.

    Mirar solo la sesión normal deja crecer el primer encuentro sin que nadie
    lo vea — hasta que un niño nuevo estrena el prompt más gordo del sistema.

    Techo propio (40 KB) y no el de la sesión normal (38 KB), decidido el 18/08
    tras chocar tres veces en una tarde. Este caso carga un bloque entero de más
    por definición, así que medirlo contra el mismo número obligaba a comprimir
    prosa que estaba bien cada vez que se tocaba cualquier otra sección. Los dos
    techos siguen puestos y siguen siendo decisiones; lo que cambió es que ahora
    son dos, porque son dos casos distintos.

    Se dijo acá que adelgazar de verdad —mover doctrina a knowledge/product/—
    era deuda abierta, y que subir un techo no la paga. Se pagó el 20/08: el
    prompt bajó 7,3 KB, este caso quedó en 33.256, y el techo BAJA de 40.000 a
    35.000 en el mismo movimiento.
    """
    texto = construir_instruccion_sistema("Juan, 7 años, 2° grado.", primer_encuentro=True)
    assert len(texto) < 35_000, (
        f"el prompt del primer encuentro llegó a {len(texto)} caracteres"
    )


def test_el_primer_encuentro_no_escribe_el_nombre_a_mano():
    """El nombre vive en `config.NOMBRE_TUTOR` para tener un solo lugar que
    cambiar — por país, o el día que la familia pueda elegirlo. Un ejemplo con
    el nombre escrito en el .md lo convierte en dos lugares, y el segundo es el
    que nadie se acuerda de tocar."""
    from tutor import config as cfg

    guion = cargar_prompt("primer_encuentro")
    assert cfg.NOMBRE_TUTOR not in guion, (
        f"'{cfg.NOMBRE_TUTOR}' quedó escrito a mano en primer_encuentro.es.md"
    )


def test_el_primer_encuentro_no_le_ensena_al_nino_a_desconfiar_de_la_memoria():
    """PASÓ DE VERDAD, `ses_47dfebd9aa43` (20/08).

    Felipe preguntó "¿sabes quién soy?". El tutor contestó que no estaba seguro
    de si ya habían hablado y que *"como soy una inteligencia artificial, a veces
    mi memoria no funciona tan bien"*. Cuatro turnos después lo llamó Felipe, y
    el niño lo cazó: *"¿por qué antes no me dijiste que era Felipe?"*.

    Dos daños en una frase. El chico: le enseñó que puede contradecirse. Y el
    producto: la memoria longitudinal es el criterio #3 de YC, y el tutor la
    estaba desmintiendo con su propia boca. Un niño al que le dicen que a este
    tutor se le olvidan las cosas no le cuenta nada que valga la pena recordar.
    """
    texto = cargar_prompt("primer_encuentro").lower()
    assert "primera vez que hablamos" in texto, "falta la respuesta directa"
    assert "tu memoria falla" in texto, "falta la prohibición de desmentir su memoria"
    assert "tu familia" in texto, "no debe adivinar si fue la mamá o el papá"


def test_la_voz_del_nino_abre_turno_aunque_hable_bajito():
    """PASÓ DE VERDAD, `ses_c973ffe7b267` (20/08).

    El tutor preguntó cuánto daba 4+4+4+4+4, Felipe contestó "veinte" bajito y
    ese audio se descartó: el turno nunca se abrió. En la transcripción no
    existe. Dos turnos después el niño reclamó *"ya te dije que 20, ¿no me
    escuchaste?"*.

    La configuración lo decía sin darse cuenta: LOW = "un chico que murmura no
    abre turno". Un niño CONTESTANDO murmura.

    Los dos errores no cuestan lo mismo: un disparo falso abre un turno vacío y
    se sigue; perder la respuesta le enseña al niño que no lo escuchan.
    """
    d = deteccion_para_edad(7)
    assert d.sensibilidad_inicio == "START_SENSITIVITY_HIGH", (
        "con LOW se pierde la respuesta del niño que contesta bajito"
    )
    assert d.padding_inicio_ms >= 300, "sin padding se come el arranque de la palabra"


def test_el_playbook_no_deja_declararle_al_nino_que_si_puede():
    """`ses_c973ffe7b267`: Felipe dijo "yo creo que no puedo" y el tutor
    respondió "claro que puedes".

    La Constitución es explícita: la confianza en sí mismo no se declara, se
    construye con logros reales. Decirle "sí puedes" mientras sigue sin poder es
    la versión amable de no ayudarlo — y le enseña que las palabras del tutor no
    describen la realidad.
    """
    playbook = cargar_prompt("socratic_playbook").lower()
    assert "no puedo" in playbook, "falta el caso: dice que ÉL no es capaz"
    assert "no se declara" in playbook, "falta la razón, y sin razón no se sostiene"


def test_el_tutor_sabe_que_tiene_pizarra_y_no_la_niega():
    """PASÓ DE VERDAD, `ses_6a7a36736734` (20/08), con la pizarra ya integrada.

        nino:  "no lo logro imaginar, ¿me lo podrías hacer más visual?"
        tutor: [se lo explica de palabra]
        nino:  "¿pero no podrías tú dibujarlo?"
        tutor: "Mira que no puedo dibujar por ahora."

    Los siete tools estaban en el token —verificado: Google valida `behavior` y
    rechaza un valor inventado con 400—. O sea que el tutor TENÍA el tablero y
    dijo que no. La instrucción hablaba de CUÁNDO usarla y nunca de que la
    tiene, así que al preguntarle por su capacidad contestó desde lo que cree
    ser, no desde lo que puede hacer.

    Negar algo que sí puede hacer es peor que no poder: el niño aprende a no
    pedirlo, y la función queda muerta aunque funcione.
    """
    playbook = cargar_prompt("socratic_playbook").lower()
    assert "tienes una pizarra" in playbook, "falta que sepa que la tiene"
    assert "nunca digas que no puedes dibujar" in playbook, "falta la prohibición"


def test_la_pizarra_le_muestra_al_modelo_como_traducir_lo_que_pide_el_nino():
    """El otro medio hallazgo de esa sesión: el niño pidió "2 canastas con 9
    manzanas" y eso el tablero SÍ lo puede mostrar (`grupos`). El modelo no hizo
    la conexión porque la descripción listaba los tipos en abstracto.

    Un ejemplo concreto por tipo vale más que la lista de tipos. Y va en la
    descripción del tool, que no paga el techo del prompt de sesión.
    """
    tool = next(t for t in DECLARACIONES_TOOLS if t["name"] == "mostrar_en_pizarra")
    d = tool["description"]
    assert "canastas" in d, "falta el ejemplo que traduce lo que pide el niño"
    assert "→" in d, "los ejemplos tienen que mostrar el mapeo, no solo nombrar tipos"


def test_ninguna_regla_se_cae_al_adelgazar_el_prompt():
    """EL CONTRAPESO DE LOS DOS TECHOS.

    Los techos empujan a recortar; esto define qué NO se puede perder al
    hacerlo. Sin este test, adelgazar es apostar: se corta prosa, el peso baja,
    los tests siguen verdes y una regla desapareció sin que nadie lo note —
    hasta que el tutor le regala una respuesta a un niño.

    Cada línea es una promesa del producto. Si una falla al recortar, o se
    reescribe la regla en menos palabras, o el recorte se deshace. Lo que no se
    hace es borrarla y seguir.

    Se buscan frases que caben en UN renglón: el texto va envuelto a 80 columnas
    y una frase partida por un salto de línea no matchea aunque esté ahí.
    """
    texto = construir_instruccion_sistema(
        "Juan, 7 años, 2° grado.", modo="pedido", primer_encuentro=True
    ).lower()

    reglas = {
        "no da la respuesta": "nunca das la respuesta",
        "explica lo convencional": "no se descubren pensando",
        "no explica el resultado": "el resultado del ejercicio que están haciendo",
        "la escalera tiene techo": "no hay escalón 5",
        "el 'no puedo' se responde con un logro": "no se declara",
        "sabe que tiene pizarra": "tienes una pizarra",
        "no niega saber dibujar": "nunca digas que no puedes dibujar",
        "la aritmética no la hace él": "la verifica la herramienta, no tú",
        "'cerca' es un dato": 'cerca" es un dato',
        "no cede por insistencia": "no cedas por insistencia",
        "el elogio nombra algo real": "elogio vacío",
        "el nombre no cambia": "nunca te presentas con un nombre distinto",
        "registro colombiano neutro": "español colombiano neutro",
        "veta la jerga callejera": "parcero",
        "no finge ser humano": "nunca finges ser humano",
        "aguanta el enojo sin enfriarse": "estás bravo conmigo",
        "no inventa por qué falló": "no inventes la",
        "no describe una foto que no llegó": "no describas nada",
        "la primera vez no miente sobre lo que sabe": "primera vez",
        "los ejercicios salen del banco": "nunca de tu cabeza",
        "no dice los nombres de los tools": "nunca se dicen en voz alta",
        "el modo pedido es más estricto": "no es hacerle la tarea",
        "la seguridad puede escalar": "escalate_safety",
        "los valores no se predican": "no hay una lección de valores",
    }

    faltan = [nombre for nombre, frase in reglas.items() if frase not in texto]
    assert not faltan, "el prompt adelgazó de más y perdió reglas: " + ", ".join(faltan)


def test_los_prompts_del_tutor_tampoco_vosean():
    """El modelo imita el registro de lo que lee.

    Ya había test para las descripciones de los tools y para el resumen del
    niño, pero no para los .md que forman el prompt — y ahí se coló "podés ser
    juguetón" el 20/08. Una instrucción en voseo es una invitación a que el
    tutor le hable así al niño, que es justo lo que `tutor_persona` prohíbe.
    """
    import re

    voseo = re.compile(
        r"\b(podés|tenés|querés|hacés|sabés|decís|comés|sumás|contás|mirá|fijate|"
        r"pensá|andá|dale|sos)\b",
        re.IGNORECASE,
    )
    for nombre in ("tutor_persona", "socratic_playbook", "valores", "safety_policy"):
        texto = cargar_prompt(nombre)
        # La línea que VETA el voseo nombra las formas: esa no cuenta.
        lineas = [ln for ln in texto.splitlines() if "voseo" not in ln.lower()]
        for ln in lineas:
            if (m := voseo.search(ln)):
                raise AssertionError(f"voseo en {nombre}.es.md: {m.group()!r} — {ln.strip()[:70]}")
