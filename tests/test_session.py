"""Tests del orquestador de sesión.

Lo que verifican estos tests son los TRES CANDADOS de ARCHITECTURE.md §10 —
lo único que sostiene que el audio pueda ir directo sin perder el control.
"""

from datetime import datetime, timedelta

import pytest

from tutor.curriculum import cargar_grafo
from tutor.models import (
    Ejercicio,
    EstadoSesion,
    EvaluacionSeguridad,
    ModoSesion,
    Nino,
    NivelSeguridad,
    TextoLocalizado,
)
from tutor.session import (
    ErrorPresupuesto,
    ErrorSesion,
    Orquestador,
    Turno,
    prefiltro_seguridad,
)
from tutor.storage import RepositorioSQLite
from tutor.voice import EmisorFalso

AHORA = datetime(2026, 8, 17, 16, 0)


@pytest.fixture
def repo(tmp_path):
    r = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    nino = Nino(id="n1", nombre="Juan", edad=7, grado=2, creado_en=AHORA)
    nino.perfil.intereses = ["futbol"]
    r.guardar_nino(nino)
    # Ejercicios para TODA habilidad del grafo, igual que la base real. Antes
    # había solo de una, y el fixture se rompía cada vez que el planificador
    # cambiaba de opinión — acoplaba estos tests a una decisión pedagógica que
    # no es lo que están probando.
    r.guardar_ejercicios(
        [
            Ejercicio(
                id=f"e_{h.id}_{i}",
                habilidad_id=h.id,
                enunciado=TextoLocalizado(es=f"ejercicio {i}"),
                respuesta=str(i),
                validado=True,
            )
            for h in cargar_grafo()
            for i in range(20)
        ]
    )
    return r


@pytest.fixture
def orq(repo):
    return Orquestador(repo, cargar_grafo(), EmisorFalso())


def _turnos(*textos: str) -> list[Turno]:
    return [Turno(quien="nino", texto=t) for t in textos]


# ─────────────────────────────────────────────────────────────────────────────
# Prefiltro: nivel 1 de seguridad, 0ms, en código
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "dijo",
    [
        "mi papa me pega cuando llego tarde",
        "no quiero vivir mas",
        "tengo miedo de volver a mi casa",
        "es un secreto, no le digas a nadie",
        "tengo hambre",
    ],
)
def test_el_prefiltro_atrapa_lo_evidente(dijo):
    """String match: 0ms, no puede fallar por red. Antecede al Vigilante."""
    assert prefiltro_seguridad(dijo) is not None


@pytest.mark.parametrize(
    "dijo",
    ["me da miedo el resultado", "no se cuanto da", "cuarenta y dos", "mi mama me ayuda"],
)
def test_el_prefiltro_no_salta_por_cualquier_cosa(dijo):
    assert prefiltro_seguridad(dijo) is None


def test_el_prefiltro_ignora_acentos():
    assert prefiltro_seguridad("no quiero estar aquí") is not None


# ─────────────────────────────────────────────────────────────────────────────
# Abrir: todo el trabajo pesado ANTES de que el niño hable
# ─────────────────────────────────────────────────────────────────────────────


def test_abrir_deja_todo_listo(orq):
    a = orq.abrir("n1", ahora=AHORA)
    assert a.token, "el navegador recibe un token"
    # Cuál habilidad toca lo decide el planificador y ya tiene sus propios
    # tests. Acá solo importa que la sesión venga con una de verdad.
    assert a.habilidad_id in {h.id for h in cargar_grafo()}
    assert len(a.ejercicios) == 15, "precargados en memoria: durante la sesión no se consulta"
    assert a.deteccion.silencio_ms >= 1200, "paciencia calibrada por edad"


def test_candado_1_lo_que_viaja_atado_al_token(orq):
    """El navegador recibe un TOKEN, no una configuración. No puede cambiar la
    persona, el método ni la política de seguridad."""
    orq.abrir("n1", ahora=AHORA)
    atado = orq.emisor.emitidos[0].instruccion_sistema.lower()

    assert "nunca das la respuesta" in atado, "el método va atado"
    assert "escalate_safety" in atado, "la política de seguridad va atada"
    assert "juan" in atado, "y el niño de esta sesión"


def test_el_modo_pedido_endurece_el_metodo(orq):
    orq.abrir("n1", modo=ModoSesion.PEDIDO, ahora=AHORA)
    assert "no es hacerle la tarea" in orq.emisor.emitidos[0].instruccion_sistema


def test_abrir_un_nino_inexistente_falla_claro(orq):
    with pytest.raises(ErrorSesion, match="No existe el niño"):
        orq.abrir("fantasma", ahora=AHORA)


def test_candado_3_el_tope_diario_se_aplica(orq):
    """Se cobra suscripción fija: sin techo, el costo por niño es ilimitado."""
    for _ in range(3):
        a = orq.abrir("n1", ahora=AHORA)
        orq.banco(a.sesion_id).get_next_problem()  # solo cuentan las trabajadas
        orq.cerrar(a.sesion_id, ahora=AHORA)
    with pytest.raises(ErrorPresupuesto, match="tope"):
        orq.abrir("n1", ahora=AHORA)


def test_avisa_cuando_la_sesion_se_paso_de_larga(orq):
    a = orq.abrir("n1", ahora=AHORA)
    assert not orq.excedio_duracion(a.sesion_id, AHORA + timedelta(minutes=10))
    assert orq.excedio_duracion(a.sesion_id, AHORA + timedelta(minutes=90))


# ─────────────────────────────────────────────────────────────────────────────
# Durante: reportar y seguridad
# ─────────────────────────────────────────────────────────────────────────────


def test_reportar_persiste_a_mitad_de_sesion(orq, repo):
    """Si se cae la voz, el trabajo del niño no se pierde."""
    a = orq.abrir("n1", ahora=AHORA)
    orq.registrar_turnos(a.sesion_id, _turnos("hola", "cuarenta y dos"))
    assert "cuarenta y dos" in repo.obtener_transcripcion(a.sesion_id)


def test_el_prefiltro_dispara_alerta_al_instante(orq):
    a = orq.abrir("n1", ahora=AHORA)
    alertas = orq.registrar_turnos(a.sesion_id, _turnos("mi hermano me pega"))
    assert alertas and alertas[0].requiere_escalamiento
    assert alertas[0].nivel == NivelSeguridad.CRITICO


def test_el_vigilante_mira_una_ventana_no_un_turno_suelto(repo):
    """Un turno sin contexto es ambiguo; los patrones viven ENTRE turnos."""
    vistas = []

    def vigilante(ventana):
        vistas.append(len(ventana))
        return EvaluacionSeguridad(nivel=NivelSeguridad.OK)

    orq = Orquestador(repo, cargar_grafo(), EmisorFalso(), vigilante=vigilante)
    a = orq.abrir("n1", ahora=AHORA)

    orq.registrar_turnos(a.sesion_id, _turnos("uno", "dos"))
    assert not vistas, "con 2 turnos todavía no hay ventana"

    orq.registrar_turnos(a.sesion_id, _turnos("tres", "cuatro"))
    assert vistas == [4], "recién con 4 turnos evalúa"


def test_el_vigilante_no_bloquea_ni_cuando_falla(repo):
    """El tutor responde igual. La seguridad es paralela, no un cuello de botella."""
    orq = Orquestador(repo, cargar_grafo(), EmisorFalso())  # sin vigilante
    a = orq.abrir("n1", ahora=AHORA)
    assert orq.registrar_turnos(a.sesion_id, _turnos("a", "b", "c", "d")) == []


def test_candado_2_sin_reportar_no_hay_recarga(orq):
    """Un cliente que deja de reportar se queda sin ejercicios."""
    a = orq.abrir("n1", ahora=AHORA)
    with pytest.raises(ErrorSesion, match="No hay turnos nuevos"):
        orq.recargar_ejercicios(a.sesion_id)

    orq.registrar_turnos(a.sesion_id, _turnos("cuarenta y dos"))
    assert orq.recargar_ejercicios(a.sesion_id), "reportando sí recarga"


def test_el_banco_entrega_sin_tocar_la_base(orq):
    a = orq.abrir("n1", ahora=AHORA)
    banco = orq.banco(a.sesion_id)
    assert banco.get_next_problem() is not None
    assert banco.restantes == 14


# ─────────────────────────────────────────────────────────────────────────────
# Cerrar y reanudar
# ─────────────────────────────────────────────────────────────────────────────


def test_cerrar_encola_para_el_analista(orq, repo):
    a = orq.abrir("n1", ahora=AHORA)
    orq.registrar_turnos(a.sesion_id, _turnos("hola"))
    orq.banco(a.sesion_id).get_next_problem()

    sesion = orq.cerrar(a.sesion_id, ahora=AHORA + timedelta(minutes=25), tokens_consumidos=4200)

    assert sesion.estado == EstadoSesion.COMPLETADA
    assert sesion.analizada is False, "queda en la cola del Analista"
    assert sesion.habilidades_trabajadas == [a.habilidad_id]
    assert [s.id for s in repo.sesiones_sin_analizar()] == [a.sesion_id]


def test_una_sesion_caida_se_puede_reanudar(orq, repo):
    a = orq.abrir("n1", ahora=AHORA)
    orq.registrar_turnos(a.sesion_id, _turnos("estaba en la mitad"))
    orq.cerrar(a.sesion_id, ahora=AHORA, interrumpida=True)

    assert repo.obtener_sesion(a.sesion_id).estado == EstadoSesion.INTERRUMPIDA
    nueva = orq.reanudar(a.sesion_id)
    assert nueva.sesion_id != a.sesion_id
    assert nueva.token


def test_no_se_reanuda_una_sesion_terminada_bien(orq):
    a = orq.abrir("n1", ahora=AHORA)
    orq.cerrar(a.sesion_id, ahora=AHORA)
    with pytest.raises(ErrorSesion, match="interrumpidas"):
        orq.reanudar(a.sesion_id)


def test_cerrar_libera_la_memoria(orq):
    a = orq.abrir("n1", ahora=AHORA)
    orq.cerrar(a.sesion_id, ahora=AHORA)
    with pytest.raises(ErrorSesion):
        orq.banco(a.sesion_id)


def test_una_sesion_que_no_se_uso_no_quema_un_cupo(orq, repo):
    """Si un chico abre la app y se corta internet, o toca el boton sin querer,
    no puede perder uno de sus 3 cupos del dia sin haber aprendido nada."""
    for _ in range(3):
        a = orq.abrir("n1", ahora=AHORA)
        orq.cerrar(a.sesion_id, ahora=AHORA, interrumpida=True)  # sin trabajar nada

    # Las tres quedaron vacias: el cupo sigue entero.
    assert orq.abrir("n1", ahora=AHORA)


def test_las_sesiones_donde_si_trabajo_cuentan(orq):
    for _ in range(3):
        a = orq.abrir("n1", ahora=AHORA)
        orq.banco(a.sesion_id).get_next_problem()  # trabajo de verdad
        orq.cerrar(a.sesion_id, ahora=AHORA)

    with pytest.raises(ErrorPresupuesto, match="tope"):
        orq.abrir("n1", ahora=AHORA)


def test_un_nino_no_puede_tener_dos_sesiones_de_voz_a_la_vez(orq, repo):
    """El cuarto candado, y el único que el navegador no puede evadir.

    Cada puerta del navegador abre una conexión Live nueva y deja viva la
    anterior: recargar la página, el hot-reload de Vite, dos pestañas, un doble
    clic. Las viejas siguen hablando por los mismos parlantes — el niño oye dos
    tutores encima y el audio se traba.

    En la prueba del 18/08 el backend registró tres POST /api/sesiones seguidos
    y una sola sesión con turnos: las otras dos nunca se cerraron. Se taparon de
    a una en el frontend hasta que quedó claro que el candado estaba del lado
    que no controlamos.
    """
    primera = orq.abrir("n1", ahora=AHORA)
    segunda = orq.abrir("n1", ahora=AHORA + timedelta(seconds=3))

    assert primera.sesion_id != segunda.sesion_id

    vieja = repo.obtener_sesion(primera.sesion_id)
    assert vieja is not None
    assert vieja.estado == EstadoSesion.INTERRUMPIDA, (
        "la sesión anterior quedó viva: dos conexiones Live hablando a la vez"
    )
    assert vieja.fin is not None, "se cerró sin registrar cuándo"

    nueva = repo.obtener_sesion(segunda.sesion_id)
    assert nueva is not None
    assert nueva.estado == EstadoSesion.ACTIVA, "gana la última, no la primera"


def test_recargar_la_pagina_no_deja_al_nino_sin_poder_empezar(orq):
    """Gana la última: se cierra la previa, no se rechaza la nueva.

    Si el candado rechazara la segunda, recargar la página dejaría al niño
    trabado hasta que venciera algo que él no ve — que es peor que el bug.
    """
    orq.abrir("n1", ahora=AHORA)
    for i in range(1, 4):
        abierta = orq.abrir("n1", ahora=AHORA + timedelta(seconds=i * 5))
        assert abierta.token, f"la recarga #{i} se quedó sin sesión"
