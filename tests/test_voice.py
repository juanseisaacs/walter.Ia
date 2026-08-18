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


def test_los_tres_prompts_existen_y_no_estan_vacios():
    for nombre in ("tutor_persona", "socratic_playbook", "safety_policy"):
        assert len(cargar_prompt(nombre)) > 200, f"{nombre} está vacío o es un stub"


def test_un_prompt_faltante_falla_ruidosamente():
    with pytest.raises(FileNotFoundError):
        cargar_prompt("no_existe")


def test_la_instruccion_junta_las_cuatro_partes():
    texto = construir_instruccion_sistema("Juan, 7 años, 2° grado.")
    assert "hermano mayor" in texto, "falta la persona"
    assert "escalera" in texto.lower(), "falta el método"
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
# Los 4 tools
# ─────────────────────────────────────────────────────────────────────────────


def test_estan_declarados_los_cuatro_tools():
    nombres = {t["name"] for t in DECLARACIONES_TOOLS}
    assert nombres == {"check_answer", "get_next_problem", "request_camera", "escalate_safety"}


def test_check_answer_le_dice_al_modelo_que_no_calcule_el():
    """La aritmética no la valida un modelo. Tiene que estar dicho en el tool."""
    tool = next(t for t in DECLARACIONES_TOOLS if t["name"] == "check_answer")
    assert "vos no calculás" in tool["description"]
    assert "tal cual" in tool["parameters"]["properties"]["respuesta_nino"]["description"]


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
    assert len(d["tools"][0]["functionDeclarations"]) == 4


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
