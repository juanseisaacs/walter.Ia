"""Tests de los agentes offline.

Sin API key: el cliente se inyecta. Lo que se prueba no es el modelo, sino
cómo se arma la llamada y qué se hace con lo que devuelve — que es lo único
que está bajo nuestro control.
"""

from datetime import datetime, timedelta

import pytest

from tutor.curriculum import cargar_grafo
from tutor.models import (
    AnalisisSesion,
    AuditoriaCumplimiento,
    EvaluacionSeguridad,
    MetricasReporte,
    ModoSesion,
    Nino,
    NivelSeguridad,
    Observacion,
    PerfilPersonal,
    RegistroDominio,
    ReporteParaPapa,
    Sesion,
    TipoObservacion,
)
from tutor.pipeline import (
    MAX_ITEMS_PERFIL,
    ClienteFalso,
    FichaInicial,
    _SalidaAnalista,
    analizar_sesion,
    aplicar_analisis,
    calcular_metricas,
    crear_nino_desde_ficha,
    evaluar_seguridad,
    extraer_ficha,
    generar_reporte,
    siguiente_pregunta,
    verificar_reporte,
)

AHORA = datetime(2026, 8, 17, 16, 0)
GRAFO = cargar_grafo()
HAB = "mat.numeros.conteo_hasta_100"


def _nino(**kw) -> Nino:
    return Nino(id="n1", nombre="Juan", edad=7, grado=2, **kw)


def _sesion() -> Sesion:
    return Sesion(id="s1", nino_id="n1", modo=ModoSesion.GUIADO, inicio=AHORA)


def _cumplio() -> AuditoriaCumplimiento:
    return AuditoriaCumplimiento(
        regalo_la_respuesta=False, respeto_escalera_pistas=True, detecto_frustracion=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# Analista: una llamada, dos preguntas
# ─────────────────────────────────────────────────────────────────────────────


def test_el_analista_pregunta_por_el_nino_y_por_el_tutor():
    cliente = ClienteFalso(
        _SalidaAnalista(
            observaciones=[
                Observacion(habilidad_id=HAB, tipo=TipoObservacion.ACIERTO, evidencia="42")
            ],
            cumplimiento=_cumplio(),
        )
    )
    analisis = analizar_sesion(_sesion(), "tutor: hola\nnino: cuarenta y dos", cliente)

    assert analisis.sesion_id == "s1"
    assert analisis.observaciones[0].tipo == TipoObservacion.ACIERTO
    assert analisis.cumplimiento.regalo_la_respuesta is False


def test_el_analista_usa_haiku_y_recibe_la_transcripcion():
    cliente = ClienteFalso(_SalidaAnalista(cumplimiento=_cumplio()))
    analizar_sesion(_sesion(), "nino: cuarenta y dos", cliente)

    llamada = cliente.llamadas[0]
    assert "haiku" in llamada["modelo"]
    assert "cuarenta y dos" in llamada["mensaje"]
    assert "auditoría" in llamada["sistema"].lower(), "el prompt pide auditar al tutor"


# ─────────────────────────────────────────────────────────────────────────────
# Aplicar el análisis: acá se cierra el circuito adaptativo
# ─────────────────────────────────────────────────────────────────────────────


def test_un_acierto_sube_el_dominio():
    analisis = AnalisisSesion(
        sesion_id="s1",
        observaciones=[
            Observacion(habilidad_id=HAB, tipo=TipoObservacion.ACIERTO, evidencia="bien")
        ],
        cumplimiento=_cumplio(),
    )
    nuevo = aplicar_analisis(_nino(), analisis, GRAFO, AHORA)
    assert nuevo.dominio[HAB].nivel > 0
    assert nuevo.dominio[HAB].intentos == 1


def test_un_error_no_sube_el_dominio():
    previo = _nino(
        dominio={HAB: RegistroDominio(habilidad_id=HAB, nivel=0.8, ultima_practica=AHORA)}
    )
    analisis = AnalisisSesion(
        sesion_id="s1",
        observaciones=[
            Observacion(habilidad_id=HAB, tipo=TipoObservacion.ERROR, evidencia="41")
        ],
        cumplimiento=_cumplio(),
    )
    assert aplicar_analisis(previo, analisis, GRAFO, AHORA).dominio[HAB].nivel < 0.8


def test_una_habilidad_inexistente_se_ignora_sin_romper():
    analisis = AnalisisSesion(
        sesion_id="s1",
        observaciones=[
            Observacion(habilidad_id="mat.inventada", tipo=TipoObservacion.ACIERTO, evidencia="x")
        ],
        cumplimiento=_cumplio(),
    )
    assert aplicar_analisis(_nino(), analisis, GRAFO, AHORA).dominio == {}


def test_el_perfil_se_consolida_no_se_acumula():
    """REGLA CRÍTICA: si a los 6 meses la ficha tiene cien intereses, no sirve."""
    nino = _nino(perfil=PerfilPersonal(intereses=["futbol", "dinosaurios"]))
    analisis = AnalisisSesion(
        sesion_id="s1",
        perfil_sugerido=PerfilPersonal(intereses=["futbol", "espacio"]),
        cumplimiento=_cumplio(),
    )
    intereses = aplicar_analisis(nino, analisis, GRAFO, AHORA).perfil.intereses

    assert intereses.count("futbol") == 1, "no duplica lo que ya sabía"
    assert "espacio" in intereses, "suma lo nuevo"
    assert len(intereses) == 3


def test_el_perfil_tiene_techo():
    nino = _nino(perfil=PerfilPersonal(intereses=[f"cosa{i}" for i in range(5)]))
    analisis = AnalisisSesion(
        sesion_id="s1",
        perfil_sugerido=PerfilPersonal(intereses=[f"nueva{i}" for i in range(10)]),
        cumplimiento=_cumplio(),
    )
    resultado = aplicar_analisis(nino, analisis, GRAFO, AHORA)
    assert len(resultado.perfil.intereses) == MAX_ITEMS_PERFIL


def test_cada_sesion_el_tutor_conoce_mas_al_nino():
    """El pendiente que arrastrábamos desde la fase 3: madurez_vinculo sube."""
    nino = _nino()
    assert nino.perfil.madurez_vinculo == 0

    analisis = AnalisisSesion(sesion_id="s1", cumplimiento=_cumplio())
    for esperado in (1, 2, 3):
        nino = aplicar_analisis(nino, analisis, GRAFO, AHORA)
        assert nino.perfil.madurez_vinculo == esperado


def test_aplicar_no_muta_el_original():
    nino = _nino()
    analisis = AnalisisSesion(
        sesion_id="s1",
        observaciones=[
            Observacion(habilidad_id=HAB, tipo=TipoObservacion.ACIERTO, evidencia="x")
        ],
        cumplimiento=_cumplio(),
    )
    aplicar_analisis(nino, analisis, GRAFO, AHORA)
    assert nino.dominio == {}, "el original queda intacto"


# ─────────────────────────────────────────────────────────────────────────────
# Vigilante
# ─────────────────────────────────────────────────────────────────────────────


def test_el_vigilante_ve_la_ventana_entera():
    cliente = ClienteFalso(EvaluacionSeguridad(nivel=NivelSeguridad.OK))
    evaluar_seguridad(
        [("nino", "me da miedo"), ("tutor", "que pasa?"), ("nino", "mi papa")], cliente
    )
    mensaje = cliente.llamadas[0]["mensaje"]
    assert "me da miedo" in mensaje and "mi papa" in mensaje


def test_si_el_vigilante_falla_no_bloquea_pero_tampoco_miente():
    """No puede tirar la sesión abajo, ni afirmar que todo está bien sin haber mirado."""

    class Roto(ClienteFalso):
        def extraer(self, *a, **k):
            raise RuntimeError("sin red")

    resultado = evaluar_seguridad([("nino", "hola")], Roto())
    assert resultado.nivel == NivelSeguridad.ATENCION
    assert resultado.requiere_escalamiento is False
    assert resultado.categoria == "vigilante_no_disponible"


def test_el_vigilante_usa_haiku_y_un_prompt_sin_persona():
    cliente = ClienteFalso(EvaluacionSeguridad(nivel=NivelSeguridad.OK))
    evaluar_seguridad([("nino", "hola")], cliente)

    sistema = cliente.llamadas[0]["sistema"].lower()
    assert "haiku" in cliente.llamadas[0]["modelo"]
    assert "no hablás con nadie" in sistema, "contexto limpio: no es el tutor"


# ─────────────────────────────────────────────────────────────────────────────
# Reporte al papá
# ─────────────────────────────────────────────────────────────────────────────


def test_las_metricas_se_calculan_en_codigo():
    """Los hechos NO los inventa el modelo: se los pasamos calculados."""
    nino = _nino(
        dominio={
            HAB: RegistroDominio(
                habilidad_id=HAB, nivel=0.95, intentos=9, aciertos=8, ultima_practica=AHORA
            )
        }
    )
    sesion = _sesion()
    sesion.fin = AHORA + timedelta(minutes=25)

    m = calcular_metricas(
        nino, [sesion], [AnalisisSesion(sesion_id="s1", cumplimiento=_cumplio())], GRAFO, AHORA
    )
    assert m.sesiones == 1
    assert m.minutos_totales == 25
    assert m.cumplimiento_metodo == 1.0
    assert "Contar hasta 100" in m.habilidades_dominadas


def test_el_cumplimiento_baja_si_el_tutor_regalo_la_respuesta():
    fallo = AnalisisSesion(
        sesion_id="s2",
        cumplimiento=AuditoriaCumplimiento(
            regalo_la_respuesta=True, respeto_escalera_pistas=False, detecto_frustracion=True
        ),
    )
    bien = AnalisisSesion(sesion_id="s1", cumplimiento=_cumplio())
    m = calcular_metricas(_nino(), [], [bien, fallo], GRAFO, AHORA)
    assert m.cumplimiento_metodo == 0.5


def test_el_reporte_recibe_los_hechos_no_la_transcripcion():
    cliente = ClienteFalso(texto="A Juan le fue bien.")
    m = calcular_metricas(_nino(), [], [], GRAFO, AHORA)
    generar_reporte(_nino(), m, AHORA - timedelta(days=7), AHORA, cliente)

    llamada = cliente.llamadas[0]
    assert "sonnet" in llamada["modelo"], "acá sí importa la calidad de prosa"
    assert "DATOS DEL PERÍODO" in llamada["mensaje"]
    assert "no afirmás nada que no esté" in llamada["sistema"].lower()


def _reporte(texto: str, **kw) -> ReporteParaPapa:
    base = dict(
        sesiones=3, minutos_totales=75, cumplimiento_metodo=1.0,
        grado_de_trabajo=2, adelanto_grados=0,
    )
    base.update(kw)
    return ReporteParaPapa(
        nino_id="n1", desde=AHORA - timedelta(days=7), hasta=AHORA,
        metricas=MetricasReporte(**base), contenido=texto,
    )


def test_el_verificador_atrapa_un_numero_inventado():
    """Un reporte inflado es peor que ninguno: el papá habla con su hijo."""
    assert verificar_reporte(_reporte("Juan hizo 3 sesiones y resolvió 87 ejercicios."))


def test_el_verificador_deja_pasar_un_reporte_honesto():
    assert verificar_reporte(_reporte("Juan hizo 3 sesiones, 75 minutos en total.")) == []


def test_el_verificador_exige_mencionar_que_va_adelantado():
    """Es de lo más valioso que puede leer un papá. No se puede omitir."""
    problemas = verificar_reporte(
        _reporte("Juan viene bien.", adelanto_grados=1, grado_de_trabajo=3)
    )
    assert any("adelantado" in p for p in problemas)


# ─────────────────────────────────────────────────────────────────────────────
# Onboarding: la entrevista al papá
# ─────────────────────────────────────────────────────────────────────────────


def _ficha_completa(**kw) -> FichaInicial:
    base = dict(email_papa="ana@ej.com", nombre_nino="Juan", edad=7, grado=2)
    base.update(kw)
    return FichaInicial(**base)


def test_la_ficha_sabe_que_le_falta():
    """Sin los cuatro obligatorios, una alerta de seguridad no le llega a nadie."""
    vacia = FichaInicial()
    assert set(vacia.falta()) == {"email_papa", "nombre_nino", "edad", "grado"}
    assert not vacia.completa
    assert _ficha_completa().completa


def test_el_email_es_obligatorio():
    sin_mail = _ficha_completa(email_papa=None)
    assert "email_papa" in sin_mail.falta()


def test_el_extractor_recibe_la_conversacion_entera():
    cliente = ClienteFalso(_ficha_completa())
    extraer_ficha([("asesor", "Hola"), ("papa", "Se llama Juan, tiene 7")], cliente)

    mensaje = cliente.llamadas[0]["mensaje"]
    assert "Juan" in mensaje and "Hola" in mensaje
    assert "no infieras" in cliente.llamadas[0]["sistema"].lower()


def test_el_entrevistador_sabe_que_le_falta():
    cliente = ClienteFalso(texto="¿Cómo se llama tu hijo?")
    siguiente_pregunta([], FichaInicial(), cliente)

    assert "Todavía te falta" in cliente.llamadas[0]["mensaje"]
    assert "email_papa" in cliente.llamadas[0]["mensaje"]
    assert "sonnet" in cliente.llamadas[0]["modelo"], "acá la calidez es el producto"


def test_cuando_ya_tiene_todo_le_dice_que_cierre():
    """Sin esto sigue preguntando de más y la entrevista se vuelve un formulario."""
    cliente = ClienteFalso(texto="Listo, arranquemos.")
    siguiente_pregunta([("papa", "todo dicho")], _ficha_completa(), cliente)

    mensaje = cliente.llamadas[0]["mensaje"]
    assert "Cerrá la conversación" in mensaje
    assert "No preguntes nada más" in mensaje


def test_la_ficha_se_convierte_en_nino():
    ficha = _ficha_completa(
        intereses=["futbol", "dinosaurios"],
        dificultades=["se frustra rapido"],
        motivadores=["competir"],
        estilo_comunicacion="directo",
    )
    nino = crear_nino_desde_ficha(ficha, "n1")

    assert nino.nombre == "Juan"
    assert nino.email_papa == "ana@ej.com", "sin esto las alertas no llegan"
    assert nino.perfil.intereses == ["futbol", "dinosaurios"]
    assert nino.perfil.frustraciones == ["se frustra rapido"]


def test_el_nino_arranca_sin_dominio_academico():
    """Lo que el papá CREE que su hijo sabe no es dato. El dominio se mide en
    las primeras sesiones — por eso son exploratorias."""
    nino = crear_nino_desde_ficha(_ficha_completa(), "n1")
    assert nino.dominio == {}
    assert nino.perfil.madurez_vinculo == 0, "se lo contaron, no lo conoce"


def test_no_se_puede_crear_un_nino_a_medias():
    with pytest.raises(ValueError, match="Faltan datos"):
        crear_nino_desde_ficha(FichaInicial(nombre_nino="Juan"), "n1")
