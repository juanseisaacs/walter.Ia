"""El motor de técnicas.

Lo que se prueba no es que elija: es que **abandone**. Un motor que prueba una
técnica y se queda con ella para siempre es un valor por defecto con pasos de
más — y se ve exactamente igual desde afuera mientras el niño no empeore.
"""

from __future__ import annotations

import pytest

from tutor.tecnicas import (
    GANANCIA_MINIMA,
    SESIONES_PARA_JUZGAR,
    Biblioteca,
    ErrorTecnicas,
    Evidencia,
    Tecnica,
    bloque_para_prompt,
    cambio_de_metodo,
    cargar_biblioteca,
    elegir,
    medir,
)

HAB = "mat.suma.sin_reagrupacion"


def _tecnica(id_: str, rival: str, **kw) -> Tecnica:
    return Tecnica(
        id=id_,
        nombre=id_,
        rival=rival,
        como_ensena=f"así enseña {id_}",
        senal_de_que_funciona="x",
        senal_de_que_no="y",
        evidencia=Evidencia(fuente="f", respaldo="r"),
        **kw,
    )


def _par() -> Biblioteca:
    return Biblioteca([_tecnica("a", "b"), _tecnica("b", "a")])


# ─────────────────────────────────────────────────────────────────────────────
# La biblioteca de verdad
# ─────────────────────────────────────────────────────────────────────────────


def test_la_biblioteca_del_repo_carga():
    b = cargar_biblioteca()
    assert len(b) >= 2, "sin al menos un par no hay nada que elegir"
    assert len(b) % 2 == 0, "las técnicas van de a pares: alguna quedó sin rival"


def test_toda_tecnica_declara_de_donde_sale():
    """Ninguna entra porque nos pareció buena idea."""
    for t in cargar_biblioteca():
        assert t.evidencia.fuente.strip(), f"{t.id} sin fuente"
        assert t.evidencia.respaldo.strip(), f"{t.id} sin respaldo"
        assert t.evidencia.adaptacion_es.strip(), (
            f"{t.id} no dice si su evidencia transfiere al español. Obligar a "
            f"contestarlo es lo que impide meter material traducido sin mirar."
        )


def test_ninguna_tecnica_finge_un_efecto_medido():
    """`efecto_verificado` en `true` exige haberlo contrastado con la fuente.

    Hoy ninguna lo está, y eso tiene que verse en vez de disimularse con un
    número que suene bien. Es la misma regla que el currículum con los DBA.
    """
    for t in cargar_biblioteca():
        if t.evidencia.efecto_verificado:
            pytest.fail(
                f"{t.id} declara efecto verificado. Si es cierto, este test se "
                f"actualiza citando contra qué se contrastó; si no, es humo."
            )


def test_ninguna_tecnica_puede_pisar_el_metodo_socratico():
    """LA comprobación de seguridad de este módulo.

    La técnica entra al prompt como un bloque más. Una redactada sin cuidado
    —"resuélvele el ejercicio para que vea cómo se hace"— contradiría la única
    regla que el producto promete, y el modelo obedecería a la instrucción más
    concreta. Acá se prohíben las formas de decirlo.
    """
    prohibido = [
        "dale la respuesta",
        "dile la respuesta",
        "dale el resultado",
        "resuélvele el ejercicio",
        "resuelve su ejercicio",
        "dile cuánto da",
    ]
    for t in cargar_biblioteca():
        texto = t.como_ensena.lower()
        for frase in prohibido:
            assert frase not in texto, f"{t.id} contradice el método: dice «{frase}»"


def test_el_ejemplo_resuelto_avisa_de_no_usar_los_mismos_numeros():
    """La trampa clásica: un ejemplo con SUS números es darle la respuesta."""
    t = cargar_biblioteca().obtener("modelo_resuelto")
    assert "otros números" in t.como_ensena or "otros numeros" in t.como_ensena.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Los pares tienen que cerrar
# ─────────────────────────────────────────────────────────────────────────────


def test_un_rival_colgado_no_pasa():
    """Sin rival, el motor no tiene a dónde ir cuando abandona — y eso se
    descubriría con el niño enfrente, tres sesiones después."""
    with pytest.raises(ErrorTecnicas, match="no existe"):
        Biblioteca([_tecnica("a", "fantasma")])


def test_los_pares_tienen_que_ser_mutuos():
    with pytest.raises(ErrorTecnicas, match="mutuos"):
        Biblioteca([_tecnica("a", "b"), _tecnica("b", "c"), _tecnica("c", "b")])


def test_no_se_admiten_dos_tecnicas_con_el_mismo_id():
    with pytest.raises(ErrorTecnicas, match="duplicada"):
        Biblioteca([_tecnica("a", "b"), _tecnica("a", "b")])


def test_una_biblioteca_vacia_falla_ruidosamente():
    with pytest.raises(ErrorTecnicas, match="vacía"):
        Biblioteca([])


def test_aplica_a_filtra_por_habilidad():
    b = Biblioteca(
        [_tecnica("a", "b", aplica_a=["fracciones"]), _tecnica("b", "a", aplica_a=["fracciones"])]
    )
    assert b.para("mat.fracciones.medios") != []
    assert b.para("mat.suma.llevando") == []


# ─────────────────────────────────────────────────────────────────────────────
# Medir
# ─────────────────────────────────────────────────────────────────────────────


def test_la_ganancia_es_la_suma_de_lo_que_movio():
    h = medir([("a", 0.20, 0.35), ("a", 0.35, 0.50)])
    assert h["a"].sesiones == 2
    assert h["a"].ganancia == pytest.approx(0.30)
    assert h["a"].funciono


def test_las_sesiones_sin_tecnica_no_cuentan_para_ninguna():
    """Las 62 sesiones anteriores al motor no dicen nada de ninguna técnica.

    Repartirlas entre las que existen hoy sería inventar evidencia — el pecado
    que la fase 6 dejó documentado: tratar la ausencia de dato como dato.
    """
    assert medir([(None, 0.1, 0.9), (None, 0.2, 0.8)]) == {}


def test_moverse_un_poquito_no_cuenta_como_que_funciono():
    """El dominio sube algo con cualquier práctica. Si eso contara, la primera
    técnica probada ganaría siempre y no se cambiaría nunca."""
    h = medir([("a", 0.30, 0.30 + GANANCIA_MINIMA / 2)])
    assert not h["a"].funciono


def test_una_tecnica_que_empeora_se_ve():
    h = medir([("a", 0.50, 0.40)])
    assert h["a"].ganancia < 0 and not h["a"].funciono


# ─────────────────────────────────────────────────────────────────────────────
# Elegir: el ciclo entero
# ─────────────────────────────────────────────────────────────────────────────


def test_con_un_nino_nuevo_prueba_alguna():
    d = elegir(_par(), HAB, {}, None)
    assert d.tecnica_id in {"a", "b"}
    assert d.es_nueva


def test_no_cambia_de_metodo_antes_de_juzgarlo():
    """Cambiar cada sesión es lo mismo que no tener método."""
    h = medir([("a", 0.3, 0.3)])  # una sola sesión, y mala
    d = elegir(_par(), HAB, h, "a")
    assert d.tecnica_id == "a", "la abandonó sin darle sus tres sesiones"
    assert str(SESIONES_PARA_JUZGAR) in d.porque


def test_a_las_tres_sesiones_sin_movimiento_entra_el_rival():
    """EL comportamiento que justifica el módulo entero."""
    h = medir([("a", 0.30, 0.30)] * SESIONES_PARA_JUZGAR)
    d = elegir(_par(), HAB, h, "a")

    assert d.tecnica_id == "b", "se quedó con una técnica que no movió nada"
    assert d.es_nueva
    assert "camino opuesto" in d.porque


def test_si_funciona_no_se_toca():
    h = medir([("a", 0.20, 0.45)] * SESIONES_PARA_JUZGAR)
    d = elegir(_par(), HAB, h, "a")
    assert d.tecnica_id == "a" and not d.es_nueva
    assert "funcionando" in d.porque


def test_probadas_todas_y_ninguna_buena_vuelve_a_la_menos_mala():
    """Ninguna sirvió mucho, pero quedarse con la peor no ayuda a nadie.

    Ojo con las dos ganancias: tienen que quedar las dos POR DEBAJO del umbral
    o esto no prueba lo que dice. La primera versión le puso a `b` tres
    sesiones de +0,02 —que suman 0,06 y superan el mínimo— así que la elegía
    por «le está funcionando» y el camino que se quería probar no se tocaba.
    """
    h = {}
    h.update(medir([("a", 0.30, 0.29)] * SESIONES_PARA_JUZGAR))  # −0,03: empeoró
    h.update(medir([("b", 0.30, 0.31)] * SESIONES_PARA_JUZGAR))  # +0,03: bajo el umbral
    assert not h["a"].funciono and not h["b"].funciono, "el test perdió su premisa"

    d = elegir(_par(), HAB, h, "b")
    assert d.tecnica_id == "b", "b movió más que a"
    assert "mejor anduvo" in d.porque


def test_elegir_es_deterministico():
    """Mismos datos, misma respuesta. Lo que decide algo sobre el niño se
    explica, y para explicarlo tiene que ser reproducible."""
    b, h = _par(), medir([("a", 0.3, 0.3)] * SESIONES_PARA_JUZGAR)
    assert {elegir(b, HAB, h, "a").tecnica_id for _ in range(20)} == {"b"}


def test_sin_ninguna_tecnica_aplicable_falla_claro():
    solo_lectura = [
        _tecnica("a", "b", aplica_a=["lectura"]),
        _tecnica("b", "a", aplica_a=["lectura"]),
    ]
    b = Biblioteca(solo_lectura)
    with pytest.raises(ErrorTecnicas, match="Ninguna técnica aplica"):
        elegir(b, "mat.suma.llevando", {}, None)


# ─────────────────────────────────────────────────────────────────────────────
# Lo que llega al prompt
# ─────────────────────────────────────────────────────────────────────────────


def test_al_prompt_va_el_metodo_y_nada_mas():
    """El tutor no tiene que saber que es parte de un experimento.

    Meterle el nombre de la técnica, su evidencia o su rival gasta prompt y le
    da algo de qué hablar que no le incumbe al niño.
    """
    t = _tecnica("concreto", "abstracto")
    bloque = bloque_para_prompt(t)

    assert "así enseña concreto" in bloque
    assert "concreto" not in bloque.replace("así enseña concreto", ""), "se coló el id"
    assert "abstracto" not in bloque, "se coló el rival"
    assert "evidencia" not in bloque.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Lo que se le cuenta al papá
# ─────────────────────────────────────────────────────────────────────────────


def test_sin_tecnicas_no_se_le_afirma_nada_al_papa():
    """`None`, no una frase vaga. Es la lección de la fase 6: 'no lo medimos'
    se dice, no se completa con un default que parece un dato."""
    c = cambio_de_metodo(_par(), [(None, 0.2, 0.3), (None, 0.3, 0.4)])
    assert c.actual is None and c.anterior is None and c.porque is None


def test_con_una_sola_tecnica_se_dice_cual_y_nada_de_cambios():
    c = cambio_de_metodo(_par(), [("a", 0.2, 0.3), ("a", 0.3, 0.4)])
    assert c.actual == "a"
    assert c.anterior is None
    assert c.porque is None, "no hubo cambio: no se inventa una razón"


def test_cuando_cambia_de_metodo_la_razon_llega_redactada():
    """LA frase del producto: «¿por qué cambió de método?».

    Llega hecha desde el código, no la infiere el modelo. Si dependiera del
    modelo, un reporte podría decir que cambió por un motivo que no fue.
    """
    tres_malas_y_un_cambio = [("a", 0.3, 0.3)] * 3 + [("b", 0.3, 0.4)]
    c = cambio_de_metodo(_par(), tres_malas_y_un_cambio)

    assert c.actual == "b"
    assert c.anterior == "a"
    assert c.porque and "no se movió" in c.porque
    assert "3 sesiones" in c.porque, "tiene que decir cuántas se probó antes de cambiar"


def test_se_le_habla_al_papa_con_nombres_no_con_ids():
    b = Biblioteca(
        [
            _tecnica("concreto_primero", "estructura_primero"),
            _tecnica("estructura_primero", "concreto_primero"),
        ]
    )
    # `_tecnica` pone el id como nombre; acá se comprueba que lee el NOMBRE.
    c = cambio_de_metodo(b, [("concreto_primero", 0.2, 0.3)])
    assert c.actual == b.obtener("concreto_primero").nombre


def test_una_tecnica_que_ya_no_existe_no_revienta_el_reporte():
    """Si alguien borra un YAML, las sesiones viejas siguen apuntando a él. El
    reporte del papá no puede caerse por eso."""
    c = cambio_de_metodo(_par(), [("borrada_hace_meses", 0.2, 0.3)])
    assert c.actual is None
