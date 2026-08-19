"""Tests del cerebro pedagógico.

Estos tests son la especificación de cómo aprende y olvida el sistema. Si uno
falla, algo cambió en la pedagogía — no en el código.
"""

from datetime import datetime, timedelta

from tutor.curriculum import cargar_grafo
from tutor.models import Nino, RegistroDominio
from tutor.pedagogy import (
    UMBRAL_DOMINIO,
    NivelPista,
    actualizar_dominio,
    adelanto,
    esta_dominada,
    grado_de_trabajo,
    habilidades_disponibles,
    habilidades_para_repasar,
    necesita_repaso,
    nivel_efectivo,
    resumen_para_prompt,
    siguiente_habilidad,
    siguiente_pista,
    va_adelantado,
    valor_evidencia,
)

AHORA = datetime(2026, 8, 17, 10, 0)


def _dominado(hid: str, cuando: datetime = AHORA, nivel: float = 0.95) -> RegistroDominio:
    return RegistroDominio(
        habilidad_id=hid, nivel=nivel, intentos=10, aciertos=9, ultima_practica=cuando
    )


def _nino(dominio: dict[str, RegistroDominio] | None = None, grado: int = 2) -> Nino:
    return Nino(id="n1", nombre="Juan", edad=7, grado=grado, dominio=dominio or {})


# ─────────────────────────────────────────────────────────────────────────────
# Evidencia: acertar con ayuda no es acertar solo
# ─────────────────────────────────────────────────────────────────────────────


def test_las_pistas_bajan_el_valor_de_un_acierto():
    """Sin esto, un niño que necesita 3 pistas cada vez figura como que domina."""
    assert valor_evidencia(True, 0) > valor_evidencia(True, 1) > valor_evidencia(True, 3)
    assert valor_evidencia(False, 0) == 0.0


def test_el_dominio_sube_con_aciertos_y_baja_con_errores():
    reg = RegistroDominio(habilidad_id="mat.suma.sin_reagrupacion")
    for _ in range(8):
        reg = actualizar_dominio(reg, acerto=True, ahora=AHORA)
    assert reg.nivel > UMBRAL_DOMINIO
    assert reg.intentos == 8

    caido = actualizar_dominio(reg, acerto=False, ahora=AHORA)
    assert caido.nivel < reg.nivel


def test_acertar_solo_llega_mas_lejos_que_acertar_con_pistas():
    solo = con_pistas = RegistroDominio(habilidad_id="mat.a")
    for _ in range(6):
        solo = actualizar_dominio(solo, acerto=True, pistas_usadas=0, ahora=AHORA)
        con_pistas = actualizar_dominio(con_pistas, acerto=True, pistas_usadas=2, ahora=AHORA)
    assert solo.nivel > con_pistas.nivel


# ─────────────────────────────────────────────────────────────────────────────
# Olvido
# ─────────────────────────────────────────────────────────────────────────────


def test_el_nivel_decae_con_el_tiempo():
    reg = _dominado("mat.a", cuando=AHORA)
    assert nivel_efectivo(reg, AHORA) == reg.nivel
    assert nivel_efectivo(reg, AHORA + timedelta(days=30)) < reg.nivel


def test_lo_bien_aprendido_se_olvida_mas_lento():
    """Vida media dependiente del dominio: consolidar sirve de algo."""
    firme = _dominado("mat.a", cuando=AHORA, nivel=0.95)
    flojo = RegistroDominio(habilidad_id="mat.b", nivel=0.35, ultima_practica=AHORA)

    luego = AHORA + timedelta(days=20)
    retencion_firme = nivel_efectivo(firme, luego) / firme.nivel
    retencion_floja = nivel_efectivo(flojo, luego) / flojo.nivel
    assert retencion_firme > retencion_floja


def test_el_decaimiento_no_muta_lo_guardado():
    """Se calcula al leer. Sin esto haría falta un job nocturno decayendo a todos."""
    reg = _dominado("mat.a", cuando=AHORA)
    nivel_efectivo(reg, AHORA + timedelta(days=60))
    assert reg.nivel == 0.95, "el registro guardado no cambia"


def test_lo_nunca_aprendido_no_necesita_repaso():
    """Repaso es para lo que se supo y se está yendo, no para lo que nunca se supo."""
    nuevo = RegistroDominio(habilidad_id="mat.a", nivel=0.2, ultima_practica=AHORA)
    assert not necesita_repaso(nuevo, AHORA + timedelta(days=90))

    sabido = _dominado("mat.b", cuando=AHORA)
    assert necesita_repaso(sabido, AHORA + timedelta(days=150))


# ── Calibración: que los números sean REALISTAS, no solo coherentes ──────────
# Estos tests existen porque una demo mostró que el olvido estaba diez veces
# más rápido de lo real: un nino "perdia" contar hasta 100 en dos semanas.
# Los tests relativos (decae, lo firme decae menos) no lo detectaron.


def test_lo_dominado_sobrevive_un_receso_escolar():
    """Dos semanas sin practicar no borran algo que el nino domina."""
    reg = _dominado("mat.numeros.conteo_hasta_100", cuando=AHORA)
    assert esta_dominada(reg, AHORA + timedelta(days=14))
    assert not necesita_repaso(reg, AHORA + timedelta(days=14))


def test_las_vacaciones_largas_desgastan_pero_no_borran():
    """El 'summer slide' es real: vuelve flojo, no en cero."""
    reg = _dominado("mat.suma.con_reagrupacion", cuando=AHORA)
    nivel = nivel_efectivo(reg, AHORA + timedelta(days=70))
    assert 0.55 < nivel < UMBRAL_DOMINIO, "conviene retocarlo, no reenseñarlo"


def test_lo_visto_una_vez_si_se_va_rapido():
    """Poca práctica y nivel bajo: eso sí se pierde en un mes."""
    flojo = RegistroDominio(habilidad_id="mat.x", nivel=0.35, intentos=2, aciertos=2,
                            ultima_practica=AHORA)
    assert nivel_efectivo(flojo, AHORA + timedelta(days=30)) < 0.30


def test_practicar_mas_consolida_mas():
    """Principio del repaso espaciado: cada práctica estira el próximo intervalo."""
    mucho = RegistroDominio(habilidad_id="mat.a", nivel=0.9, intentos=20, aciertos=18,
                            ultima_practica=AHORA)
    poco = RegistroDominio(habilidad_id="mat.b", nivel=0.9, intentos=3, aciertos=2,
                           ultima_practica=AHORA)
    luego = AHORA + timedelta(days=60)
    assert nivel_efectivo(mucho, luego) > nivel_efectivo(poco, luego)


# ─────────────────────────────────────────────────────────────────────────────
# La frontera: lo que hace posible ser adaptativo
# ─────────────────────────────────────────────────────────────────────────────


def test_sin_prerequisitos_solo_estan_las_raices():
    """Grado 1 a propósito: sin años anteriores no hay nada que presumir, así
    que acá se ve la mecánica pura del grafo. Ver
    `prerrequisito_satisfecho`."""
    g = cargar_grafo()
    disponibles = habilidades_disponibles(_nino(grado=1), g, AHORA)
    assert [h.id for h in disponibles] == ["mat.numeros.conteo_hasta_100"]


def test_dominar_algo_abre_lo_que_depende_de_ello():
    g = cargar_grafo()
    n = _nino({"mat.numeros.conteo_hasta_100": _dominado("mat.numeros.conteo_hasta_100")})
    ids = {h.id for h in habilidades_disponibles(n, g, AHORA)}
    assert "mat.numeros.valor_posicional_decenas" in ids


def test_no_se_ofrece_algo_con_prerequisitos_a_medias():
    """Suma llevando necesita suma sin llevar Y valor posicional. Con uno solo, no.

    Grado 1 para que ninguno de los dos se presuma y quede a la vista que es
    el grafo el que bloquea.
    """
    g = cargar_grafo()
    n = _nino(
        {"mat.suma.sin_reagrupacion": _dominado("mat.suma.sin_reagrupacion")}, grado=1
    )
    ids = {h.id for h in habilidades_disponibles(n, g, AHORA)}
    assert "mat.suma.con_reagrupacion" not in ids


def test_el_nino_avanza_por_donde_puede_no_en_fila_india():
    """LA PRUEBA DE QUE ES ADAPTATIVO.

    Este niño va bien en suma y no tocó resta. La frontera le ofrece seguir por
    suma sin obligarlo a esperar a la resta. Una lista lineal no puede hacer eso.
    """
    g = cargar_grafo()
    n = _nino(
        {
            "mat.numeros.conteo_hasta_100": _dominado("mat.numeros.conteo_hasta_100"),
            "mat.numeros.valor_posicional_decenas": _dominado(
                "mat.numeros.valor_posicional_decenas"
            ),
            "mat.suma.sin_reagrupacion": _dominado("mat.suma.sin_reagrupacion"),
        }
    )
    ids = {h.id for h in habilidades_disponibles(n, g, AHORA)}
    assert "mat.suma.con_reagrupacion" in ids, "puede seguir por suma"
    assert "mat.resta.sin_desagrupacion" in ids, "y la resta sigue abierta"


# ─────────────────────────────────────────────────────────────────────────────
# El planificador
# ─────────────────────────────────────────────────────────────────────────────


def test_el_planificador_es_deterministico():
    """Mismos datos, misma respuesta. Es lo que permite explicárselo a un papá."""
    g = cargar_grafo()
    n = _nino({"mat.numeros.conteo_hasta_100": _dominado("mat.numeros.conteo_hasta_100")})
    respuestas = {siguiente_habilidad(n, g, AHORA).id for _ in range(20)}
    assert len(respuestas) == 1


def test_el_repaso_gana_sobre_avanzar():
    """Lo olvidado bloquea todo lo que se apoya en ello."""
    g = cargar_grafo()
    hace_mucho = AHORA - timedelta(days=150)
    n = _nino(
        {
            "mat.numeros.conteo_hasta_100": _dominado("mat.numeros.conteo_hasta_100", hace_mucho),
            "mat.numeros.valor_posicional_decenas": _dominado(
                "mat.numeros.valor_posicional_decenas", AHORA
            ),
        }
    )
    assert habilidades_para_repasar(n, g, AHORA)
    assert siguiente_habilidad(n, g, AHORA).id == "mat.numeros.conteo_hasta_100"


# ─────────────────────────────────────────────────────────────────────────────
# SIN TECHO — el grado escolar no limita
# ─────────────────────────────────────────────────────────────────────────────


def _juan_veloz() -> Nino:
    """Un nino de 2do que ya domino todo el contenido de 1ro y 2do."""
    g = cargar_grafo()
    hasta_segundo = [h.id for h in g if h.grado_sugerido <= 2]
    return _nino({hid: _dominado(hid) for hid in hasta_segundo}, grado=2)


def test_el_grado_no_pone_techo():
    """LA CARACTERISTICA: si tiene los prerrequisitos, se lo ofrece igual.

    Un nino de 2do que ya domino 2do NO se queda esperando a marzo.
    """
    g = cargar_grafo()
    disponibles = habilidades_disponibles(_juan_veloz(), g, AHORA)
    assert disponibles, "tiene que haber a donde seguir"
    assert all(h.grado_sugerido > 2 for h in disponibles), "todo lo de 2do ya lo domina"

    proximo = siguiente_habilidad(_juan_veloz(), g, AHORA)
    assert proximo.grado_sugerido == 3, "el planificador lo deja subir de grado"


def test_mide_el_grado_real_no_el_administrativo():
    g = cargar_grafo()
    assert grado_de_trabajo(_juan_veloz(), g, AHORA) == 3
    assert grado_de_trabajo(_nino(grado=1), g, AHORA) == 1, "en 1ro no hay nada que presumir"


def test_sin_evidencia_no_se_le_dice_al_papa_que_su_hijo_va_atrasado():
    """Un nino de 2do del que no medimos nada trabaja EN 2do, no en 1ro.

    Los nodos de 1ro sin registro no son lagunas: son cosas que no miramos. Es la
    misma presuncion de grado del planificador, y sin ella el reporte le decia al
    papa que su hijo de 2do "trabaja a nivel de 1ro" sin un solo dato que lo
    sostenga.
    """
    g = cargar_grafo()
    nuevo_de_segundo = _nino(grado=2)

    assert grado_de_trabajo(nuevo_de_segundo, g, AHORA) == 2
    assert adelanto(nuevo_de_segundo, g, AHORA) == 0, "ni adelantado ni atrasado: sin medir"


def test_la_evidencia_le_gana_a_la_presuncion():
    """Si SI lo medimos y no le sale, el atraso es real y hay que reportarlo.

    Presumir no es medir: la presuncion solo cubre el silencio.
    """
    g = cargar_grafo()
    flojo = _nino(
        {
            "mat.numeros.conteo_hasta_100": RegistroDominio(
                habilidad_id="mat.numeros.conteo_hasta_100",
                nivel=0.15,
                intentos=6,
                aciertos=1,
                ultima_practica=AHORA,
            )
        },
        grado=2,
    )

    assert grado_de_trabajo(flojo, g, AHORA) == 1
    assert adelanto(flojo, g, AHORA) == -1


def test_detecta_al_nino_adelantado_para_avisarle_al_papa():
    g = cargar_grafo()
    assert adelanto(_juan_veloz(), g, AHORA) == 1
    assert va_adelantado(_juan_veloz(), g, AHORA)
    assert not va_adelantado(_nino(grado=1), g, AHORA)


def test_el_tutor_se_entera_de_que_va_adelantado():
    """Sin esto el tutor lo trataria como a un nino promedio de 2do y lo frenaria."""
    g = cargar_grafo()
    resumen = resumen_para_prompt(_juan_veloz(), g, AHORA)
    assert "ADELANTADO" in resumen
    assert "No lo frenes" in resumen


def test_subir_de_grado_no_se_penaliza_como_bajar():
    """El sesgo del planificador es asimetrico: adelante gratis, atras con costo."""
    g = cargar_grafo()
    n = _juan_veloz()
    # Le "desdominamos" algo de 1ro para que compita contra contenido de 3ro
    n.dominio["mat.numeros.comparar_ordenar"] = RegistroDominio(
        habilidad_id="mat.numeros.comparar_ordenar", nivel=0.1, ultima_practica=AHORA
    )
    ids = {h.id for h in habilidades_disponibles(n, g, AHORA)}
    assert "mat.multiplicacion.tablas" in ids, "lo de 3ro sigue disponible"


def test_un_nino_nuevo_arranca_por_la_raiz():
    """Un niño de PRIMERO sin historia sí arranca en la raíz: no cursó nada
    antes, no hay nada que presumirle.

    Para grados más altos la respuesta es otra a propósito — ver
    `test_un_nino_sin_historia_no_arranca_en_la_raiz_del_grafo`.
    """
    g = cargar_grafo()
    h = siguiente_habilidad(_nino(grado=1), g, AHORA)
    assert h.id == "mat.numeros.conteo_hasta_100"


def test_sin_nada_por_hacer_devuelve_none():
    g = cargar_grafo()
    n = _nino({h.id: _dominado(h.id) for h in g})
    assert siguiente_habilidad(n, g, AHORA) is None


# ─────────────────────────────────────────────────────────────────────────────
# La escalera socrática — el diferencial del producto
# ─────────────────────────────────────────────────────────────────────────────


def test_la_escalera_nunca_llega_a_la_respuesta():
    """LA GARANTÍA DEL PRODUCTO.

    No existe un nivel "dar la respuesta". Está codificado en el tipo: no se
    puede devolver algo que no existe.
    """
    niveles = {n.name for n in NivelPista}
    assert not any("RESPUESTA" in n for n in niveles)
    assert max(NivelPista) == NivelPista.EJEMPLO_PARALELO


def test_la_escalera_sube_de_a_poco():
    assert siguiente_pista(0) == NivelPista.PREGUNTA_ABIERTA
    assert siguiente_pista(1) == NivelPista.PREGUNTA_ORIENTADORA
    assert siguiente_pista(2) == NivelPista.PISTA_CONCEPTUAL
    assert siguiente_pista(3) == NivelPista.PISTA_CONCRETA


def test_la_escalera_tiene_techo():
    """Aunque se trabe 50 veces, el último escalón es un ejemplo PARECIDO."""
    assert siguiente_pista(50) == NivelPista.EJEMPLO_PARALELO
    assert siguiente_pista(-3) == NivelPista.PREGUNTA_ABIERTA


# ─────────────────────────────────────────────────────────────────────────────
# Resumen para el prompt
# ─────────────────────────────────────────────────────────────────────────────


def test_el_resumen_es_corto():
    """Regla de latencia: el prompt de sesión se mantiene flaco."""
    g = cargar_grafo()
    n = _nino()
    n.perfil.intereses = ["fútbol", "dinosaurios"]
    n.perfil.motivadores = ["competir con el reloj"]
    resumen = resumen_para_prompt(n, g, AHORA)
    assert len(resumen) < 700, "el resumen no puede crecer sin techo"
    assert "Juan" in resumen and "fútbol" in resumen


def test_el_resumen_avisa_cuando_el_tutor_conoce_poco_al_nino():
    """Dos avisos distintos, porque son dos situaciones distintas: no haber
    hablado NUNCA (todo vino del papá) y llevar dos o tres sesiones."""
    g = cargar_grafo()

    poco = _nino()
    poco.perfil.madurez_vinculo = 1
    assert "lo conoces poco" in resumen_para_prompt(poco, g, AHORA)


# ─────────────────────────────────────────────────────────────────────────────
# Presunción de grado — el arranque en frío
# ─────────────────────────────────────────────────────────────────────────────


def test_un_nino_sin_historia_no_arranca_en_la_raiz_del_grafo():
    """El bug del 17/08: a Juan, de 2°, que venía pidiendo sumas de dos
    dígitos, el planificador le ofrecía "contar hasta 100" porque no tenía
    registro de nada.

    Y el costo escondido era peor que ofrecer algo aburrido: con un ejercicio
    así de fácil enfrente, el modelo lo ignoraba y se inventaba los suyos. Al
    inventarlos no llamaba a la herramienta, así que nunca se registraba
    dominio, así que la próxima sesión volvía a arrancar en la raíz. El
    círculo se cerraba solo y desconectaba todo el motor pedagógico.
    """
    g = cargar_grafo()

    h = siguiente_habilidad(_nino(grado=2), g)

    assert h is not None
    assert h.grado_sugerido >= 2, f"le ofreció {h.nombre} (grado {h.grado_sugerido})"


def test_la_presuncion_no_escribe_dominio_inventado():
    """Presumir no es medir. Si guardáramos nivel en la ficha, el reporte al
    papá diría que el niño domina cosas que nunca practicó."""
    g = cargar_grafo()
    nino = _nino(grado=3)

    habilidades_disponibles(nino, g)

    assert nino.dominio == {}


def test_la_evidencia_le_gana_a_la_presuncion():
    """Si lo medimos y no le sale, el grado no lo salva: eso es justo lo que
    el grafo tiene que atrapar."""
    g = cargar_grafo()
    raiz = next(h for h in g if not h.prerequisitos)
    dependiente = next(h for h in g if raiz.id in h.prerequisitos)

    # Grado alto y sin evidencia: la presunción lo deja pasar.
    sin_evidencia = _nino(grado=5)
    assert dependiente.id in {h.id for h in habilidades_disponibles(sin_evidencia, g)}

    # Con evidencia de que NO la domina, queda bloqueado.
    con_evidencia = _nino(
        {raiz.id: RegistroDominio(habilidad_id=raiz.id, nivel=0.1, intentos=4, aciertos=0)},
        grado=5,
    )
    assert dependiente.id not in {h.id for h in habilidades_disponibles(con_evidencia, g)}


def test_no_se_presume_el_grado_que_esta_cursando():
    """Se presume lo que el colegio ya cubrió en años anteriores, no lo de
    este año. Si no, un chico de 2° saltaría a 3° sin mostrar nada — y eso
    no es "sin techo", es adivinar."""
    g = cargar_grafo()
    disponibles = {h.id for h in habilidades_disponibles(_nino(grado=2), g)}

    for h in g:
        if h.grado_sugerido < 3 or not h.prerequisitos:
            continue
        previos = [g.habilidad(p) for p in h.prerequisitos if g.existe(p)]
        if previos and all(p.grado_sugerido >= 2 for p in previos):
            assert h.id not in disponibles, f"{h.nombre} se coló sin evidencia de 2°"


def test_la_primera_vez_el_tutor_sabe_que_se_lo_conto_el_papa():
    """El tutor tiene prohibido decir "me contaron" — y en la primera sesión esa
    regla lo hacía mentir.

    Detectado en la primera prueba real del onboarding (18/08): el papá terminó
    la entrevista, el niño entró, y el tutor le dijo que lo que sabía de él se
    lo había contado él mismo. Nunca habían hablado. Si el niño responde "yo
    nunca te dije eso", el tutor queda como alguien que inventa — justo lo
    contrario de lo que la regla protegía, y contra "Verdad, siempre" de la
    Constitución.

    El código ya distinguía (`madurez_vinculo=0` al crear desde la ficha del
    papá); lo que faltaba era que la distinción llegara al prompt.
    """
    grafo = cargar_grafo()
    recien = Nino(id="n1", nombre="Juan", edad=7, grado=2)
    recien.perfil.intereses = ["dinosaurios"]
    recien.perfil.madurez_vinculo = 0

    texto = resumen_para_prompt(recien, grafo, AHORA)
    assert "PRIMERA VEZ" in texto
    assert "no digas que te lo contó él" in texto


def test_cuando_ya_se_conocen_no_le_avisa_de_la_primera_vez():
    """La advertencia tiene que desaparecer sola, o el tutor le sigue diciendo
    a un niño de la sesión diez que es la primera vez que hablan."""
    grafo = cargar_grafo()
    conocido = Nino(id="n1", nombre="Juan", edad=7, grado=2)
    conocido.perfil.intereses = ["dinosaurios"]
    conocido.perfil.madurez_vinculo = 4

    texto = resumen_para_prompt(conocido, grafo, AHORA)
    assert "PRIMERA VEZ" not in texto


def test_el_resumen_del_nino_no_vosea():
    """Va al prompt del tutor, que tiene prohibido el voseo. Ya se coló dos
    veces por acá: es texto en Python, no en el .md que todos revisan."""
    grafo = cargar_grafo()
    nino = Nino(id="n1", nombre="Juan", edad=7, grado=2)
    nino.perfil.madurez_vinculo = 1

    texto = resumen_para_prompt(nino, grafo, AHORA).lower()
    for forma in ["conocés", "preguntá", "explorá", "seguí", "tenés", "usá"]:
        assert forma not in texto, f"voseo en el resumen del niño: {forma!r}"
