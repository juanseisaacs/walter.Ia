"""Tests de los agentes offline.

Sin API key: el cliente se inyecta. Lo que se prueba no es el modelo, sino
cómo se arma la llamada y qué se hace con lo que devuelve — que es lo único
que está bajo nuestro control.
"""

import logging
import sys
from datetime import datetime, timedelta

import pytest

from tutor import config as cfg
from tutor.curriculum import cargar_grafo
from tutor.models import (
    AnalisisSesion,
    AuditoriaCumplimiento,
    Calendario,
    EstadoSesion,
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
    DestinoSenal,
    ErrorReporteInventado,
    FichaInicial,
    _atar_habilidad_unica,
    _contexto_habilidades,
    _destino,
    _SalidaAnalista,
    _SalidaReporte,
    analizar_sesion,
    aplicar_analisis,
    aplicar_retencion,
    calcular_metricas,
    clasificar_senales,
    crear_nino_desde_ficha,
    evaluar_seguridad,
    extraer_ficha,
    generar_reporte,
    generar_reporte_del_periodo,
    generar_reportes_pendientes,
    procesar_pendientes,
    procesar_sesion,
    siguiente_pregunta,
    verificar_reporte,
)
from tutor.storage import RepositorioSQLite

AHORA = datetime(2026, 8, 17, 16, 0)
GRAFO = cargar_grafo()
HAB = "mat.numeros.conteo_hasta_100"
OTRA_HAB = "mat.numeros.valor_posicional_decenas"


def _nino(**kw) -> Nino:
    return Nino(id="n1", nombre="Juan", edad=7, grado=2, **kw)


def _sesion() -> Sesion:
    return Sesion(id="s1", nino_id="n1", modo=ModoSesion.GUIADO, inicio=AHORA)


def _cliente_reporte(narrativa: str, sugerencia: str = "Contá porotos con él.") -> ClienteFalso:
    """El reporte viene en dos campos: lo que afirma y lo que propone."""
    return ClienteFalso(_SalidaReporte(narrativa=narrativa, sugerencia_para_casa=sugerencia))


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

    for llamada in cliente.llamadas:
        assert "haiku" in llamada["modelo"]
        assert "cuarenta y dos" in llamada["mensaje"]


def test_el_nino_y_el_tutor_se_miran_en_llamadas_separadas():
    """Fusionadas, las dos mitades competían y perdía la extracción: el modelo
    devolvía la auditoría impecable y `observaciones: []`. Ver `analizar_sesion`.

    Si alguien las vuelve a juntar para ahorrarse una llamada, este test avisa.
    """
    cliente = ClienteFalso(_SalidaAnalista(cumplimiento=_cumplio()))
    analizar_sesion(_sesion(), "nino: cuarenta y dos", cliente)

    assert len(cliente.llamadas) == 2, "el Analista dejó de ser dos llamadas"
    extractor, auditor = (llamada["sistema"].lower() for llamada in cliente.llamadas)

    assert "señales" in extractor, "la primera llamada no es la extracción"
    assert "auditoría" not in extractor, "la auditoría se coló en la extracción"
    assert "auditás al tutor" in auditor, "la segunda llamada no es la auditoría"


def test_el_analista_recibe_los_ids_de_habilidad_para_poder_atarlos():
    """Sin la lista de habilidades en el mensaje, el modelo devuelve
    habilidad_id=None y `aplicar_analisis` descarta la señal en silencio."""
    cliente = ClienteFalso(_SalidaAnalista(cumplimiento=_cumplio()))
    sesion = _sesion()
    sesion.habilidades_trabajadas = [HAB]
    analizar_sesion(sesion, "nino: cuarenta y dos", cliente, GRAFO)

    mensaje = cliente.llamadas[0]["mensaje"]
    assert HAB in mensaje, "el id del nodo trabajado tiene que llegar al Analista"
    assert GRAFO.habilidad(HAB).nombre.es in mensaje, "también el nombre humano"


def test_sin_grafo_el_analista_no_inyecta_contexto():
    """Compatibilidad: la firma vieja (sin grafo) sigue funcionando."""
    cliente = ClienteFalso(_SalidaAnalista(cumplimiento=_cumplio()))
    sesion = _sesion()
    sesion.habilidades_trabajadas = [HAB]
    analizar_sesion(sesion, "nino: hola", cliente)  # sin grafo

    assert "HABILIDADES TRABAJADAS" not in cliente.llamadas[0]["mensaje"]


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
# Procesar la cola: el eslabón que faltaba entre cerrar() y el dominio
# ─────────────────────────────────────────────────────────────────────────────
# Sin esto, session.cerrar() encolaba (analizada=False) pero nadie procesaba: la
# tabla `dominio` quedaba en cero para siempre. Esa era la Prioridad 2 de PENDIENTE.


def _repo_con_sesion(tmp_path, *, con_transcripcion=True) -> RepositorioSQLite:
    """Un niño y una sesión cerrada sin analizar, como la deja cerrar()."""
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.guardar_nino(_nino())
    repo.crear_sesion(_sesion())
    if con_transcripcion:
        repo.guardar_transcripcion("s1", "nino: cuarenta y dos\ntutor: ¡eso!")
    return repo


def _cliente_analista() -> ClienteFalso:
    return ClienteFalso(
        _SalidaAnalista(
            observaciones=[
                Observacion(habilidad_id=HAB, tipo=TipoObservacion.ACIERTO, evidencia="42")
            ],
            cumplimiento=_cumplio(),
        )
    )


def test_procesar_pendientes_escribe_el_dominio(tmp_path):
    """El circuito completo: sesión encolada → Analista → tabla dominio."""
    repo = _repo_con_sesion(tmp_path)
    assert repo.obtener_nino("n1").dominio == {}, "arranca sin evidencia"

    procesadas = procesar_pendientes(repo, GRAFO, _cliente_analista(), AHORA)

    assert procesadas == 1
    assert repo.obtener_nino("n1").dominio[HAB].nivel > 0, "el acierto quedó registrado"
    assert repo.sesiones_sin_analizar() == [], "la sesión salió de la cola"
    assert repo.obtener_sesion("s1").analizada is True


def test_no_procesa_dos_veces_la_misma_sesion(tmp_path):
    """IDEMPOTENCIA: el session_id es llave. Sin esto, doble conteo de dominio."""
    repo = _repo_con_sesion(tmp_path)
    procesar_pendientes(repo, GRAFO, _cliente_analista(), AHORA)
    intentos = repo.obtener_nino("n1").dominio[HAB].intentos

    reprocesadas = procesar_pendientes(repo, GRAFO, _cliente_analista(), AHORA)

    assert reprocesadas == 0, "la cola ya estaba vacía"
    assert repo.obtener_nino("n1").dominio[HAB].intentos == intentos, "no vuelve a contar"


def test_sin_transcripcion_sale_de_la_cola_sin_inventar_dominio(tmp_path):
    """Si la transcripción ya pasó la retención, la sesión no puede reprocesarse
    para siempre — pero tampoco se inventa un dominio que nadie midió."""
    repo = _repo_con_sesion(tmp_path, con_transcripcion=False)
    sesion = repo.obtener_sesion("s1")

    assert procesar_sesion(repo, GRAFO, sesion, _cliente_analista(), AHORA) is True
    assert repo.obtener_nino("n1").dominio == {}, "no escribe dominio sin evidencia"
    assert repo.sesiones_sin_analizar() == [], "igual sale de la cola"


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

    m = calcular_metricas(nino, [sesion], [_cumplio()], GRAFO, AHORA)
    assert m.sesiones == 1
    assert m.minutos_totales == 25
    assert m.cumplimiento_metodo == 1.0
    assert "Contar hasta 100" in m.habilidades_dominadas


def test_el_cumplimiento_baja_si_el_tutor_regalo_la_respuesta():
    fallo = AuditoriaCumplimiento(
        regalo_la_respuesta=True, respeto_escalera_pistas=False, detecto_frustracion=True
    )
    m = calcular_metricas(_nino(), [], [_cumplio(), fallo], GRAFO, AHORA)
    assert m.cumplimiento_metodo == 0.5


def test_sin_auditorias_las_metricas_no_afirman_que_salio_bien():
    """Nunca se midió ≠ 100%. El mismo pecado que el panel evita: un reporte que
    afirma "sostuvo el método en el 100% de las sesiones" sin haber auditado
    ninguna es exactamente la clase de dato inventado que nos hace perder al papá."""
    m = calcular_metricas(_nino(), [_sesion()], [], GRAFO, AHORA)
    assert m.cumplimiento_metodo is None


def test_al_redactor_se_le_dice_que_no_hay_medicion_del_metodo():
    """Y el dato tiene que llegarle al modelo como ausencia, no como silencio:
    un campo que falta lo completa; una instrucción explícita, no."""
    cliente = _cliente_reporte("A Juan le fue bien.")
    m = calcular_metricas(_nino(), [_sesion()], [], GRAFO, AHORA)
    generar_reporte(_nino(), m, AHORA - timedelta(days=7), AHORA, cliente)

    mensaje = cliente.llamadas[0]["mensaje"]
    assert "ninguna sesión auditada" in mensaje
    assert "100%" not in mensaje


def test_el_reporte_recibe_los_hechos_no_la_transcripcion():
    cliente = _cliente_reporte("A Juan le fue bien.")
    m = calcular_metricas(_nino(), [], [_cumplio()], GRAFO, AHORA)
    generar_reporte(_nino(), m, AHORA - timedelta(days=7), AHORA, cliente)

    llamada = cliente.llamadas[0]
    assert "sonnet" in llamada["modelo"], "acá sí importa la calidad de prosa"
    assert "DATOS DEL PERÍODO" in llamada["mensaje"]
    assert "no afirmás nada que no esté" in llamada["sistema"].lower()


def test_una_confesion_del_nino_no_viaja_al_reporte_del_papa():
    """Constitución §6.2.8: las travesuras no se reportan como eventos.

    El riesgo no es el prompt, es el canal: si alguien suma `perfil.notas` al
    contexto del reporte, todo lo que el Analista haya anotado ahí —incluida una
    confesión— le llega al papá sin que nadie lo haya decidido. Un niño al que
    le devuelven en un informe lo que contó en confianza no vuelve a contar nada,
    y ahí se pierde también lo que sí importa que cuente.
    """
    perfil = PerfilPersonal(
        intereses=["dinosaurios"],
        notas="Le confesó al tutor que copió en la prueba de sociales.",
    )
    cliente = _cliente_reporte("A Juan le fue bien.")
    m = calcular_metricas(_nino(), [], [_cumplio()], GRAFO, AHORA)
    generar_reporte(_nino(perfil=perfil), m, AHORA - timedelta(days=7), AHORA, cliente)

    mensaje = cliente.llamadas[0]["mensaje"]
    assert "dinosaurios" in mensaje, "los intereses sí van: hacen útil el reporte"
    assert "copió" not in mensaje, "una confesión del niño llegó al reporte del papá"
    assert "sociales" not in mensaje


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
    assert "Cierra la conversación" in mensaje
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


# ─────────────────────────────────────────────────────────────────────────────
# Quién dispara el reporte
# ─────────────────────────────────────────────────────────────────────────────
# `generar_reporte()` existía desde la fase 3 y NADIE lo llamaba: el panel tenía
# la sección "El resumen de la semana" y jamás aparecía.


def _repo_con_semana(tmp_path, *, auditada=True) -> RepositorioSQLite:
    """Un niño con una sesión cerrada en el período, lista para reportar."""
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.guardar_nino(_nino())
    sesion = _sesion()
    sesion.fin = AHORA + timedelta(minutes=25)
    repo.crear_sesion(sesion)
    repo.actualizar_sesion(sesion)
    if auditada:
        repo.guardar_auditoria("s1", _cumplio())
    return repo


def test_el_reporte_semanal_se_genera_y_queda_guardado(tmp_path):
    """Lo que faltaba de punta a punta: el panel ya puede mostrarlo."""
    repo = _repo_con_semana(tmp_path)
    cliente = _cliente_reporte("Juan trabajó con ganas esta semana.")

    reporte = generar_reporte_del_periodo(repo, GRAFO, "n1", cliente, AHORA + timedelta(hours=1))

    assert reporte is not None
    assert repo.ultimo_reporte("n1").contenido == "Juan trabajó con ganas esta semana."


def test_no_se_le_mandan_dos_reportes_al_papa_en_la_misma_semana(tmp_path):
    """IDEMPOTENCIA: la tarea corre todos los días; el reporte es semanal."""
    repo = _repo_con_semana(tmp_path)
    ahora = AHORA + timedelta(hours=1)
    generar_reporte_del_periodo(repo, GRAFO, "n1", _cliente_reporte("El primero."), ahora)

    segundo = generar_reporte_del_periodo(
        repo, GRAFO, "n1", _cliente_reporte("El segundo."), ahora + timedelta(days=1)
    )

    assert segundo is None
    assert repo.ultimo_reporte("n1").contenido == "El primero."


def test_pasada_la_semana_vuelve_a_reportar(tmp_path):
    repo = _repo_con_semana(tmp_path)
    ahora = AHORA + timedelta(hours=1)
    generar_reporte_del_periodo(repo, GRAFO, "n1", _cliente_reporte("El primero."), ahora)

    # Ocho días después hay otra sesión y el período ya venció.
    tarde = ahora + timedelta(days=8)
    otra = Sesion(id="s2", nino_id="n1", modo=ModoSesion.GUIADO, inicio=tarde - timedelta(hours=1))
    otra.fin = tarde
    repo.crear_sesion(otra)
    repo.guardar_auditoria("s2", _cumplio())

    assert generar_reporte_del_periodo(
        repo, GRAFO, "n1", _cliente_reporte("El segundo."), tarde
    ) is not None


def test_una_semana_sin_sesiones_no_genera_reporte(tmp_path):
    """No hay nada que contar. Pedirle a un modelo que escriba sobre la nada es
    pedirle que invente, y además gasta tokens en no decir nada."""
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.guardar_nino(_nino())
    cliente = _cliente_reporte("Juan estuvo brillante.")

    assert generar_reporte_del_periodo(repo, GRAFO, "n1", cliente, AHORA) is None
    assert cliente.llamadas == [], "ni siquiera se llamó al modelo"


# ─────────────────────────────────────────────────────────────────────────────
# Retención
# ─────────────────────────────────────────────────────────────────────────────
# `borrar_transcripciones_anteriores_a` tenía seis tests propios y ningún
# llamador fuera de una demo: la regla dura de datos de menores no se ejecutaba
# nunca. Estos tests cubren la función Y el hecho de que alguien la llame.


def test_la_retencion_borra_lo_vencido_y_respeta_lo_reciente(tmp_path):
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.guardar_nino(_nino())
    edades = [("vieja", AHORA - timedelta(days=40)), ("nueva", AHORA - timedelta(days=2))]
    for sid, cuando in edades:
        s = Sesion(id=sid, nino_id="n1", modo=ModoSesion.GUIADO, inicio=cuando, analizada=True)
        repo.crear_sesion(s)
        repo.actualizar_sesion(s)
        repo.guardar_transcripcion(sid, "nino: hola")

    r = aplicar_retencion(repo, ahora=AHORA, dias=30)

    assert r.borradas == 1
    assert repo.obtener_transcripcion("vieja") is None
    assert repo.obtener_transcripcion("nueva") is not None, "lo de esta semana no se toca"


def test_el_modo_seco_no_borra_nada(tmp_path):
    """Poder mirar qué se va a perder antes de perderlo."""
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.guardar_nino(_nino())
    repo.crear_sesion(Sesion(id="s1", nino_id="n1", modo=ModoSesion.GUIADO,
                             inicio=AHORA - timedelta(days=40)))
    repo.guardar_transcripcion("s1", "nino: hola")

    r = aplicar_retencion(repo, ahora=AHORA, dias=30, seco=True)

    assert r.borradas == 1, "reporta lo que borraría"
    assert repo.obtener_transcripcion("s1") is not None, "pero no lo borró"


def test_avisa_cuando_se_pierde_una_sesion_sin_analizar(tmp_path, caplog):
    """La retención manda —es legal, no una preferencia— pero perder el trabajo
    de un niño antes de leerlo no puede pasar en silencio."""
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.guardar_nino(_nino())
    repo.crear_sesion(Sesion(id="s1", nino_id="n1", modo=ModoSesion.GUIADO,
                             inicio=AHORA - timedelta(days=40)))  # analizada=False
    repo.guardar_transcripcion("s1", "nino: cuarenta y dos")

    with caplog.at_level(logging.WARNING, logger="tutor.pipeline"):
        r = aplicar_retencion(repo, ahora=AHORA, dias=30)

    assert r.sin_analizar == ("s1",)
    assert "sin haberse analizado" in caplog.text
    assert "s1" in r.diagnostico()


def test_retencion_corre_de_verdad(tmp_path, monkeypatch, capsys):
    """EL test de este bloque: que el script la llame.

    Entra por `main()`, que es por donde entra quien corre la tarea. Un test de
    la función sola no prueba que la función se use — que es exactamente cómo
    esto se quedó sin llamador durante fases (`BITACORA.md`, 21/08).
    """
    import scripts.procesar_pendientes as script

    monkeypatch.setattr(cfg, "DB", tmp_path / "t.db")
    monkeypatch.setattr(cfg, "DATOS", tmp_path)
    monkeypatch.setattr(sys, "argv", ["procesar_pendientes"])

    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.guardar_nino(_nino())
    vieja = Sesion(id="s1", nino_id="n1", modo=ModoSesion.GUIADO,
                   inicio=datetime.now() - timedelta(days=999), analizada=True)
    repo.crear_sesion(vieja)
    repo.actualizar_sesion(vieja)  # cola vacía: la retención igual tiene que correr
    repo.guardar_transcripcion("s1", "nino: hola")

    assert script.main() == 0
    assert repo.obtener_transcripcion("s1") is None, (
        "la transcripción venció hace 969 días y el script la dejó ahí: "
        "la retención volvió a quedarse sin llamador"
    )
    assert "RETENCIÓN" in capsys.readouterr().out


def test_un_reporte_que_inventa_un_numero_no_llega_al_papa(tmp_path):
    """La verificación en código ya existía; ahora tiene quién la haga cumplir.
    Un reporte inflado es peor que ninguno: el papá habla con su hijo y se da
    cuenta."""
    repo = _repo_con_semana(tmp_path)
    cliente = _cliente_reporte("Juan resolvió 47 ejercicios en 9 sesiones.")

    with pytest.raises(ErrorReporteInventado) as e:
        generar_reporte_del_periodo(repo, GRAFO, "n1", cliente, AHORA + timedelta(hours=1))

    assert "47" in str(e.value)
    assert repo.ultimo_reporte("n1") is None, "no se guardó nada"


def test_el_cumplimiento_del_reporte_sale_de_las_auditorias_persistidas(tmp_path):
    """Una semana después la transcripción puede estar borrada. El veredicto no:
    por eso el reporte se apoya en la auditoría y no en un análisis nuevo."""
    repo = _repo_con_semana(tmp_path)
    repo.borrar_transcripciones_anteriores_a(AHORA + timedelta(days=1))

    reporte = generar_reporte_del_periodo(
        repo, GRAFO, "n1", _cliente_reporte("Bien."), AHORA + timedelta(hours=1)
    )

    assert reporte.metricas.cumplimiento_metodo == 1.0


def test_sin_auditar_el_reporte_no_afirma_nada_del_metodo(tmp_path):
    repo = _repo_con_semana(tmp_path, auditada=False)

    reporte = generar_reporte_del_periodo(
        repo, GRAFO, "n1", _cliente_reporte("Bien."), AHORA + timedelta(hours=1)
    )

    assert reporte.metricas.cumplimiento_metodo is None


def test_un_reporte_que_miente_no_tumba_los_de_los_demas_ninos(tmp_path):
    """La tarea recorre a toda la población: el que falla se aparta y se
    devuelve — no se traga, pero tampoco frena al resto."""
    repo = _repo_con_semana(tmp_path)
    repo.guardar_nino(Nino(id="n2", nombre="Sofia", edad=8, grado=3))
    otra = Sesion(id="s2", nino_id="n2", modo=ModoSesion.GUIADO, inicio=AHORA)
    otra.fin = AHORA + timedelta(minutes=20)
    repo.crear_sesion(otra)

    class Mentiroso(ClienteFalso):
        def extraer(self, modelo, sistema, mensaje, formato, temperatura=0.0):
            narrativa = "Sofia hizo 91 ejercicios." if "Sofia" in mensaje else "Juan avanzó bien."
            return _SalidaReporte(narrativa=narrativa, sugerencia_para_casa="Jueguen a contar.")

    generados, fallidos = generar_reportes_pendientes(
        repo, GRAFO, Mentiroso(), AHORA + timedelta(hours=1)
    )

    assert [r.nino_id for r in generados] == ["n1"]
    assert [f.nino_id for f in fallidos] == ["n2"]


# ─────────────────────────────────────────────────────────────────────────────
# La frontera con el modelo
# ─────────────────────────────────────────────────────────────────────────────


def test_la_extraccion_no_deja_la_temperatura_al_azar():
    """Extraer no es escribir. Con la temperatura por defecto (1.0), la misma
    transcripción daba 0 observaciones en una corrida y 5 en la siguiente: un
    eval en rojo y la sesión del niño sin registrar, según el humor del muestreo.
    """
    from tutor.pipeline import TEMPERATURA_EXTRACCION, ClienteAnthropic

    capturado = {}

    class _Bloque:
        type = "tool_use"
        input = {
            "regalo_la_respuesta": False,
            "respeto_escalera_pistas": True,
            "detecto_frustracion": False,
        }

    class _Messages:
        def create(self, **kw):
            capturado.update(kw)
            return type("R", (), {"content": [_Bloque()], "stop_reason": "tool_use"})()

    cliente = ClienteAnthropic(api_key="test")
    cliente._cliente = type("C", (), {"messages": _Messages()})()

    cliente.extraer("modelo-x", "sistema", "mensaje", AuditoriaCumplimiento)

    assert capturado["temperature"] == TEMPERATURA_EXTRACCION == 0.0


def test_la_salida_estructurada_va_por_tool_use_y_no_por_parse():
    """MEDIDO el 20/08 con `ses_47dfebd9aa43`, mismo modelo y mismo prompt:

    · `messages.parse(output_format=…)` → 38.642 chars, cortada por `max_tokens`.
      JSON partido a la mitad de una cadena, Pydantic lo rechaza ENTERO y la
      sesión del niño queda sin registrar.
    · tool use con `tool_choice` forzado → 2.813 chars, 1.199 tokens, y tres
      corridas idénticas a temperatura 0.

    Con el esquema como contrato de la herramienta el modelo lo llena y para. Si
    alguien vuelve a `parse` porque "es más corto", esto se cae — y con razón:
    el camino corto perdía sesiones enteras en silencio.
    """
    from tutor.pipeline import ClienteAnthropic

    capturado = {}

    class _Bloque:
        type = "tool_use"
        input = {
            "regalo_la_respuesta": False,
            "respeto_escalera_pistas": True,
            "detecto_frustracion": False,
        }

    class _Messages:
        def create(self, **kw):
            capturado.update(kw)
            return type("R", (), {"content": [_Bloque()], "stop_reason": "tool_use"})()

        def parse(self, **kw):
            raise AssertionError("la extracción volvió a `parse`: pierde sesiones enteras")

    cliente = ClienteAnthropic(api_key="test")
    cliente._cliente = type("C", (), {"messages": _Messages()})()
    cliente.extraer("modelo-x", "sistema", "mensaje", AuditoriaCumplimiento)

    assert capturado["tool_choice"]["type"] == "tool", "hay que forzar la herramienta"
    assert capturado["tools"][0]["input_schema"]["properties"].keys() >= {
        "regalo_la_respuesta"
    }, "el esquema tiene que viajar como contrato de la herramienta"


def test_los_numeros_de_la_sugerencia_no_tumban_el_reporte(tmp_path):
    """El caso real que rompió: el modelo propuso "este dinosaurio pesaba 350
    kilos" y la verificación descartó el reporte entero. 350 no es un dato sobre
    el niño — es del juego. El papá se quedaba sin nada por una frase que no
    afirmaba nada sobre su hijo.
    """
    repo = _repo_con_semana(tmp_path)
    cliente = _cliente_reporte(
        "Juan trabajó con centenas.",
        sugerencia="Pedile que ordene 350, 500 y 275 kilos de dinosaurios.",
    )

    reporte = generar_reporte_del_periodo(repo, GRAFO, "n1", cliente, AHORA + timedelta(hours=1))

    assert reporte is not None
    assert "350" in reporte.sugerencia
    assert verificar_reporte(reporte) == [], "la sugerencia no se verifica"


def test_la_narrativa_sigue_verificandose_igual_de_estricto(tmp_path):
    """Separar los campos no aflojó nada donde importa: un número inventado en lo
    que se AFIRMA sobre el niño sigue tumbando el reporte."""
    repo = _repo_con_semana(tmp_path)
    cliente = _cliente_reporte("Juan hizo 47 ejercicios.", sugerencia="Contá con él.")

    with pytest.raises(ErrorReporteInventado):
        generar_reporte_del_periodo(repo, GRAFO, "n1", cliente, AHORA + timedelta(hours=1))


def test_al_redactor_se_le_explica_que_la_sugerencia_es_libre():
    """El prompt es dato: si no dice esto, el modelo se autocensura y propone
    actividades sin números — que en matemáticas no sirven para nada."""
    from tutor.voice import cargar_prompt

    prompt = cargar_prompt("parent_companion")
    assert "sugerencia_para_casa" in prompt
    assert "narrativa" in prompt


def test_si_el_modelo_devuelve_basura_los_demas_ninos_igual_reciben(tmp_path):
    """Pasó de verdad: `messages.parse` recibió una respuesta vacía y la tarea
    entera murió a mitad de camino. Una falla del modelo con un niño no puede
    dejar sin reporte a los demás — y tiene que quedar dicha, no tragada."""
    repo = _repo_con_semana(tmp_path)
    repo.guardar_nino(Nino(id="n2", nombre="Sofia", edad=8, grado=3))
    otra = Sesion(id="s2", nino_id="n2", modo=ModoSesion.GUIADO, inicio=AHORA)
    otra.fin = AHORA + timedelta(minutes=20)
    repo.crear_sesion(otra)

    class SeCaeConSofia(ClienteFalso):
        def extraer(self, modelo, sistema, mensaje, formato, temperatura=0.0):
            if "Sofia" in mensaje:
                raise RuntimeError("el modelo no devolvió JSON válido")
            return _SalidaReporte(narrativa="Juan avanzó bien.", sugerencia_para_casa="Contá.")

    generados, fallidos = generar_reportes_pendientes(
        repo, GRAFO, SeCaeConSofia(), AHORA + timedelta(hours=1)
    )

    assert [r.nino_id for r in generados] == ["n1"]
    assert fallidos[0].nino_id == "n2"
    assert "JSON" in fallidos[0].motivo


def test_el_entrevistador_del_papa_no_vosea():
    """El modelo imita el registro de sus instrucciones — es la lección que ya
    costó cara en el prompt del tutor.

    Este archivo estuvo entero en voseo argentino ("Sos", "Tenés", "Escuchá",
    "Decile") hasta el 18/08, y de ahí salía el registro con el que le hablaba a
    un papá colombiano. Cuarta vez que el voseo se cuela por un lugar que nadie
    revisa.
    """
    from tutor.pipeline import cargar_prompt

    # Se salta la línea que las VETA, que obviamente las nombra. Mismo cuidado
    # que en el test del bloque del modo pedido: buscar a ciegas da un falso
    # positivo justo sobre la regla que uno quiere proteger.
    # Se saltan las líneas que las VETAN, que obviamente las nombran: la línea
    # de la regla y la tabla de ejemplos (empieza con ✗). Buscar a ciegas da un
    # falso positivo justo sobre la regla que uno quiere proteger — ya pasó con
    # el test del modo pedido.
    lineas = [
        linea
        for linea in cargar_prompt("parent_interview").lower().splitlines()
        if "voseo" not in linea and not linea.strip().startswith("> ✗")
    ]
    guion = chr(10).join(lineas)
    for forma in ["sos ", "tenés", "conversás", "escuchá", "preguntá", "decile", "cerrá"]:
        assert forma not in guion, f"voseo en el entrevistador del papá: {forma!r}"


def test_el_entrevistador_no_pide_datos_medicos():
    """Pedir diagnósticos cambia lo que somos, y no hace falta para empezar.

    Si el papá los trae por su cuenta se reciben sin repreguntar; lo que no se
    hace es ir a buscarlos.
    """
    from tutor.pipeline import cargar_prompt

    guion = cargar_prompt("parent_interview")
    assert "Diagnósticos, terapias o condiciones médicas" in guion
    assert "Lo que NO preguntas" in guion


# ─────────────────────────────────────────────────────────────────────────────
# El 20% institucional: del Analista a la ficha
# ─────────────────────────────────────────────────────────────────────────────


def test_lo_que_el_nino_cuenta_del_colegio_entra_a_la_ficha():
    """La ley obliga al 80% nacional; el 20% lo define cada colegio en su PEI.

    El grafo nace sabiendo el 80%. El 20% solo se aprende oyendo al niño, sesión
    a sesión, y es lo que hace que el tutor acompañe la clase real en vez de
    adivinar el temario.
    """
    nino = _nino()
    analisis = AnalisisSesion(
        sesion_id="s1",
        perfil_sugerido=PerfilPersonal(
            contexto_escolar="La profe Marcela está dando los mapas de Colombia."
        ),
        cumplimiento=_cumplio(),
    )
    resultado = aplicar_analisis(nino, analisis, GRAFO, AHORA)
    assert resultado.perfil.contexto_escolar.startswith("La profe Marcela")


def test_el_colegio_se_reemplaza_no_se_apila():
    """Misma regla que el resto del perfil: consolidar, no acumular. Es UNA
    línea con el estado de hoy, no el historial de lo que fue viendo."""
    nino = _nino(perfil=PerfilPersonal(contexto_escolar="Estaban en sumas."))
    analisis = AnalisisSesion(
        sesion_id="s1",
        perfil_sugerido=PerfilPersonal(contexto_escolar="Ahora van en fracciones."),
        cumplimiento=_cumplio(),
    )
    resultado = aplicar_analisis(nino, analisis, GRAFO, AHORA)
    assert resultado.perfil.contexto_escolar == "Ahora van en fracciones."


def test_una_sesion_sin_colegio_no_borra_lo_que_ya_sabiamos():
    """El niño no habla del colegio todos los días. Si el Analista devuelve
    vacío, eso significa "no salió el tema", no "cambió de colegio"."""
    nino = _nino(perfil=PerfilPersonal(contexto_escolar="Estaban en fracciones."))
    analisis = AnalisisSesion(
        sesion_id="s1", perfil_sugerido=PerfilPersonal(), cumplimiento=_cumplio()
    )
    resultado = aplicar_analisis(nino, analisis, GRAFO, AHORA)
    assert resultado.perfil.contexto_escolar == "Estaban en fracciones."


def test_el_calendario_del_colegio_llega_de_la_entrevista_a_la_ficha():
    """En agosto un niño de calendario A lleva medio año y uno de B arranca.

    El campo existe en `Nino` desde el 19/08, pero un campo que nada puede
    escribir nunca sale de su default: el cableado tiene que llegar hasta acá,
    o el calendario B no existe en la práctica.
    """
    ficha = FichaInicial(
        email_papa="papa@ejemplo.com", nombre_nino="Sofía", edad=8, grado=3,
        calendario=Calendario.B,
    )
    assert crear_nino_desde_ficha(ficha, "n9").calendario == Calendario.B


def test_sin_calendario_en_la_entrevista_se_asume_el_de_la_mayoria():
    """No es obligatorio a propósito: bloquear el alta por un dato que muchos
    papás no saben de memoria cuesta más de lo que arregla. El default es A,
    que es el de casi todos los colegios del país."""
    ficha = FichaInicial(email_papa="papa@ejemplo.com", nombre_nino="Juan", edad=7, grado=2)
    assert "calendario" not in ficha.falta(), "no puede bloquear el onboarding"
    assert crear_nino_desde_ficha(ficha, "n8").calendario == Calendario.A


# ─────────────────────────────────────────────────────────────────────────────
# Cuando el niño trae su tarea: la sesión no pasa por el banco
# ─────────────────────────────────────────────────────────────────────────────


def _sesion_sin_banco() -> Sesion:
    return Sesion(
        id="s_tarea", nino_id="n1", modo=ModoSesion.GUIADO,
        estado=EstadoSesion.COMPLETADA, inicio=AHORA, habilidades_trabajadas=[],
    )


def test_sin_banco_el_analista_igual_recibe_candidatos_reales():
    """EL BUG DEL 19/08, medido en `ses_60f5ee744aca`.

    El niño llegó con su tarea, el tutor la trabajó sin pedir ejercicios y
    `habilidades_trabajadas` quedó vacío. Esta función devolvía cadena vacía: el
    modelo se quedaba sin una sola opción real y **no devolvía None — inventaba
    un id plausible**. El niño resolvió 56+38 llevando una decena y quedó
    grabado como `mat.suma.sin_reagrupacion`, justo lo que no hizo. Como el id
    existe en el grafo, `aplicar_analisis` lo aceptó y entró a su ficha.

    Elegir entre trece opciones con nombre es leer la transcripción. Inventar un
    id de la nada es otra cosa, y el reporte al papá no distingue.
    """
    contexto = _contexto_habilidades(_sesion_sin_banco(), GRAFO)

    assert contexto, "sin candidatos el modelo inventa el id en vez de dejarlo en null"
    for habilidad in GRAFO:
        assert habilidad.id in contexto, f"falta el candidato {habilidad.id}"
    assert "null" in contexto, "tiene que quedar permitido no atribuir"


def test_con_banco_solo_se_ofrecen_las_habilidades_de_la_sesion():
    """La lista completa es el plan B. Cuando el banco sí entregó, ofrecer los
    trece nodos volvería a abrir la puerta a atribuir lo que no se trabajó."""
    sesion = _sesion_sin_banco()
    sesion.habilidades_trabajadas = ["mat.suma.con_reagrupacion"]

    contexto = _contexto_habilidades(sesion, GRAFO)
    assert "mat.suma.con_reagrupacion" in contexto
    assert "mat.fracciones.medios_tercios_cuartos" not in contexto


def test_sin_grafo_no_hay_contexto():
    """El Analista corre también sin grafo (tests, scripts sueltos)."""
    assert _contexto_habilidades(_sesion_sin_banco(), None) == ""


def test_lo_que_el_nino_cuenta_de_si_mismo_no_se_pierde():
    """PASÓ DOS VECES: `ses_afce08f934ea` y `ses_8c8334cfc756`.

        nino: "Walter, ¿cuál es mi color favorito?"
        ...
        nino: "Pero si te lo dije en la sesión pasada."

    No había dónde ponerlo. `intereses` son temas que le gustan y la lista se
    llena de observaciones pedagógicas; `notas` es un párrafo, y un párrafo se
    resume — un dato concreto se pierde en el resumen.

    Un dato no se sintetiza: o se recuerda o no se recuerda. Y es la memoria
    longitudinal —criterio #3— fallando justo donde el niño la nota.
    """
    nino = _nino()
    analisis = AnalisisSesion(
        sesion_id="s1",
        perfil_sugerido=PerfilPersonal(
            datos_suyos=["color favorito: rojo", "tiene un perro que se llama Kira"]
        ),
        cumplimiento=_cumplio(),
    )
    resultado = aplicar_analisis(nino, analisis, GRAFO, AHORA)
    assert "color favorito: rojo" in resultado.perfil.datos_suyos


def test_los_datos_del_nino_se_consolidan_como_el_resto():
    """Misma regla que los intereses: no se acumulan cien líneas."""
    nino = _nino(perfil=PerfilPersonal(datos_suyos=["color favorito: rojo"]))
    analisis = AnalisisSesion(
        sesion_id="s1",
        perfil_sugerido=PerfilPersonal(datos_suyos=["color favorito: rojo", "le dicen Pipe"]),
        cumplimiento=_cumplio(),
    )
    datos = aplicar_analisis(nino, analisis, GRAFO, AHORA).perfil.datos_suyos
    assert datos.count("color favorito: rojo") == 1
    assert "le dicen Pipe" in datos


# ─────────────────────────────────────────────────────────────────────────────
# Que el descarte deje rastro
# ─────────────────────────────────────────────────────────────────────────────
# El fallo que motivó esto no era que se descartaran señales —a veces hay que
# descartarlas— sino que se descartaran SIN QUE NADIE PUDIERA ENTERARSE. Estos
# tests prueban dos cosas distintas: que el conteo es fiel a lo que el código
# hace, y que la pérdida sale por algún lado.


def _obs(tipo, habilidad_id=HAB) -> Observacion:
    return Observacion(habilidad_id=habilidad_id, tipo=tipo, evidencia="x")


def _analisis(*observaciones) -> AnalisisSesion:
    return AnalisisSesion(
        sesion_id="s1", observaciones=list(observaciones), cumplimiento=_cumplio()
    )


def test_una_senal_academica_sin_id_se_cuenta_como_perdida():
    senales = clasificar_senales(_analisis(_obs(TipoObservacion.ACIERTO, None)), GRAFO)

    assert senales.perdidas == 1
    assert senales.sin_id == 1
    assert senales.aplicadas == 0
    assert "sin habilidad_id" in senales.diagnostico()


def test_un_id_inventado_se_cuenta_y_ademas_se_nombra():
    """Saber que se perdió una no alcanza: hay que ver QUÉ id devolvió el
    modelo, o no hay cómo corregir el prompt que lo produjo."""
    senales = clasificar_senales(_analisis(_obs(TipoObservacion.ERROR, "mat.inventada")), GRAFO)

    assert senales.perdidas == 1
    assert senales.ids_desconocidos == ("mat.inventada",)
    assert "mat.inventada" in senales.diagnostico()


def test_lo_que_va_al_perfil_no_es_una_perdida():
    """Un interés no lleva habilidad_id por diseño. Contarlo como perdido sería
    un falso positivo, y un aviso que grita siempre no lo mira nadie."""
    senales = clasificar_senales(
        _analisis(_obs(TipoObservacion.INTERES, None), _obs(TipoObservacion.FRUSTRACION, None)),
        GRAFO,
    )

    assert senales.perdidas == 0
    assert senales.perfil == 2


def test_una_pista_con_id_valido_entro_no_se_perdio():
    """`pista_necesaria` no mueve el nivel por sí sola, pero se cuenta dentro
    del cálculo. Entró: marcarla como perdida sería mentir al revés."""
    senales = clasificar_senales(_analisis(_obs(TipoObservacion.PISTA_NECESARIA)), GRAFO)

    assert senales.perdidas == 0
    assert senales.pistas == 1


@pytest.mark.parametrize("tipo", list(TipoObservacion))
def test_toda_observacion_tiene_un_destino_con_nombre(tipo):
    """Recorrer las ramas, no un caso de ejemplo (lección de la fase 8).

    Si mañana se agrega un `TipoObservacion`, este test obliga a decidir dónde
    cae en vez de dejarlo caer en el `continue` mudo de siempre.
    """
    assert _destino(_obs(tipo), GRAFO) in set(DestinoSenal)
    assert _destino(_obs(tipo, None), GRAFO) in set(DestinoSenal)


def test_el_conteo_no_puede_contradecir_lo_que_el_codigo_hizo():
    """EL test de esta tanda: `clasificar_senales` cuenta con el MISMO predicado
    con el que `aplicar_analisis` decide. Si alguien duplica la regla en vez de
    reusarla, las dos lecturas se separan sin avisar — que es exactamente cómo
    `verificable_en_codigo` vivió mal dos fases (lección de la fase 4)."""
    analisis = _analisis(
        _obs(TipoObservacion.ACIERTO),  # entra
        _obs(TipoObservacion.ERROR),  # entra (mismo nodo)
        _obs(TipoObservacion.ACIERTO, None),  # se pierde
        _obs(TipoObservacion.DOMINIO, "mat.inventada"),  # se pierde
        _obs(TipoObservacion.INTERES, None),  # al perfil
    )
    senales = clasificar_senales(analisis, GRAFO)
    resultado = aplicar_analisis(_nino(), analisis, GRAFO, AHORA)

    assert senales.dominio == 2, "dos señales movieron dominio"
    assert senales.perdidas == 2
    assert resultado.dominio[HAB].intentos == senales.dominio, (
        "el conteo tiene que coincidir con los intentos que de verdad se escribieron"
    )


def test_la_perdida_de_senales_sale_por_el_log(tmp_path, caplog):
    """Antes era un `continue` mudo: el niño practicaba, el dominio no subía, y
    no había ni excepción ni contador ni línea donde enterarse."""
    repo = _repo_con_sesion(tmp_path)
    cliente = ClienteFalso(
        _SalidaAnalista(
            observaciones=[Observacion(tipo=TipoObservacion.ACIERTO, evidencia="42")],
            cumplimiento=_cumplio(),
        )
    )
    sesion = repo.obtener_sesion("s1")
    sesion.habilidades_trabajadas = [HAB, OTRA_HAB]  # dos: el atado no aplica
    repo.actualizar_sesion(sesion)

    with caplog.at_level(logging.WARNING, logger="tutor.pipeline"):
        procesar_sesion(repo, GRAFO, repo.obtener_sesion("s1"), cliente, AHORA)

    assert "sin habilidad_id" in caplog.text
    assert "s1" in caplog.text


def test_la_sesion_que_cierra_sin_un_solo_nodo_avisa(tmp_path, caplog):
    """El caso de `ses_cdb0b7fae50f`: nueve turnos escribiendo la w, cero filas
    de dominio, 16.573 tokens que el papá no ve en ningún reporte."""
    repo = _repo_con_sesion(tmp_path)
    sesion = repo.obtener_sesion("s1")
    sesion.tokens_consumidos = 16_573
    sesion.habilidades_trabajadas = []
    repo.actualizar_sesion(sesion)

    with caplog.at_level(logging.WARNING, logger="tutor.pipeline"):
        procesar_sesion(repo, GRAFO, repo.obtener_sesion("s1"), _cliente_analista(), AHORA)

    assert "sin habilidades trabajadas" in caplog.text
    assert "16573" in caplog.text


def test_la_sesion_sin_insumo_tampoco_se_va_callada(tmp_path, caplog):
    """Sale de la cola —eso sigue estando bien— pero deja dicho por qué."""
    repo = _repo_con_sesion(tmp_path, con_transcripcion=False)

    with caplog.at_level(logging.WARNING, logger="tutor.pipeline"):
        procesar_sesion(repo, GRAFO, repo.obtener_sesion("s1"), _cliente_analista(), AHORA)

    assert "sin insumo" in caplog.text
    assert repo.sesiones_sin_analizar() == [], "igual sale de la cola"


def test_una_sesion_limpia_no_dispara_ningun_aviso(tmp_path, caplog):
    """Un aviso que salta siempre deja de ser un aviso."""
    repo = _repo_con_sesion(tmp_path)
    sesion = repo.obtener_sesion("s1")
    sesion.habilidades_trabajadas = [HAB]
    repo.actualizar_sesion(sesion)

    with caplog.at_level(logging.WARNING, logger="tutor.pipeline"):
        procesar_sesion(repo, GRAFO, repo.obtener_sesion("s1"), _cliente_analista(), AHORA)

    assert caplog.text == ""


# ── Recuperar lo recuperable, sin adivinar ───────────────────────────────────


def test_un_id_inventado_se_corrige_si_la_sesion_trabajo_un_solo_nodo():
    """Mismo argumento que el del id ausente: si el banco entregó ejercicios de
    UNA habilidad, toda señal académica es de esa. No se adivina — se usa el
    dato que el código ya tenía y el modelo estaba pisando."""
    sesion = _sesion()
    sesion.habilidades_trabajadas = [HAB]
    observaciones = [
        {"habilidad_id": "mat.sumas_dobles", "tipo": TipoObservacion.ACIERTO, "evidencia": "x"}
    ]

    atadas = _atar_habilidad_unica(observaciones, sesion, GRAFO)

    assert atadas[0]["habilidad_id"] == HAB


def test_con_dos_habilidades_el_id_inventado_no_se_toca():
    """Ahí sí hay algo que decidir, y la decisión no es del código."""
    sesion = _sesion()
    sesion.habilidades_trabajadas = [HAB, OTRA_HAB]
    observaciones = [
        {"habilidad_id": "mat.sumas_dobles", "tipo": TipoObservacion.ACIERTO, "evidencia": "x"}
    ]

    atadas = _atar_habilidad_unica(observaciones, sesion, GRAFO)

    assert atadas[0]["habilidad_id"] == "mat.sumas_dobles", (
        "prefiero perderla y contarla que reescribirla con un dato que no tengo"
    )


def test_no_se_reescribe_hacia_un_id_que_tampoco_existe():
    """Si `habilidades_trabajadas` trae basura, corregir empeoraría el dato."""
    sesion = _sesion()
    sesion.habilidades_trabajadas = ["mat.tampoco_existe"]
    observaciones = [{"habilidad_id": None, "tipo": TipoObservacion.ACIERTO, "evidencia": "x"}]

    assert _atar_habilidad_unica(observaciones, sesion, GRAFO)[0]["habilidad_id"] is None


def test_sin_grafo_el_atado_se_comporta_como_antes():
    """Compatibilidad: la firma vieja sigue rellenando el null y nada más."""
    sesion = _sesion()
    sesion.habilidades_trabajadas = [HAB]
    observaciones = [
        {"habilidad_id": None, "tipo": TipoObservacion.ACIERTO, "evidencia": "x"},
        {"habilidad_id": "mat.inventada", "tipo": TipoObservacion.ACIERTO, "evidencia": "y"},
    ]

    atadas = _atar_habilidad_unica(observaciones, sesion)

    assert atadas[0]["habilidad_id"] == HAB
    assert atadas[1]["habilidad_id"] == "mat.inventada", "sin grafo no sabe que es falso"


# ─────────────────────────────────────────────────────────────────────────────
# El cambio de método, en el reporte del papá
# ─────────────────────────────────────────────────────────────────────────────


def _con_cambio() -> dict:
    """Los campos de método, para pasárselos sueltos a `_reporte`.

    Devuelve un dict y no un `MetricasReporte` a propósito: `_reporte` arma las
    métricas él, y pasarle un objeto lo metía como campo desconocido — Pydantic
    lo ignoraba en silencio y el test medía las métricas por defecto. Pasó al
    escribirlo, y es exactamente el descarte mudo que este repo persigue.
    """
    return dict(
        sesiones=4,
        minutos_totales=60,
        metodo_actual="Empezar por la estructura",
        metodo_anterior="Empezar por lo concreto",
        porque_cambio=(
            "con «Empezar por lo concreto» el nivel no se movió en 3 sesiones, "
            "así que se pasó a «Empezar por la estructura»"
        ),
    )


def test_un_reporte_que_cuenta_bien_el_cambio_no_se_tumba():
    """EL riesgo de conectar el motor al reporte, y por eso este test existe.

    La verificación compara los números del texto contra las métricas. La frase
    del porqué trae un "3 sesiones" que no está en ninguna métrica numérica, y
    sin cuidado tumbaría un reporte perfectamente correcto — la falla de la
    fase 6 al revés: un verificador que rechaza lo válido deja al papá sin nada.
    """
    reporte = _reporte(
        "Juan tuvo 4 sesiones. Con «Empezar por lo concreto» el nivel no se movió "
        "en 3 sesiones, así que se pasó a «Empezar por la estructura».",
        **_con_cambio(),
    )
    assert verificar_reporte(reporte) == []


def test_el_reporte_sigue_sin_poder_inventar_numeros():
    """Aflojar para el porqué no puede aflojar para todo lo demás."""
    reporte = _reporte(
        "Juan tuvo 4 sesiones y resolvió 47 ejercicios con el método nuevo.",
        **_con_cambio(),
    )
    problemas = verificar_reporte(reporte)
    assert any("47" in p for p in problemas), "dejó pasar un número inventado"


def test_las_metricas_traen_como_se_le_enseno(tmp_path):
    """Que el dato llegue hasta el reporte, no solo que se calcule."""
    repo = _repo_con_semana(tmp_path)
    sesiones = repo.sesiones_de("n1", AHORA - timedelta(days=7), AHORA + timedelta(days=1))
    for s in sesiones:
        s.tecnica_id = "concreto_primero"
        s.dominio_inicial = 0.2
        repo.actualizar_sesion(s)

    m = calcular_metricas(
        repo.obtener_nino("n1"),
        repo.sesiones_de("n1", AHORA - timedelta(days=7), AHORA + timedelta(days=1)),
        [],
        GRAFO,
        AHORA,
    )
    assert m.metodo_actual == "Empezar por lo concreto"
    assert m.porque_cambio is None, "no hubo cambio: no se inventa una razón"


def test_sin_tecnicas_el_reporte_no_afirma_nada_del_metodo(tmp_path):
    """Las 62 sesiones anteriores al motor están en NULL."""
    repo = _repo_con_semana(tmp_path)
    m = calcular_metricas(
        repo.obtener_nino("n1"),
        repo.sesiones_de("n1", AHORA - timedelta(days=7), AHORA + timedelta(days=1)),
        [],
        GRAFO,
        AHORA,
    )
    assert m.metodo_actual is None and m.porque_cambio is None


def test_el_auditor_recibe_lo_que_el_nino_vio_de_verdad():
    """NO PUEDE ADIVINAR EL ESTADO DE LA PANTALLA DESDE LA CONVERSACIÓN.

    Es la regla dura del proyecto: ningún agente afirma nada que no esté en los
    datos. El auditor juzga si el tutor «afirmó algo falso» sobre la pizarra, y
    hasta el 25/08 lo hacía leyendo lo que decían — en `ses_60ea3b164f17` leyó
    «¿podrías mostrarme las estrellas?» como un desmentido y acusó al tutor de
    mentir sobre unas estrellas que sí había dibujado.
    """
    from tutor.pipeline import _lo_que_vio_el_nino

    texto = _lo_que_vio_el_nino(
        [
            {"t": "latencia", "ms": 40},
            {"t": "pizarra", "que": "7 estrellas"},
            {"t": "pizarra", "que": "una cuenta 7 − 4"},
        ]
    )
    assert "7 estrellas" in texto and "una cuenta 7 − 4" in texto
    assert texto.index("7 estrellas") < texto.index("una cuenta"), "el orden importa"
    assert "latencia" not in texto, "solo lo que el niño VIO"


def test_sin_diario_el_auditor_no_recibe_nada_inventado():
    """Sesiones anteriores al 25/08, o pestañas que no alcanzaron a reportar.
    Ahí el auditor no tiene el dato — y el prompt le dice que sin dato no puede
    marcar la pizarra como falsa."""
    from tutor.pipeline import _lo_que_vio_el_nino

    assert _lo_que_vio_el_nino(None) == ""
    assert _lo_que_vio_el_nino([]) == ""


def test_una_sesion_sin_pizarra_lo_dice_explicito():
    """Distinto de no tener el dato: acá SABEMOS que no se dibujó nada, y eso es
    justo lo que convierte un «ahí te lo estoy mostrando» en afirmación falsa."""
    from tutor.pipeline import _lo_que_vio_el_nino

    texto = _lo_que_vio_el_nino([{"t": "latencia", "ms": 12}])
    assert "NADA" in texto


def test_la_pizarra_que_fallo_tambien_llega():
    """Es el caso más grave: el tutor cree que dibujó y la pantalla quedó vacía."""
    from tutor.pipeline import _lo_que_vio_el_nino

    texto = _lo_que_vio_el_nino([{"t": "pizarra_fallo", "args": '{"tipo":"grupos"}'}])
    assert "NO SE PUDO DIBUJAR" in texto
