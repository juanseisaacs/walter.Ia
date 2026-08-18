"""Tests de los tools.

El grueso está en `check_answer`: es la pieza donde un error destruye la
confianza del papá. El principio que verifican estos tests es
TOLERANTE CON LA FORMA, ESTRICTO CON EL VALOR.
"""

import pytest

from tutor.models import Ejercicio, Habilidad, Materia, TextoLocalizado
from tutor.tools import (
    BancoDeSesion,
    Distancia,
    Veredicto,
    check_answer,
    escalate_safety,
    palabras_a_numero,
    request_camera,
    verify_arithmetic,
)


def _ej(respuesta: str, eid: str = "e1") -> Ejercicio:
    return Ejercicio(
        id=eid,
        habilidad_id="mat.suma.con_reagrupacion",
        enunciado=TextoLocalizado(es="27 + 15"),
        respuesta=respuesta,
        validado=True,
    )


def _habilidad(verificable: bool) -> Habilidad:
    return Habilidad(
        id="x.y",
        nombre=TextoLocalizado(es="X"),
        descripcion=TextoLocalizado(es="X"),
        materia=Materia.MATEMATICAS,
        grado_sugerido=2,
        verificable_en_codigo=verificable,
    )


def _es_correcto(respuesta_esperada: str, dijo: str) -> bool:
    return check_answer(_ej(respuesta_esperada), dijo).veredicto == Veredicto.CORRECTO


# ─────────────────────────────────────────────────────────────────────────────
# Números en palabras — el caso de la voz
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "palabras,numero",
    [
        ("cero", 0),
        ("siete", 7),
        ("quince", 15),
        ("dieciseis", 16),
        ("veintidos", 22),
        ("cuarenta y dos", 42),
        ("noventa y nueve", 99),
        ("cien", 100),
        ("ciento veinte", 120),
        ("trescientos cuarenta y cinco", 345),
        ("mil", 1000),
    ],
)
def test_entiende_numeros_dichos_en_palabras(palabras, numero):
    """Un nene de 7 anos dice 'cuarenta y dos', no '42'.

    Sin esta traduccion, TODAS sus respuestas habladas figuran como incorrectas.
    """
    assert palabras_a_numero(palabras) == numero


def test_los_acentos_no_importan():
    """El motor de voz puede transcribir con o sin tilde."""
    assert palabras_a_numero("dieciseis") == palabras_a_numero("dieciséis") == 16


def test_una_palabra_desconocida_invalida_la_lectura():
    """Mejor no entender que adivinar mal."""
    assert palabras_a_numero("cuarenta y banana") is None
    assert palabras_a_numero("no se") is None


# ─────────────────────────────────────────────────────────────────────────────
# Tolerante con la forma
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "dijo",
    [
        "42",
        " 42 ",
        "42!",
        "es 42",
        "son 42",
        "el resultado es 42",
        "creo que es 42",
        "cuarenta y dos",
        "es cuarenta y dos",
        "42 manzanas",
        "cuarenta y dos figuritas",
    ],
)
def test_acepta_la_respuesta_correcta_dicha_de_cualquier_forma(dijo):
    assert _es_correcto("42", dijo), f"deberia aceptar: {dijo!r}"


def test_acepta_coma_decimal():
    """En Colombia se escribe 4,5 — no 4.5."""
    assert _es_correcto("4.5", "4,5")
    assert _es_correcto("4,5", "4.5")


# ─────────────────────────────────────────────────────────────────────────────
# Estricto con el valor
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("dijo", ["41", "43", "cuarenta y uno", "24", "420", "4"])
def test_rechaza_lo_que_esta_mal(dijo):
    """LA REGLA: 41 nunca es 42. Sin 'casi', sin redondeo, sin piedad."""
    assert not _es_correcto("42", dijo), f"NO deberia aceptar: {dijo!r}"


def test_no_adivina_cuando_hay_varios_numeros():
    """'42 o 43' es ambiguo. Adivinar seria peor que pedir que repita."""
    assert not _es_correcto("42", "42 o 43")


def test_una_respuesta_vacia_o_confusa_no_pasa():
    for dijo in ["", "   ", "no se", "ni idea"]:
        assert not _es_correcto("42", dijo)


def test_deja_ver_que_entendio():
    """Para auditar: si el nino reclama que dijo bien, se puede revisar."""
    r = check_answer(_ej("42"), "cuarenta y dos")
    assert r.valor_interpretado == "42"


# ─────────────────────────────────────────────────────────────────────────────
# Lo que el codigo NO puede juzgar
# ─────────────────────────────────────────────────────────────────────────────


def test_comprension_y_redaccion_requieren_juicio():
    """Devolver INCORRECTO aca seria mentir: no esta mal, es que esta pregunta
    no se contesta con una comparacion."""
    r = check_answer(_ej("el nino estaba triste"), "estaba triste", _habilidad(verificable=False))
    assert r.veredicto == Veredicto.REQUIERE_JUICIO


def test_matematica_si_se_verifica_en_codigo():
    r = check_answer(_ej("42"), "42", _habilidad(verificable=True))
    assert r.veredicto == Veredicto.CORRECTO


def test_respuestas_de_texto_se_comparan_normalizadas():
    assert _es_correcto("mayor que", "es mayor que")
    assert not _es_correcto("mayor que", "menor que")


# ─────────────────────────────────────────────────────────────────────────────
# Banco de sesion
# ─────────────────────────────────────────────────────────────────────────────


def test_el_banco_no_repite_ejercicios():
    banco = BancoDeSesion([_ej("1", "e1"), _ej("2", "e2"), _ej("3", "e3")])
    entregados = [banco.get_next_problem().id for _ in range(3)]
    assert entregados == ["e1", "e2", "e3"]
    assert len(set(entregados)) == 3


def test_el_banco_avisa_cuando_se_agota():
    banco = BancoDeSesion([_ej("1", f"e{i}") for i in range(5)])
    assert not banco.se_esta_agotando()
    for _ in range(3):
        banco.get_next_problem()
    assert banco.se_esta_agotando(), "session.py debe recargar antes de quedarse sin nada"


def test_banco_vacio_devuelve_none_sin_romper():
    assert BancoDeSesion([]).get_next_problem() is None


def test_el_banco_recuerda_lo_entregado():
    """Insumo del Analista: que ejercicios vio el nino en esta sesion."""
    banco = BancoDeSesion([_ej("1", "e1"), _ej("2", "e2")])
    banco.get_next_problem()
    assert [e.id for e in banco.entregados] == ["e1"]


# ─────────────────────────────────────────────────────────────────────────────
# Camara y seguridad: decisiones, no efectos
# ─────────────────────────────────────────────────────────────────────────────


def test_pedir_camara_devuelve_una_intencion():
    assert request_camera("ver la tarea del cuaderno").motivo == "ver la tarea del cuaderno"


def test_escalar_seguridad_marca_su_origen():
    """Dos caminos independientes a la alarma. Este es el del tutor."""
    alerta = escalate_safety("el nino menciono algo preocupante", evidencia="cita textual")
    assert alerta.origen == "tutor"
    assert alerta.evidencia == "cita textual"


# ─────────────────────────────────────────────────────────────────────────────
# verify_arithmetic — lo que el tutor improvisa
# ─────────────────────────────────────────────────────────────────────────────
# Los tres casos de ses_91c13b1747a2 donde el tutor evaluó de memoria y se
# equivocó. Cada uno es un momento real en que un nino de 7 anos escucho algo
# falso sobre su propia respuesta.


def test_los_tres_errores_reales_de_la_sesion_quedan_atrapados():
    # "135 mas 241" -> el nino dijo 780; el tutor: "estas muy cerca" (es 376)
    r = verify_arithmetic("135 + 241", "780")
    assert r.veredicto == Veredicto.INCORRECTO
    assert r.distancia == Distancia.LEJOS, "780 no esta cerca de 376"

    # "578 menos 34" -> el nino dijo 400; el tutor: "estas cerca" (es 544)
    assert verify_arithmetic("578 - 34", "400").distancia == Distancia.LEJOS

    # "7 menos 3" -> el nino dijo "cuarenta y ocho"; el tutor: "!Eso!"
    assert verify_arithmetic("7 - 3", "cuarenta y ocho").veredicto == Veredicto.INCORRECTO


def test_entiende_lo_que_el_nino_dice_en_palabras():
    assert verify_arithmetic("7 - 3", "cuatro").veredicto == Veredicto.CORRECTO
    assert verify_arithmetic("135+241", "trescientos setenta y seis").veredicto == Veredicto.CORRECTO


def test_cerca_es_una_medida_no_una_impresion():
    """La frase que mas se dijo a la ligera. Ahora sale de un numero."""
    assert verify_arithmetic("578 - 34", "545").distancia == Distancia.CERCA
    assert verify_arithmetic("578 - 34", "544").distancia == Distancia.EXACTO
    assert verify_arithmetic("578 - 34", "100").distancia == Distancia.LEJOS


def test_nunca_devuelve_el_resultado_correcto():
    """Si el modelo lo tuviera, la tentacion de decirlo en voz alta es el
    fracaso que el producto promete no tener."""
    campos = verify_arithmetic("135 + 241", "780").model_dump()
    assert 376 not in campos.values()
    assert "376" not in str(campos)


def test_lo_que_no_se_puede_verificar_se_dice():
    """Antes que inventar un veredicto, se declara que no se puede. El prompt
    manda no afirmar nada en ese caso."""
    assert verify_arithmetic("2 / 3", "uno").veredicto == Veredicto.REQUIERE_JUICIO
    assert verify_arithmetic("cuantas manzanas", "5").veredicto == Veredicto.REQUIERE_JUICIO
    assert verify_arithmetic("5 / 0", "0").veredicto == Veredicto.REQUIERE_JUICIO


def test_no_ejecuta_lo_que_le_manden():
    """Del otro lado hay un modelo: nada de eval. Lo que no entra en 'numero
    operador numero' no se resuelve, se rechaza."""
    for peligro in ["__import__('os').system('dir')", "1+1; print(9)", "999**999"]:
        assert verify_arithmetic(peligro, "2").veredicto == Veredicto.REQUIERE_JUICIO


def test_multiplicacion_con_las_tres_formas_de_escribirla():
    for op in ["12 x 3", "12 * 3", "12 × 3"]:
        assert verify_arithmetic(op, "36").veredicto == Veredicto.CORRECTO
