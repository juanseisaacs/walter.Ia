"""El instrumento que mide si la conversación fluye.

Nació sin tests, y eso costó: durante dos días el número que usábamos para
decidir si un arreglo había servido estaba **medido mal por el propio
instrumento**. Un medidor sin test es una opinión con decimales.
"""

from __future__ import annotations

from scripts.medir_fluidez import medir

MUDEZ = "[el tutor no contestó: se quedó callado]"


def test_un_turno_de_varias_lineas_es_UN_turno():
    """EL BUG QUE INFLABA LOS CORTES.

    El modelo mete saltos de línea en lo que dice —párrafos, o el hueco que
    deja un tool call a mitad de frase—. El parser leía solo la primera línea y
    descartaba el resto: 14 de 82 líneas en `ses_6c6fb58aafbb`.

    Así, un turno que termina perfectamente tres líneas más abajo se contaba
    como CORTADO, porque la primera queda a mitad de palabra. Dos de los cuatro
    "cortes del VAD" de esa sesión eran esto.
    """
    texto = (
        "tutor: ¡Listo! Vamos con las letras. A ver, déjame busco\n"
        "\n"
        " la primera... Espérame un momentico.\n"
        "nino: bueno.\n"
    )
    m = medir(texto, MUDEZ)
    assert m["turnos"] == 1, "el turno del tutor se contó más de una vez"
    assert m["cortados"] == 0, "un turno que termina bien se contó como cortado"


def test_un_turno_de_verdad_cortado_se_sigue_viendo():
    """Y el arreglo no puede tapar lo que sí está roto."""
    m = medir("tutor: ¡Dale, no\nnino: nueve.\n", MUDEZ)
    assert m["cortados"] == 1


def test_los_turnos_del_nino_cortados_se_cuentan_aparte():
    """Es la falla espejo: el VAD le cerró el turno antes de que terminara.
    «Tengo una tarea de» es un chico de 7 armando la frase (`ses_02805f3edba1`)."""
    m = medir("tutor: ¿Qué tienes?\nnino: Tengo una tarea de\n", MUDEZ)
    assert m["cortados_nino"] == 1


def test_una_respuesta_corta_no_esta_cortada():
    """"impar", "nueve", "bueno sí" no llevan punto y están completas. Sin esta
    exclusión, casi todo turno del niño contaría como corte y taparía los reales."""
    m = medir("tutor: ¿par o impar?\nnino: impar\n", MUDEZ)
    assert m["cortados_nino"] == 0


def test_contar_en_voz_alta_no_es_un_corte():
    """«1 2 3 4 5 6 7 8 9 10 11 12» es un niño contando hasta el final."""
    m = medir("tutor: ¿cuántas hay?\nnino: 1 2 3 4 5 6 7 8 9 10 11 12\n", MUDEZ)
    assert m["cortados_nino"] == 0


def test_dos_turnos_del_tutor_seguidos_son_una_retoma():
    """Se cortó y volvió a arrancar: el niño oyó la frase dos veces a medias."""
    m = medir("tutor: Uy, se me\ntutor: Te decía que nueve galletas.\n", MUDEZ)
    assert m["retomas"] == 1


def test_la_marca_de_mudez_se_cuenta_y_no_como_corte():
    """La escribe el navegador; no es algo que el tutor haya dicho a medias."""
    m = medir(f"nino: ¿estás?\ntutor: {MUDEZ}\n", MUDEZ)
    assert m["mudeces"] == 1


def test_la_frase_antes_de_una_herramienta_no_es_un_corte():
    """FALSO POSITIVO QUE MANDÓ A BUSCAR BUGS DONDE HABÍA BUEN COMPORTAMIENTO.

    El playbook le ORDENA al tutor decir una frase corta antes de usar una
    herramienta —«de una, ahí te va:»— para que el niño no oiga silencio
    mientras se resuelve. Contar eso como «se cortó» convierte el cumplimiento
    de una regla en una alarma.

    En `ses_9c5a9c436312` eso solo infló el número de 11% a 22%: la mitad de los
    «cortes» era el tutor haciendo exactamente lo que se le pide.
    """
    m = medir("tutor: De una, ahí te va:\nnino: bueno.\n", MUDEZ)
    assert m["cortados"] == 0


def test_un_corte_de_verdad_sigue_contando():
    """El arreglo no puede tapar lo que sí está roto."""
    assert medir("tutor: ¡Dale, no\nnino: nueve.\n", MUDEZ)["cortados"] == 1


def test_el_turno_del_nino_que_empieza_a_mitad_se_cuenta():
    """LA MÉTRICA QUE FALTABA, y por eso el bug duró una semana.

    Las otras tres miran dónde TERMINA la frase. Esta mira dónde empieza, que es
    donde se veía el defecto del que se quejó RBH el 25/08: «pareciera como que
    mi audio le llega tarde». El micrófono le tiraba al niño hasta medio segundo
    de audio cada vez que el tutor terminaba de hablar, por considerarlo eco —
    y ahí estaba el arranque de su respuesta.

    La señal es la minúscula inicial: el transcriptor abre en mayúscula.
    """
    m = medir("tutor: ¿Y entonces?\nnino: respuesta, si era la línea recta.\n", MUDEZ)
    assert m["descabezados"] == 1


def test_una_respuesta_suelta_en_minuscula_no_es_un_descabezado():
    """«siete», «impar»: el transcriptor las deja en minúscula por ser
    continuación, y están completas. Sin este piso, la métrica contaría como
    daño la forma normal en que un niño contesta."""
    m = medir("tutor: ¿Cuánto da?\nnino: siete\n", MUDEZ)
    assert m["descabezados"] == 0


def test_la_sordera_se_cuenta():
    """El niño habló y su voz no llegó. La espejo de la voz muda, y la que dejó
    morir en silencio a `ses_60ea3b164f17`: setenta segundos sin un solo evento
    porque nadie miraba ese lado."""
    from scripts.medir_fluidez import _marca_de_sordera

    m = medir(f"tutor: ¿cuánto da?\nnino: {_marca_de_sordera()}\n", MUDEZ)
    assert m["sordera"] == 1


def test_las_marcas_se_leen_del_codigo_de_verdad_y_no_de_un_respaldo():
    """UN INSTRUMENTO QUE SE DEGRADA EN SILENCIO MIENTE CON AUTORIDAD.

    Estas marcas las escribe el navegador y las cuenta este script: son dos
    puntas que se pueden desincronizar sin que nada avise. Había un respaldo
    —un prefijo cableado acá— y el 25/08 hizo exactamente lo que hacen los
    respaldos: al mudarse las constantes a `perillas.ts`, el regex dejó de
    encontrarlas, esto empezó a contar contra el prefijo, y siguió en verde
    porque el prefijo casualmente coincidía.

    Ahora no hay respaldo: se lee la constante completa o se cae.
    """
    from scripts.medir_fluidez import _marca_de_mudez, _marca_de_sordera, _marca_de_voz_muda

    for leer in (_marca_de_mudez, _marca_de_voz_muda, _marca_de_sordera):
        marca = leer()
        assert marca.startswith("[") and marca.endswith("]"), (
            f"{marca!r} está truncada: se está leyendo un respaldo, no la constante"
        )
