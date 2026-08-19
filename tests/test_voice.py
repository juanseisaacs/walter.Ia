"""Tests de la configuración de voz.

Sin API key: todo lo que importa acá es cómo se arma la configuración y que
quede atada al token. La conexión real la hace el navegador.
"""

import pytest

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
    """Cortarle la frase mientras piensa es lo peor que puede pasar acá."""
    assert deteccion_para_edad(7).silencio_ms >= 1200


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
    """
    texto = construir_instruccion_sistema("Juan, 7 años, 2° grado.")
    assert len(texto) < 38_000, (
        f"el prompt de sesión llegó a {len(texto)} caracteres. "
        "Antes de subir el techo: ¿qué párrafo cambia lo que el tutor DICE? "
        "Lo que solo explica el porqué va en knowledge/product/."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Los 4 tools
# ─────────────────────────────────────────────────────────────────────────────


def test_estan_declarados_los_cinco_tools():
    nombres = {t["name"] for t in DECLARACIONES_TOOLS}
    assert nombres == {
        "check_answer",
        "verify_arithmetic",
        "get_next_problem",
        "request_camera",
        "escalate_safety",
    }


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
    assert len(d["tools"][0]["functionDeclarations"]) == 5


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

    Sigue en pie que el prompt está gordo y que adelgazarlo de verdad —mover
    doctrina a knowledge/product/— es deuda abierta. Subir un techo no la paga.
    """
    texto = construir_instruccion_sistema("Juan, 7 años, 2° grado.", primer_encuentro=True)
    assert len(texto) < 40_000, (
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
